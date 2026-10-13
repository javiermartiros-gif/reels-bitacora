"""
scheduler.py

Construye el calendario de publicación para un lote de variantes, repartidas
en un rango de días (por defecto 14), probando distintas franjas horarias y
emparejando cada variante con un audio distinto.

Lógica de "optimización" aplicada (simple pero con criterio, no aleatoria):
  - Intervalo base de 2-3 días entre publicaciones (configurable), para que
    el algoritmo trate cada Trial Reel como contenido nuevo y no como
    repetición inmediata del anterior.
  - Las franjas horarias rotan (mañana / mediodía / tarde / noche) en vez de
    repetir siempre la misma hora, para descubrir con los propios datos qué
    franja funciona mejor para esta cuenta.
  - Nunca se repite el mismo audio en dos publicaciones consecutivas del
    lote, aunque la lista de audios tenga menos variedad que de reels.
  - Se guarda, por cada entrada, qué hook y qué audio usó, para que
    analytics.py pueda luego cruzar rendimiento con estas variables.

Uso:
    python scheduler.py --manifest ./out/variants_manifest.json \
                         --audios audios.txt --days 14 --out ./data/schedule.json
"""

import argparse
import json
import pathlib
from datetime import datetime, timedelta, time

# Franjas horarias a rotar (hora local de la cuenta). Ajusta si tu audiencia
# tiene un huso distinto.
TIME_SLOTS = [
    time(8, 30),   # mañana, antes de clase/trabajo
    time(13, 15),  # mediodía
    time(19, 0),   # tarde-noche, pico de uso típico
    time(21, 45),  # noche
]


def _read_lines(path: str) -> list[str]:
    return [l.strip() for l in pathlib.Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def build_schedule(
    manifest_path: str,
    audios_path: str,
    days_span: int = 14,
    min_gap_days: float = 2.0,
    start_date: datetime | None = None,
) -> list[dict]:
    manifest = json.loads(pathlib.Path(manifest_path).read_text())
    audios = _read_lines(audios_path)

    if len(audios) == 0:
        raise ValueError("No hay audios en el archivo proporcionado.")

    n = len(manifest)
    if n == 0:
        raise ValueError("El manifiesto no tiene variantes.")

    start_date = start_date or datetime.now()
    # Separación uniforme a lo largo del rango de días, respetando el gap mínimo.
    max_possible_gap = days_span / max(n - 1, 1)
    gap_days = max(min_gap_days, min(max_possible_gap, 3.0))

    schedule = []
    last_audio = None
    for i, item in enumerate(manifest):
        day_offset = round(i * gap_days, 2)
        slot = TIME_SLOTS[i % len(TIME_SLOTS)]
        publish_dt = (start_date + timedelta(days=day_offset)).replace(
            hour=slot.hour, minute=slot.minute, second=0, microsecond=0
        )

        # Elegir audio evitando repetir el inmediatamente anterior
        audio = audios[i % len(audios)]
        if audio == last_audio and len(audios) > 1:
            audio = audios[(i + 1) % len(audios)]
        last_audio = audio

        schedule.append({
            "index": item["index"],
            "hook": item["hook"],
            "video_file": item["file"],
            "audio": audio,
            "scheduled_for": publish_dt.isoformat(),
            "status": "pending",  # pending | published | failed
        })

    return schedule


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Genera el calendario óptimo de publicación.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--audios", required=True)
    parser.add_argument("--days", type=float, default=14)
    parser.add_argument("--out", default="./data/schedule.json")
    args = parser.parse_args()

    schedule = build_schedule(args.manifest, args.audios, days_span=args.days)
    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(schedule, ensure_ascii=False, indent=2))

    print(f"Calendario generado con {len(schedule)} publicaciones en {out_path}")
    for s in schedule:
        print(f"  #{s['index']:02d}  {s['scheduled_for']}  audio='{s['audio']}'  hook='{s['hook'][:40]}'")
