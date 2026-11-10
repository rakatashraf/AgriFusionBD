# FieldShift backend — uv-managed venv (user request: "use docker and uv").
#
# Build:  docker build -t fieldshift-backend .
# Run:    docker run --env-file .env -p 8000:8000 fieldshift-backend
FROM python:3.15-slim AS base

# System deps for psycopg (binary wheel) and GDAL for GeoDjango.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgdal-dev gdal-bin libproj-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast, reproducible venvs).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy requirements first so the dependency layer is cached independently of
# source changes.
COPY requirements.txt .

ENV UV_LINK_MODE=copy
RUN uv venv .venv \
    && uv pip install --python .venv/bin/python -r requirements.txt

# Then the rest of the app.
COPY . .

ENV PATH="/app/.venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings.dev \
    GDAL_LIBRARY_PATH=/usr/lib/libgdal.so

EXPOSE 8000

# Entrypoint: migrate (idempotent) then serve.
# gunicorn for the prod story; runserver for the dev story is also fine.
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py seed_demo && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 60"]
