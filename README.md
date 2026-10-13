# Instagram Trial Reels — Automatizador de variantes

Sube 1 vídeo base, genera 10 variantes (hook distinto quemado en pantalla + audio
distinto + pequeña variación de recorte), las programa como Reels de prueba
repartidos en ~2 semanas, y te avisa si un reel está rindiendo peor por
similitud con otro publicado antes.

## Lo que SÍ hace solo
- Generar las 10 variantes de vídeo (ffmpeg).
- Repartir el calendario de publicación (fecha + hora) de forma óptima.
- Publicar cada Trial Reel en su momento (GitHub Actions, sin que tengas el
  ordenador encendido).
- Leer insights después de publicar y generarte un informe de por qué un
  reel concreto rinde peor que la media (mismo hook repetido, mismo audio,
  publicado muy cerca de otro similar, etc.).

## Lo que necesitas tú (una sola vez, no por cada lote)
1. **Cuenta de Instagram en modo Business o Creator**, vinculada a una
   Página de Facebook. (Ajustes → Cuenta → Cambiar a cuenta profesional).
   Necesitas 1.000+ seguidores para que Instagram habilite los Trial Reels.
2. **Crear una app en** [developers.facebook.com](https://developers.facebook.com/apps) →
   tipo "Business" → añadir el producto "Instagram Graph API".
3. Añadir tu propia cuenta de Instagram como **tester** de esa app (dentro
   de Roles → Testers de Instagram). Esto evita tener que pasar la revisión
   de Meta (App Review), porque solo publicas en tu propia cuenta.
4. Generar un **token de acceso de larga duración** (60 días, renovable) desde
   el Explorador de la Graph API con los permisos:
   `instagram_basic`, `instagram_content_publish`, `pages_show_list`,
   `pages_read_engagement`.
5. Copiar `.env.example` a `.env` y rellenar (es el mismo `.env` que usa el
   contenedor Docker):
   - `IG_BUSINESS_ACCOUNT_ID`
   - `FB_PAGE_ACCESS_TOKEN`
   - Un host público donde los vídeos generados sean descargables por Meta
     (la API no acepta subida directa de binario desde tu disco: necesita
     una URL. Lo más simple y gratis: subirlos a un repo privado de GitHub
     y usar el enlace "raw", o a un bucket S3/R2 gratuito. El script ya
     deja el hueco listo — dime cuál prefieres y te lo conecto).

## Arrancar la interfaz
```
docker compose up
```
Abre `http://localhost:5000`. Los vídeos, variantes y el calendario se
guardan en `./uploads`, `./out` y `./data` en tu propio disco (montados
como volúmenes), así que sobreviven a reinicios del contenedor.

## Lo que haces tú en cada lote (lo mínimo posible)
1. Editas el vídeo en Edits, eligiendo el audio desde el panel "Audio en
   tendencia" de tu Dashboard Profesional de Instagram, y exportas.
2. Abres `localhost:5000` → "Nuevo lote".
3. Arrastras el vídeo, anotas qué audio usaste, añades los hooks (hay
   sugerencias precargadas, clic para insertarlas) y el nº de días para
   repartir el lote.
4. Pulsas "Generar y programar".
5. En la pestaña "Calendario" ves el estado de cada variante (pendiente /
   publicado / fallido) a medida que GitHub Actions las va subiendo.

A partir del paso 4, todo corre solo.

## Estructura del proyecto
```
app.py                  # interfaz web (subir vídeo + hooks + audios)
generate_variants.py    # genera los 10 .mp4 con ffmpeg
scheduler.py            # calcula fechas/horas óptimas de publicación
publish.py              # llama a la Graph API para publicar como Trial Reel
analytics.py            # informe de rendimiento + detección de canibalización
data/schedule.json      # cola de publicaciones pendientes (se genera solo)
.github/workflows/      # cron que ejecuta publish.py cada día
```

## Sobre el audio "trending" (limitación real, no de esta herramienta)
Instagram no expone su librería de audio con licencia por API — solo se ve
y selecciona dentro de la app. No hay forma de automatizar ese paso sin usar
un audio descargado por fuera (lo cual tiene riesgo de copyright y pierde el
boost de distribución que da el algoritmo a los audios "nativos" de IG). Por
eso ese único campo lo rellenas tú a mano, el resto es 100% automático.
