# python-app
API REST de items con Flask + PostgreSQL, servida con gunicorn. Rutas: `/`, `/health`, `/api/items[/<id>]`.
Variables: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, APP_MESSAGE (ver `.env.example`).
Puerto del contenedor: 8000.
Probar en local:
    docker build -t python-app . && docker run --rm -p 8000:8000 --env-file .env python-app
    curl -X POST localhost:8000/api/items -H 'Content-Type: application/json' -d '{"nombre":"a"}'
# python-app
