"""
publish.py

Publica como Trial Reel las entradas de data/schedule.json cuya fecha ya
ha llegado. Pensado para ejecutarse una vez al día desde GitHub Actions
(ver .github/workflows/scheduled-publish.yml), pero también funciona en
local con `python publish.py --run-due`.

Flujo de la Graph API (2 pasos, como exige Meta para vídeo):
  1. POST /{ig-user-id}/media  → crea el contenedor con video_url, caption,
     media_type=REELS y trial_params (lo marca como Trial Reel).
  2. Poll de GET /{container-id}?fields=status_code hasta que esté FINISHED.
  3. POST /{ig-user-id}/media_publish → publica el contenedor.

IMPORTANTE: Meta no acepta subir el binario directamente desde tu disco;
necesita una URL pública (PUBLIC_VIDEO_HOST_URL en .env) desde la que
descargar cada vídeo. Si tus variantes están en un repo de GitHub, usa el
enlace raw.githubusercontent.com correspondiente.
"""

import argparse
import json
import os
import pathlib
import sys
import time as time_module
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

GRAPH_VERSION = os.getenv("GRAPH_API_VERSION", "v22.0")
IG_USER_ID = os.getenv("IG_BUSINESS_ACCOUNT_ID")
ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN")
PUBLIC_HOST = os.getenv("PUBLIC_VIDEO_HOST_URL", "")

BASE_URL = f"https://graph.facebook.com/{GRAPH_VERSION}"
SCHEDULE_PATH = pathlib.Path("data/schedule.json")


def _require_env():
    missing = [k for k, v in {
        "IG_BUSINESS_ACCOUNT_ID": IG_USER_ID,
        "FB_PAGE_ACCESS_TOKEN": ACCESS_TOKEN,
    }.items() if not v]
    if missing:
        print(f"Faltan variables de entorno: {', '.join(missing)}. Revisa .env", file=sys.stderr)
        sys.exit(1)


def _video_public_url(local_path: str) -> str:
    # Conserva la ruta relativa completa (p. ej. "out/<batch_id>/variant_01.mp4"),
    # no solo el nombre del archivo, porque así es como queda subido en el repo.
    rel_path = pathlib.Path(local_path).as_posix().lstrip("./")
    if not PUBLIC_HOST:
        raise RuntimeError(
            "PUBLIC_VIDEO_HOST_URL no está configurado en .env. "
            "Necesitas un host público desde el que Meta pueda descargar el vídeo."
        )
    return f"{PUBLIC_HOST.rstrip('/')}/{rel_path}"


def create_container(video_url: str, caption: str, as_trial: bool = True) -> str:
    payload = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": ACCESS_TOKEN,
    }
    if as_trial:
        # graduationStrategy=MANUAL: el reel se queda en modo trial hasta que
        # tú decides promocionarlo a tus seguidores desde la app. Cámbialo a
        # AUTO si quieres que Instagram lo gradúe solo según el rendimiento.
        payload["trial_params"] = json.dumps({"graduation_strategy": "MANUAL"})

    resp = requests.post(f"{BASE_URL}/{IG_USER_ID}/media", data=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()["id"]


def wait_until_ready(container_id: str, timeout_s: int = 600, poll_s: int = 10) -> None:
    deadline = time_module.time() + timeout_s
    while time_module.time() < deadline:
        resp = requests.get(
            f"{BASE_URL}/{container_id}",
            params={"fields": "status_code", "access_token": ACCESS_TOKEN},
            timeout=30,
        )
        resp.raise_for_status()
        status = resp.json().get("status_code")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError(f"El contenedor {container_id} falló al procesarse.")
        time_module.sleep(poll_s)
    raise TimeoutError(f"El contenedor {container_id} no terminó de procesarse a tiempo.")


def publish_container(container_id: str) -> str:
    resp = requests.post(
        f"{BASE_URL}/{IG_USER_ID}/media_publish",
        data={"creation_id": container_id, "access_token": ACCESS_TOKEN},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def publish_entry(entry: dict) -> dict:
    video_url = _video_public_url(entry["video_file"])
    # El audio elegido no se puede fijar por API (ver README); se añade al
    # caption como recordatorio si decides finalizar el audio manualmente
    # desde la app antes de que termine de procesarse.
    caption = entry["hook"]

    container_id = create_container(video_url, caption, as_trial=True)
    wait_until_ready(container_id)
    media_id = publish_container(container_id)
    return {"media_id": media_id, "container_id": container_id}


def run_due(now: datetime | None = None, dry_run: bool = False) -> None:
    _require_env()
    now = now or datetime.now()

    if not SCHEDULE_PATH.exists():
        print("No existe data/schedule.json todavía.", file=sys.stderr)
        sys.exit(1)

    schedule = json.loads(SCHEDULE_PATH.read_text())
    changed = False

    for entry in schedule:
        if entry["status"] != "pending":
            continue
        scheduled_for = datetime.fromisoformat(entry["scheduled_for"])
        if scheduled_for > now:
            continue

        print(f"Publicando #{entry['index']:02d} (programado para {entry['scheduled_for']})...")
        if dry_run:
            print("  [dry-run] no se publica de verdad.")
            continue
        try:
            result = publish_entry(entry)
            entry["status"] = "published"
            entry["published_at"] = now.isoformat()
            entry["media_id"] = result["media_id"]
            print(f"  OK, media_id={result['media_id']}")
        except Exception as exc:
            entry["status"] = "failed"
            entry["error"] = str(exc)
            print(f"  ERROR: {exc}", file=sys.stderr)
        changed = True

    if changed and not dry_run:
        SCHEDULE_PATH.write_text(json.dumps(schedule, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Publica los reels pendientes cuya fecha ya llegó.")
    parser.add_argument("--run-due", action="store_true", help="Ejecuta las publicaciones pendientes")
    parser.add_argument("--dry-run", action="store_true", help="Simula sin publicar de verdad")
    args = parser.parse_args()

    if args.run_due:
        run_due(dry_run=args.dry_run)
    else:
        parser.print_help()
