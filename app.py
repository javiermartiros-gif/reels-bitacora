"""
app.py

Interfaz local (Flask) para el flujo completo:
  1. Subes el vídeo ya editado en Edits (con o sin audio/hook quemado).
  2. Anotas qué audio usaste (lo eliges tú en el panel "Audio en tendencia"
     de tu Dashboard Profesional de Instagram; aquí solo se registra el
     nombre para poder cruzarlo luego con el rendimiento).
  3. Eliges uno de los hooks sugeridos o escribes el tuyo. Si quieres varias
     variantes del mismo clip con hooks distintos, los añades todos.
  4. Al pulsar "Generar y programar", el backend quema los hooks (si no
     venían ya quemados desde Edits), calcula el calendario óptimo de
     publicación, y deja todo listo en data/schedule.json para que
     publish.py (vía GitHub Actions) lo vaya publicando solo.

Ejecutar con: python app.py
Abre: http://localhost:5000
"""

import pathlib
import uuid

from flask import Flask, render_template, request, redirect, url_for, flash

from generate_variants import generate_all
from scheduler import build_schedule

app = Flask(__name__)
app.secret_key = "dev-local-only"  # solo corre en local, no hace falta más

UPLOAD_DIR = pathlib.Path("uploads")
OUT_DIR = pathlib.Path("out")
DATA_DIR = pathlib.Path("data")
UPLOAD_DIR.mkdir(exist_ok=True)
OUT_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# Plantillas de hook genéricas, validadas para contenido de deporte/acción:
# contraste, pregunta directa, cifra concreta, o "POV". Son punto de partida
# editable, no texto final — se muestran precargadas en el formulario.
HOOK_SUGGESTIONS = [
    "POV: el viento sube a 25 nudos y tú ya estás en el agua",
    "Nadie te prepara para esta sensación la primera vez",
    "3 años de kite resumidos en 15 segundos",
    "Esto es lo que pasa cuando confías en la racha",
    "La diferencia entre un buen y un mal día de kite está aquí",
]


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", hook_suggestions=HOOK_SUGGESTIONS, active="nuevo")


@app.route("/calendario", methods=["GET"])
def calendario():
    schedule_path = DATA_DIR / "schedule.json"
    entries = []
    if schedule_path.exists():
        import json
        entries = json.loads(schedule_path.read_text())
        entries.sort(key=lambda e: e["scheduled_for"])
    return render_template("calendario.html", entries=entries, active="calendario")


@app.route("/submit", methods=["POST"])
def submit():
    video = request.files.get("video")
    audio_name = request.form.get("audio_name", "").strip()
    hooks_raw = request.form.get("hooks", "")
    hooks = [h.strip() for h in hooks_raw.splitlines() if h.strip()]
    days_span = float(request.form.get("days_span", 14))

    if not video or video.filename == "":
        flash("Tienes que subir un vídeo.")
        return redirect(url_for("index"))
    if not hooks:
        flash("Añade al menos un hook.")
        return redirect(url_for("index"))
    if not audio_name:
        flash("Indica qué audio usaste (lo eliges en el panel de Instagram).")
        return redirect(url_for("index"))

    batch_id = uuid.uuid4().hex[:8]
    video_path = UPLOAD_DIR / f"{batch_id}_{video.filename}"
    video.save(video_path)

    batch_out_dir = OUT_DIR / batch_id
    manifest = generate_all(str(video_path), hooks, str(batch_out_dir))

    # Un único audio anotado para todo el lote (el audio ya viene integrado
    # en el vídeo subido). Si en el futuro subes variantes con audios
    # distintos por hook, este campo pasa a leerse por variante.
    audios_file = batch_out_dir / "_audio.txt"
    audios_file.write_text(audio_name)

    schedule = build_schedule(
        manifest_path=str(batch_out_dir / "variants_manifest.json"),
        audios_path=str(audios_file),
        days_span=days_span,
    )

    # Fusiona con el calendario existente (si ya había publicaciones de
    # otros lotes pendientes) en vez de sobrescribirlo.
    schedule_path = DATA_DIR / "schedule.json"
    existing = []
    if schedule_path.exists():
        import json
        existing = json.loads(schedule_path.read_text())
    import json
    schedule_path.write_text(json.dumps(existing + schedule, ensure_ascii=False, indent=2))

    flash(f"Listo. {len(schedule)} variantes generadas y añadidas al calendario de publicación.")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
