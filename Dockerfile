FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg git curl \
    && rm -rf /var/lib/apt/lists/*

# Fuente para los hooks quemados en el vídeo: Poppins ExtraBold, estilo típico
# de hook de Reels (gruesa, redondeada, muy legible en móvil). Sin esto,
# ffmpeg usa la fuente por defecto del sistema, que se ve básica y pequeña.
RUN mkdir -p /app/fonts && \
    curl -sL -o /app/fonts/Poppins-ExtraBold.ttf \
    "https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/Poppins-ExtraBold.ttf"

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

# Render inyecta $PORT en tiempo de ejecución
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-5000} --timeout 180 app:app"]
