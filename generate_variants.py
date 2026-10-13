"""
generate_variants.py

Coge un vídeo base y una lista de hooks (texto a quemar en pantalla),
y genera N variantes .mp4 listas para publicar.

Cada variante:
  - Quema el hook correspondiente en la parte superior del vídeo.
  - Aplica una micro-variación real (recorte de 0.3-0.8s al inicio,
    ligera variación de brillo/saturación) para que no sean pixel-a-pixel
    idénticas entre sí. Instagram penaliza el contenido "casi duplicado"
    publicado en ráfaga; esto reduce ese riesgo sin cambiar el mensaje.

Requiere ffmpeg instalado en el sistema.

Uso:
    python generate_variants.py --video base.mp4 --hooks hooks.txt --out ./out
"""

import argparse
import hashlib
import json
import pathlib
import random
import subprocess
import sys

FONT_SIZE = 64
FONT_COLOR = "white"
BOX_COLOR = "black@0.55"
TEXT_Y = "h*0.08"  # near the top, standard hook placement


def _escape_drawtext(text: str) -> str:
    """Escape characters that break ffmpeg's drawtext filter."""
    return (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\u2019")  # swap straight quotes for a safe typographic one
        .replace("%", "\\%")
    )


def build_variant(
    video_path: pathlib.Path,
    hook_text: str,
    out_path: pathlib.Path,
    variant_index: int,
    font_path: str | None = None,
) -> None:
    """Render one variant with its hook burned in and a small randomized edit."""
    rng = random.Random(variant_index)  # deterministic per-variant, still varied

    # Micro-variation: trim 0.2-0.9s off the start, nudge brightness/saturation
    # a few percent. Keeps the clip visually distinct without changing content.
    start_trim = round(rng.uniform(0.2, 0.9), 2)
    brightness = round(rng.uniform(-0.03, 0.03), 3)
    saturation = round(rng.uniform(0.97, 1.05), 3)

    safe_text = _escape_drawtext(hook_text)
    font_clause = f":fontfile='{font_path}'" if font_path else ""

    drawtext = (
        f"drawtext=text='{safe_text}'{font_clause}:"
        f"fontsize={FONT_SIZE}:fontcolor={FONT_COLOR}:"
        f"box=1:boxcolor={BOX_COLOR}:boxborderw=20:"
        f"x=(w-text_w)/2:y={TEXT_Y}:"
        "line_spacing=8"
    )
    eq = f"eq=brightness={brightness}:saturation={saturation}"
    vf = f"{eq},{drawtext}"

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_trim),
        "-i", str(video_path),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg falló en variante {variant_index}:\n{result.stderr[-2000:]}")


def generate_all(video_path: str, hooks: list[str], out_dir: str) -> list[dict]:
    video_path = pathlib.Path(video_path)
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not video_path.exists():
        raise FileNotFoundError(f"No existe el vídeo base: {video_path}")

    manifest = []
    for i, hook in enumerate(hooks, start=1):
        hook = hook.strip()
        if not hook:
            continue
        fname = f"variant_{i:02d}_{hashlib.sha1(hook.encode()).hexdigest()[:6]}.mp4"
        out_path = out_dir / fname
        build_variant(video_path, hook, out_path, variant_index=i)
        manifest.append({
            "index": i,
            "hook": hook,
            "file": str(out_path),
            "filename": fname,
        })

    manifest_path = out_dir / "variants_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


def _read_hooks_file(path: str) -> list[str]:
    lines = pathlib.Path(path).read_text(encoding="utf-8").splitlines()
    return [l for l in lines if l.strip()]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Genera variantes de un reel con hooks distintos.")
    parser.add_argument("--video", required=True, help="Ruta al vídeo base")
    parser.add_argument("--hooks", required=True, help="Archivo .txt con un hook por línea")
    parser.add_argument("--out", default="./out", help="Carpeta de salida")
    args = parser.parse_args()

    hooks = _read_hooks_file(args.hooks)
    if len(hooks) == 0:
        print("No se encontraron hooks en el archivo.", file=sys.stderr)
        sys.exit(1)

    manifest = generate_all(args.video, hooks, args.out)
    print(f"Generadas {len(manifest)} variantes en {args.out}/")
    print(f"Manifiesto: {args.out}/variants_manifest.json")
