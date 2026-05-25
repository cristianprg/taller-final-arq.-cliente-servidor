# Historia #4 — Consulta de Resultados y Generación de Reportes

Sistema de análisis de sentimientos con **Clean Architecture**, endpoints REST y caché thread-safe. Esta demo es completamente ejecutable sin instalar dependencias externas.

---

## Archivos

```
historia4-demo/
├── server.py        ← Backend (Python stdlib pura: http.server + sqlite3)
├── frontend.html    ← Frontend (HTML + CSS + JS vanilla)
└── README.md
```

---

## Requisitos

- Python 3.8 o superior
- Navegador web moderno (Chrome, Firefox, Edge, Safari)
- Sin instalación de paquetes externos

---

## Cómo ejecutar

### 1. Iniciar el backend

```bash
python3 server.py
```

Verás en la terminal:

```
  Inicializando base de datos...
  Datos de ejemplo cargados.

  ✓ Servidor corriendo en http://localhost:8000
  ✓ Abre frontend.html en tu navegador
  Ctrl+C para detener
```

### 2. Abrir el frontend

Abre el archivo `frontend.html` directamente en tu navegador (doble clic). No requiere servidor web adicional.

> **Importante:** el backend debe estar corriendo antes de abrir el frontend.

---

## Qué se puede ver

Al abrir el frontend encontrarás tres secciones por cada job:

### Panel izquierdo — Lista de Jobs
Muestra los 6 jobs de ejemplo con un indicador de color según su estado:

| Color | Estado |
|-------|--------|
| 🟢 Verde | `completed` |
| 🔵 Azul (parpadeante) | `processing` |
| ⚪ Gris | `pending` |
| 🔴 Rojo | `failed` |

### Tarjeta 1 — Estado del Job
Consume `GET /jobs/{job_id}`. Muestra:
- Estado actual con badge de color
- Total de textos vs. textos procesados
- Barra de progreso con porcentaje
- Mensaje de error si el job falló

### Tarjeta 2 — Reporte Agregado
Consume `GET /jobs/{job_id}/report`. Muestra:
- Donut chart con distribución de sentimientos
- Barras de porcentaje para positivos, negativos y neutrales
- Score promedio en rango `[-1.0, 1.0]`
- Badge `⚡ caché` cuando el reporte se sirve desde caché (segunda consulta en adelante)
- Mensaje de advertencia si el job aún no está `completed`

### Tarjeta 3 — Resultados Paginados
Consume `GET /jobs/{job_id}/results`. Muestra:
- Tabla con texto original, sentimiento, score y fecha
- Filtros por sentimiento (Todos / Positivos / Negativos / Neutrales)
- Paginación con 8 resultados por página
- Contador total de resultados y páginas

---

## Endpoints de la API

El servidor expone los siguientes endpoints en `http://localhost:8000`:

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/jobs` | Lista todos los jobs del usuario demo |
| `GET` | `/api/jobs/{job_id}` | Estado y progreso de un job específico |
| `GET` | `/api/jobs/{job_id}/results` | Resultados paginados con filtro opcional |
| `GET` | `/api/jobs/{job_id}/report` | Reporte agregado de sentimientos |
| `POST` | `/api/seed` | Regenera todos los datos de ejemplo |

### Parámetros de paginación

```
GET /api/jobs/{job_id}/results?page=1&per_page=10&sentiment=positive
```

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `page` | int | `1` | Número de página |
| `per_page` | int | `10` | Resultados por página |
| `sentiment` | string | *(vacío)* | Filtrar por `positive`, `negative` o `neutral` |

### Ejemplos de respuesta

**`GET /api/jobs/{job_id}`**
```json
{
  "id": "abc-123",
  "status": "processing",
  "total_texts": 40,
  "processed_texts": 23,
  "progress_percentage": 57.5,
  "created_at": "2025-06-01T10:00:00",
  "updated_at": "2025-06-01T10:03:12",
  "error_message": null
}
```

**`GET /api/jobs/{job_id}/report`**
```json
{
  "job_id": "abc-123",
  "positive_count": 32,
  "negative_count": 9,
  "neutral_count": 9,
  "total_analyzed": 50,
  "average_score": 0.2841,
  "positive_percentage": 64.0,
  "negative_percentage": 18.0,
  "neutral_percentage": 18.0,
  "cached": true
}
```

**`GET /api/jobs/{job_id}/results?page=1&per_page=3`**
```json
{
  "job_id": "abc-123",
  "items": [
    {
      "id": "res-001",
      "original_text": "El producto superó todas mis expectativas.",
      "sentiment": "positive",
      "score": 0.8712,
      "processed_at": "2025-06-01T10:01:05"
    }
  ],
  "page": 1,
  "per_page": 3,
  "total_items": 50,
  "total_pages": 17,
  "has_next": true,
  "has_prev": false
}
```

---

## Arquitectura del backend (`server.py`)

El archivo `server.py` implementa en un único módulo ejecutable todas las capas de la Historia #4:

```
server.py
│
├── Base de datos        SQLite en memoria con sqlite3 (stdlib)
│   └── Tablas: jobs, text_results con índices optimizados
│
├── Seed                 6 jobs de ejemplo con distintos estados
│   └── Textos realistas de análisis de opinión en español
│
├── Capa de aplicación   Lógica de los 3 casos de uso
│   ├── get_job_status()         → Caso de uso 1
│   ├── get_paginated_results()  → Caso de uso 2
│   └── get_aggregated_report()  → Caso de uso 3 + caché
│
└── HTTP Server          ThreadingHTTPServer con CORS habilitado
    └── LMSHandler       Enruta GET/POST a los casos de uso
```

### Caché thread-safe

El reporte agregado se cachea en memoria una vez calculado. Solo se cachean jobs con estado `completed` porque sus reportes son **inmutables** (regla de negocio DDD).

```python
_report_cache: dict = {}
_cache_lock = threading.Lock()
```

La segunda vez que consultas `/report` del mismo job, la respuesta incluye `"cached": true` y no se accede a la base de datos.

### Índices SQL creados

```sql
CREATE INDEX ix_jobs_user        ON jobs(user_id);
CREATE INDEX ix_jobs_status      ON jobs(status);
CREATE INDEX ix_results_job      ON text_results(job_id);
CREATE INDEX ix_results_sentiment ON text_results(sentiment);
CREATE INDEX ix_results_job_sent ON text_results(job_id, sentiment);
```

---

## Datos de ejemplo generados

Al arrancar el servidor se crean automáticamente 6 jobs:

| Estado | Textos totales | Textos procesados |
|--------|---------------|-------------------|
| `completed` | 50 | 50 |
| `completed` | 30 | 30 |
| `completed` | 60 | 60 |
| `processing` | 40 | 23 |
| `pending` | 20 | 0 |
| `failed` | 15 | 8 |

Cada job completado tiene sus `text_results` con sentimientos distribuidos aproximadamente en 55% positivos, 25% negativos y 20% neutrales.

Puedes regenerar los datos en cualquier momento con el botón **↺ Regenerar datos** del frontend o con:

```bash
curl -X POST http://localhost:8000/api/seed
```

---

## Relación con la arquitectura completa (Historia #4)

Esta demo es una versión **standalone** del backend de la Historia #4. En el proyecto completo, `server.py` corresponde a:

| `server.py` (demo) | Proyecto completo |
|---|---|
| `get_job_status()` | `JobQueryService.get_job_status()` |
| `get_paginated_results()` | `JobQueryService.get_paginated_results()` |
| `get_aggregated_report()` | `JobQueryService.get_aggregated_report()` |
| `LMSHandler` | `presentation/routers/jobs_router.py` (FastAPI) |
| `sqlite3` directo | `infrastructure/persistence/sql_repositories.py` (SQLAlchemy) |
| `_report_cache` + `_cache_lock` | `JobQueryService._report_cache` + `threading.Lock` |

Para usar el proyecto completo con FastAPI se requiere instalar las dependencias listadas en `requirements.txt` y ejecutar `main.py`.
