FROM node:20-alpine AS frontend
WORKDIR /build
COPY package.json package-lock.json tailwind.config.js ./
RUN npm ci
COPY static ./static
RUN npm run build:css

FROM python:3.9-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_ENV=demo
RUN groupadd --system smartwaste && useradd --system --gid smartwaste --home /app smartwaste
WORKDIR /app
COPY requirements-runtime.txt ./
RUN pip install --no-cache-dir -r requirements-runtime.txt
COPY --chown=smartwaste:smartwaste . .
COPY --from=frontend --chown=smartwaste:smartwaste /build/static/smartwaste.css /app/static/smartwaste.css
RUN mkdir -p /app/var/private_media && chown smartwaste:smartwaste /app/var/private_media
USER smartwaste
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=3)"
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1"]
