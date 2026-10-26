import html
import logging
import os
import time
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, jsonify, request

VERSION = "v1"
DB_VARS = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]

app = Flask(__name__)
log = logging.getLogger("app")
logging.basicConfig(level=logging.INFO)


def faltantes():
    return [v for v in DB_VARS if not os.environ.get(v)]


@contextmanager
def cursor():
    conn = psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=os.environ["DB_PORT"],
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        connect_timeout=3,
    )
    try:
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
    finally:
        conn.close()


def init_db():
    if faltantes():
        log.warning("Faltan variables de entorno: %s", ", ".join(faltantes()))
        return
    for i in range(1, 11):
        try:
            with cursor() as cur:
                cur.execute(
                    """CREATE TABLE IF NOT EXISTS items (
                        id SERIAL PRIMARY KEY,
                        nombre VARCHAR(100) NOT NULL,
                        descripcion TEXT,
                        creado TIMESTAMP DEFAULT now()
                    )"""
                )
            log.info("BD lista")
            return
        except psycopg2.Error as e:
            log.warning("BD intento %d/10 fallido: %s", i, e)
            if i < 10:
                time.sleep(3)
    log.error("BD no disponible, se arranca igualmente")


def validar(datos):
    if not isinstance(datos, dict):
        return None, "Se esperaba un objeto JSON"
    nombre = datos.get("nombre")
    descripcion = datos.get("descripcion") or ""
    if not isinstance(nombre, str) or not nombre.strip() or len(nombre.strip()) > 100:
        return None, "'nombre' es obligatorio (1-100 caracteres)"
    if not isinstance(descripcion, str):
        return None, "'descripcion' debe ser texto"
    return (nombre.strip(), descripcion), None


def no_encontrado():
    return jsonify(error="Item no encontrado"), 404


@app.before_request
def comprobar_config():
    if request.path.startswith("/api/") and faltantes():
        return jsonify(error="Faltan variables de entorno: " + ", ".join(faltantes())), 503


@app.after_request
def powered_by(resp):
    resp.headers["X-Powered-By"] = "Flask"
    return resp


@app.get("/health")
def health():
    if faltantes():
        return "error", 503
    try:
        with cursor() as cur:
            cur.execute("SELECT 1")
        return "ok", 200
    except psycopg2.Error:
        return "error", 503


@app.get("/api/items")
def listar():
    with cursor() as cur:
        cur.execute("SELECT id, nombre, descripcion, creado FROM items ORDER BY id DESC")
        return jsonify(cur.fetchall())


@app.get("/api/items/<int:item_id>")
def obtener(item_id):
    with cursor() as cur:
        cur.execute("SELECT id, nombre, descripcion, creado FROM items WHERE id = %s", (item_id,))
        fila = cur.fetchone()
    return jsonify(fila) if fila else no_encontrado()


@app.post("/api/items")
def crear():
    valores, error = validar(request.get_json(silent=True))
    if error:
        return jsonify(error=error), 400
    with cursor() as cur:
        cur.execute(
            "INSERT INTO items (nombre, descripcion) VALUES (%s, %s) RETURNING id, nombre, descripcion, creado",
            valores,
        )
        return jsonify(cur.fetchone()), 201


@app.put("/api/items/<int:item_id>")
def actualizar(item_id):
    valores, error = validar(request.get_json(silent=True))
    if error:
        return jsonify(error=error), 400
    with cursor() as cur:
        cur.execute(
            "UPDATE items SET nombre = %s, descripcion = %s WHERE id = %s RETURNING id, nombre, descripcion, creado",
            (*valores, item_id),
        )
        fila = cur.fetchone()
    return jsonify(fila) if fila else no_encontrado()


@app.delete("/api/items/<int:item_id>")
def eliminar(item_id):
    with cursor() as cur:
        cur.execute("DELETE FROM items WHERE id = %s", (item_id,))
        borrado = cur.rowcount
    return ("", 204) if borrado else no_encontrado()


PAGINA = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="Flask">
<title>Items Python</title>
<style>
body{font-family:sans-serif;max-width:720px;margin:2rem auto;padding:0 1rem}
.aviso{background:#fee;border:1px solid #c00;padding:.6rem}
.msg{background:#eef;padding:.6rem}
li{margin:.3rem 0}
</style></head><body>
<h1>Items <small>(__VERSION__)</small></h1>
<p class="msg">Mensaje: __MENSAJE__</p>
__AVISO__
<form id="f">
<input name="nombre" maxlength="100" required placeholder="Nombre">
<input name="descripcion" placeholder="Descripción">
<button>Crear</button>
</form>
<p id="err" class="aviso" hidden></p>
<ul id="lista"></ul>
<script>
const lista = document.getElementById('lista'), err = document.getElementById('err');
function mostrarError(t) { err.textContent = t; err.hidden = !t; }
async function cargar() {
  const r = await fetch('/api/items');
  if (!r.ok) return mostrarError('No se pudieron cargar los items');
  lista.replaceChildren(...(await r.json()).map(it => {
    const li = document.createElement('li'), b = document.createElement('button');
    li.textContent = it.nombre + (it.descripcion ? ' — ' + it.descripcion : '') + ' ';
    b.textContent = 'Eliminar';
    b.onclick = async () => { await fetch('/api/items/' + it.id, {method: 'DELETE'}); cargar(); };
    li.append(b);
    return li;
  }));
}
document.getElementById('f').onsubmit = async e => {
  e.preventDefault();
  const r = await fetch('/api/items', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(Object.fromEntries(new FormData(e.target)))});
  if (!r.ok) return mostrarError((await r.json()).error || 'Error');
  mostrarError(''); e.target.reset(); cargar();
};
cargar();
</script></body></html>"""


@app.get("/")
def index():
    f = faltantes()
    aviso = f'<p class="aviso">Faltan variables de entorno: {html.escape(", ".join(f))}</p>' if f else ""
    return (
        PAGINA.replace("__VERSION__", html.escape(VERSION))
        .replace("__MENSAJE__", html.escape(os.environ.get("APP_MESSAGE", "(APP_MESSAGE no definido)")))
        .replace("__AVISO__", aviso)
    )


init_db()
