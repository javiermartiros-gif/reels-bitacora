#!/bin/bash
# Sube los vídeos generados y el calendario actualizado al repo de GitHub,
# para que queden en una URL pública que la Graph API pueda descargar, y
# para que GitHub Actions tenga el calendario al día.
#
# Ejecútalo DESPUÉS de pulsar "Generar y programar" en la interfaz, y ANTES
# de la fecha programada del primer vídeo del lote.
#
# Uso: ./push_batch.sh

set -e

if [ ! -d .git ]; then
  echo "Esta carpeta todavía no es un repo git. Sigue el paso C del README primero."
  exit 1
fi

git add out/ data/schedule.json
if git diff --staged --quiet; then
  echo "No hay cambios nuevos que subir."
  exit 0
fi

git commit -m "Nuevo lote: $(date '+%Y-%m-%d %H:%M')"
git push

echo "Listo. Vídeos y calendario subidos al repo."
