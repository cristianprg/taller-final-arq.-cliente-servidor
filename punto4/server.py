"""
Historia #4 — Demo ejecutable (sin dependencias externas)
=========================================================
Backend HTTP puro con sqlite3 + http.server de la stdlib.
Expone los 3 endpoints de la Historia #4 más CORS para el frontend.

Endpoints:
  GET /api/jobs                         → lista todos los jobs
  GET /api/jobs/{job_id}                → estado y progreso
  GET /api/jobs/{job_id}/results        → resultados paginados (?page=1&per_page=10&sentiment=)
  GET /api/jobs/{job_id}/report         → reporte agregado (con caché)
  POST /api/seed                        → regenera datos de ejemplo

Ejecutar: python3 server.py
Luego abrir: frontend.html en el navegador
"""

import http.server
import json
import math
import random
import re
import sqlite3
import threading
import time
import uuid
from typing import Optional
from urllib.parse import urlparse, parse_qs


# ══════════════════════════════════════════════════════════════
# 1. BASE DE DATOS (SQLite en memoria — no requiere instalación)
# ══════════════════════════════════════════════════════════════

DB_PATH = ":memory:"   # cambiar a "jobs.db" para persistencia

# Conexión única compartida + Lock (SQLite en memoria no soporta múltiples conns)
_db_conn: Optional[sqlite3.Connection] = None
_db_lock = threading.Lock()


def get_db() -> sqlite3.Connection:
    global _db_conn
    if _db_conn is None:
        _db_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _db_conn.row_factory = sqlite3.Row
        _init_db(_db_conn)
    return _db_conn


def _init_db(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id              TEXT PRIMARY KEY,
            user_id         TEXT NOT NULL,
            status          TEXT NOT NULL,
            total_texts     INTEGER NOT NULL DEFAULT 0,
            processed_texts INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL,
            error_message   TEXT
        );
        CREATE INDEX IF NOT EXISTS ix_jobs_user   ON jobs(user_id);
        CREATE INDEX IF NOT EXISTS ix_jobs_status ON jobs(status);

        CREATE TABLE IF NOT EXISTS text_results (
            id            TEXT PRIMARY KEY,
            job_id        TEXT NOT NULL REFERENCES jobs(id),
            original_text TEXT NOT NULL,
            sentiment     TEXT NOT NULL,
            score         REAL NOT NULL,
            processed_at  TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_results_job       ON text_results(job_id);
        CREATE INDEX IF NOT EXISTS ix_results_sentiment ON text_results(sentiment);
        CREATE INDEX IF NOT EXISTS ix_results_job_sent  ON text_results(job_id, sentiment);
    """)
    conn.commit()


# ══════════════════════════════════════════════════════════════
# 2. SEED — datos de ejemplo realistas
# ══════════════════════════════════════════════════════════════

POSITIVE_TEXTS = [
    "El producto superó todas mis expectativas, definitivamente lo recomendaría.",
    "Excelente atención al cliente, resolvieron mi problema en minutos.",
    "La calidad es increíble para el precio que tiene.",
    "Muy satisfecho con la compra, llegó antes de lo esperado.",
    "El diseño es elegante y la funcionalidad es perfecta.",
    "Mejor de lo que esperaba, volvería a comprar sin duda.",
    "El servicio fue excepcional, muy profesional y eficiente.",
    "Me encantó la experiencia, todo fue muy fácil e intuitivo.",
    "Producto de alta calidad, se nota la diferencia con la competencia.",
    "La app funciona perfectamente, sin errores ni lentitud.",
]

NEGATIVE_TEXTS = [
    "Muy decepcionado, el producto llegó dañado y tardó el doble.",
    "Pésima atención al cliente, nadie respondió mis mensajes.",
    "La calidad es mucho peor de lo que mostraban en las fotos.",
    "El producto dejó de funcionar a la semana de usarlo.",
    "No cumple con lo prometido en la descripción.",
    "El servicio es lento y el personal no sabe nada del producto.",
    "Tuve que devolver el producto tres veces, inaceptable.",
    "La app se cae constantemente y pierde mis datos.",
    "Precio muy alto para la calidad que ofrece.",
    "Nunca más compro aquí, fue una experiencia horrible.",
]

NEUTRAL_TEXTS = [
    "El producto cumple su función básica, nada especial.",
    "Es lo que esperaba, ni más ni menos.",
    "La entrega fue puntual, el producto es estándar.",
    "Funciona bien para uso ocasional, no para uso intensivo.",
    "El precio es acorde a la calidad que ofrece.",
    "Podría mejorar en algunos aspectos pero en general está bien.",
    "El servicio fue correcto, sin problemas pero sin destacar.",
    "Lo usaré por ahora, ya veremos con el tiempo.",
    "Cumple las especificaciones técnicas descritas.",
    "Producto promedio del mercado, sin ventajas ni desventajas.",
]


def _random_ts(days_ago_max=7) -> str:
    offset = random.uniform(0, days_ago_max * 86400)
    t = time.time() - offset
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t))


def seed_database():
    """Limpia e inserta datos de ejemplo en la BD."""
    conn = get_db()
    with _db_lock:
        conn.execute("DELETE FROM text_results")
        conn.execute("DELETE FROM jobs")
        conn.commit()

    statuses = [
        ("completed", 50, 50),
        ("completed", 30, 30),
        ("processing", 40, 23),
        ("pending",   20,  0),
        ("failed",    15,  8),
        ("completed", 60, 60),
    ]

    jobs_data = []
    for status, total, processed in statuses:
        job_id = str(uuid.uuid4())
        created = _random_ts(7)
        updated = _random_ts(1)
        jobs_data.append({
            "id": job_id, "user_id": "user-demo-001",
            "status": status, "total_texts": total,
            "processed_texts": processed,
            "created_at": created, "updated_at": updated,
            "error_message": "Timeout al conectar con el modelo NLP" if status == "failed" else None,
        })

    with _db_lock:
        for j in jobs_data:
            conn.execute(
                "INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?)",
                (j["id"], j["user_id"], j["status"], j["total_texts"],
                 j["processed_texts"], j["created_at"], j["updated_at"], j["error_message"])
            )

        # Insertar text_results para jobs completados y en processing
        for j in jobs_data:
            if j["status"] in ("completed", "processing", "failed"):
                count = j["processed_texts"]
                for _ in range(count):
                    r = random.random()
                    if r < 0.55:
                        sentiment = "positive"
                        score = random.uniform(0.2, 1.0)
                        text = random.choice(POSITIVE_TEXTS)
                    elif r < 0.80:
                        sentiment = "negative"
                        score = random.uniform(-1.0, -0.1)
                        text = random.choice(NEGATIVE_TEXTS)
                    else:
                        sentiment = "neutral"
                        score = random.uniform(-0.15, 0.15)
                        text = random.choice(NEUTRAL_TEXTS)

                    conn.execute(
                        "INSERT INTO text_results VALUES (?,?,?,?,?,?)",
                        (str(uuid.uuid4()), j["id"], text, sentiment,
                         round(score, 4), _random_ts(1))
                    )
        conn.commit()

    return [j["id"] for j in jobs_data]


# ══════════════════════════════════════════════════════════════
# 3. CAPA DE APLICACIÓN (simplificada, misma lógica)
# ══════════════════════════════════════════════════════════════

# Caché thread-safe para reportes (solo jobs completados)
_report_cache: dict = {}
_cache_lock = threading.Lock()


def get_job_status(job_id: str) -> Optional[dict]:
    conn = get_db()
    with _db_lock:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    total = d["total_texts"] or 1
    d["progress_percentage"] = round((d["processed_texts"] / total) * 100, 2)
    return d


def get_all_jobs() -> list[dict]:
    conn = get_db()
    with _db_lock:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE user_id='user-demo-001' ORDER BY created_at DESC"
        ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        total = d["total_texts"] or 1
        d["progress_percentage"] = round((d["processed_texts"] / total) * 100, 2)
        result.append(d)
    return result


def get_paginated_results(job_id: str, page: int, per_page: int,
                          sentiment: Optional[str]) -> Optional[dict]:
    if not get_job_status(job_id):
        return None
    conn = get_db()
    offset = (page - 1) * per_page

    base_q = "FROM text_results WHERE job_id=?"
    params = [job_id]
    if sentiment:
        base_q += " AND sentiment=?"
        params.append(sentiment)

    with _db_lock:
        total = conn.execute(f"SELECT COUNT(*) {base_q}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * {base_q} ORDER BY processed_at LIMIT ? OFFSET ?",
            params + [per_page, offset]
        ).fetchall()

    total_pages = math.ceil(total / per_page) if per_page else 0
    return {
        "job_id": job_id,
        "items": [dict(r) for r in rows],
        "page": page, "per_page": per_page,
        "total_items": total, "total_pages": total_pages,
        "has_next": page < total_pages, "has_prev": page > 1,
    }


def get_aggregated_report(job_id: str) -> Optional[dict]:
    job = get_job_status(job_id)
    if not job:
        return None
    if job["status"] != "completed":
        return {"error": f"Job en estado '{job['status']}'. Reporte solo disponible cuando está completed.", "status": job["status"]}

    # Caché — solo para jobs completed (reportes inmutables, regla DDD)
    with _cache_lock:
        if job_id in _report_cache:
            cached = dict(_report_cache[job_id])
            cached["cached"] = True
            return cached

    conn = get_db()
    with _db_lock:
        row = conn.execute("""
            SELECT
                COUNT(*)                                    AS total,
                SUM(CASE WHEN sentiment='positive' THEN 1 ELSE 0 END) AS positive,
                SUM(CASE WHEN sentiment='negative' THEN 1 ELSE 0 END) AS negative,
                SUM(CASE WHEN sentiment='neutral'  THEN 1 ELSE 0 END) AS neutral,
                AVG(score)                                  AS avg_score
            FROM text_results WHERE job_id=?
        """, (job_id,)).fetchone()

    total = row["total"] or 0
    pos   = row["positive"] or 0
    neg   = row["negative"] or 0
    neu   = row["neutral"]  or 0
    avg   = round(row["avg_score"] or 0.0, 4)

    report = {
        "job_id": job_id,
        "positive_count": pos, "negative_count": neg, "neutral_count": neu,
        "total_analyzed": total, "average_score": avg,
        "positive_percentage": round(pos / total * 100, 2) if total else 0,
        "negative_percentage": round(neg / total * 100, 2) if total else 0,
        "neutral_percentage":  round(neu / total * 100, 2) if total else 0,
        "cached": False,
    }

    with _cache_lock:
        _report_cache[job_id] = report

    return report


# ══════════════════════════════════════════════════════════════
# 4. HTTP SERVER
# ══════════════════════════════════════════════════════════════

def json_response(handler, status: int, data):
    body = json.dumps(data, ensure_ascii=False, default=str).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.end_headers()
    handler.wfile.write(body)


class LMSHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"  [HTTP] {self.address_string()} {fmt % args}")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path.rstrip("/")
        qs     = parse_qs(parsed.query)

        def qp(key, default=None):
            vals = qs.get(key, [])
            return vals[0] if vals else default

        # ── GET /api/jobs ──────────────────────────────
        if path == "/api/jobs":
            json_response(self, 200, get_all_jobs())
            return

        # ── GET /api/jobs/{id} ─────────────────────────
        m = re.fullmatch(r"/api/jobs/([^/]+)", path)
        if m:
            job = get_job_status(m.group(1))
            if job is None:
                json_response(self, 404, {"detail": "Job no encontrado"})
            else:
                json_response(self, 200, job)
            return

        # ── GET /api/jobs/{id}/results ─────────────────
        m = re.fullmatch(r"/api/jobs/([^/]+)/results", path)
        if m:
            job_id    = m.group(1)
            page      = int(qp("page", "1"))
            per_page  = int(qp("per_page", "10"))
            sentiment = qp("sentiment")
            data = get_paginated_results(job_id, page, per_page, sentiment)
            if data is None:
                json_response(self, 404, {"detail": "Job no encontrado"})
            else:
                json_response(self, 200, data)
            return

        # ── GET /api/jobs/{id}/report ──────────────────
        m = re.fullmatch(r"/api/jobs/([^/]+)/report", path)
        if m:
            data = get_aggregated_report(m.group(1))
            if data is None:
                json_response(self, 404, {"detail": "Job no encontrado"})
            elif "error" in data:
                json_response(self, 409, data)
            else:
                json_response(self, 200, data)
            return

        json_response(self, 404, {"detail": "Ruta no encontrada"})

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path.rstrip("/") == "/api/seed":
            job_ids = seed_database()
            json_response(self, 200, {
                "message": "Datos regenerados exitosamente",
                "jobs_created": len(job_ids),
                "job_ids": job_ids,
            })
        else:
            json_response(self, 404, {"detail": "Ruta no encontrada"})


def run_server(host="0.0.0.0", port=8000):
    # Inicializar BD y seed al arrancar
    print("  Inicializando base de datos...")
    seed_database()
    print(f"  Datos de ejemplo cargados.")
    print()
    print(f"  ✓ Servidor corriendo en http://localhost:{port}")
    print(f"  ✓ Abre frontend.html en tu navegador")
    print(f"  Ctrl+C para detener\n")

    server = http.server.ThreadingHTTPServer((host, port), LMSHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Servidor detenido.")
        server.server_close()


if __name__ == "__main__":
    run_server()
