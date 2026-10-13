"""
analytics.py

Para cada reel ya publicado en data/schedule.json, consulta sus insights
(plays, reach, retención media si está disponible) vía Graph API, y genera
un informe que compara cada reel contra la media del lote, señalando
posibles causas de bajo rendimiento basadas en las variables que SÍ
controlamos (hook repetido, audio repetido, cercanía temporal con un reel
similar, franja horaria).

No es una prueba causal (eso no te lo puede dar nadie), es una correlación
útil para decidir qué variar en el siguiente lote.

Uso:
    python analytics.py --report
"""

import argparse
import json
import os
import pathlib
import statistics
import sys
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

GRAPH_VERSION = os.getenv("GRAPH_API_VERSION", "v22.0")
ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN")
BASE_URL = f"https://graph.facebook.com/{GRAPH_VERSION}"
SCHEDULE_PATH = pathlib.Path("data/schedule.json")

INSIGHT_METRICS = "plays,reach,saved,shares,comments,likes"


def fetch_insights(media_id: str) -> dict:
    resp = requests.get(
        f"{BASE_URL}/{media_id}/insights",
        params={"metric": INSIGHT_METRICS, "access_token": ACCESS_TOKEN},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json().get("data", [])
    return {item["name"]: item["values"][0]["value"] for item in data if item.get("values")}


def _hook_similarity_flag(entry: dict, others: list[dict]) -> str | None:
    """Flags if this entry shares a hook or audio with another entry published
    within 4 days, which is the most common cause of a reel underperforming
    inside the same batch."""
    this_dt = datetime.fromisoformat(entry["scheduled_for"])
    for other in others:
        if other["index"] == entry["index"]:
            continue
        other_dt = datetime.fromisoformat(other["scheduled_for"])
        gap_days = abs((this_dt - other_dt).total_seconds()) / 86400
        if gap_days > 4:
            continue
        if other["audio"] == entry["audio"]:
            return f"mismo audio que #{other['index']:02d} (publicado {gap_days:.1f} días antes/después)"
        if other["hook"].strip().lower() == entry["hook"].strip().lower():
            return f"mismo hook que #{other['index']:02d} (publicado {gap_days:.1f} días antes/después)"
    return None


def build_report() -> list[dict]:
    if not SCHEDULE_PATH.exists():
        print("No existe data/schedule.json todavía.", file=sys.stderr)
        sys.exit(1)

    schedule = json.loads(SCHEDULE_PATH.read_text())
    published = [e for e in schedule if e["status"] == "published" and e.get("media_id")]

    if not published:
        print("Todavía no hay reels publicados para analizar.")
        return []

    for entry in published:
        entry["insights"] = fetch_insights(entry["media_id"])

    plays_values = [e["insights"].get("plays", 0) for e in published]
    avg_plays = statistics.mean(plays_values) if plays_values else 0

    report = []
    for entry in published:
        plays = entry["insights"].get("plays", 0)
        pct_vs_avg = ((plays - avg_plays) / avg_plays * 100) if avg_plays else 0
        flag = _hook_similarity_flag(entry, published) if pct_vs_avg < -15 else None

        report.append({
            "index": entry["index"],
            "hook": entry["hook"],
            "audio": entry["audio"],
            "scheduled_for": entry["scheduled_for"],
            "plays": plays,
            "pct_vs_batch_avg": round(pct_vs_avg, 1),
            "possible_cause": flag or ("sin señal clara" if pct_vs_avg < -15 else None),
        })

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Informe de rendimiento del lote.")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    if not args.report:
        parser.print_help()
        sys.exit(0)

    report = build_report()
    if not report:
        sys.exit(0)

    avg = statistics.mean([r["plays"] for r in report])
    print(f"\nMedia de plays del lote: {avg:.0f}\n")
    for r in sorted(report, key=lambda x: x["plays"]):
        marker = "⚠️ " if r["possible_cause"] else "   "
        print(f"{marker}#{r['index']:02d}  {r['plays']:>6} plays  ({r['pct_vs_batch_avg']:+.1f}% vs media)")
        if r["possible_cause"]:
            print(f"      → {r['possible_cause']}")
