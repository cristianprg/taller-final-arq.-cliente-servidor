# Dashboard administrativo con metricas de concurrencia

## Introduccion
Este proyecto simula un sistema de procesamiento concurrente con multiples workers y un dashboard administrativo que muestra metricas en tiempo real. Es simple, didactico y pensado para explicar conceptos de concurrencia y patrones de diseno.

## Arquitectura
### Backend (FastAPI)
Capas:
- presentation/: endpoints y schemas HTTP.
- application/: servicios de orquestacion.
- domain/: reglas del dominio y metrics.
- infrastructure/: workers, cola y threading.

Responsabilidades:
- presentation recibe peticiones y expone metricas.
- application inicia y controla el pool de workers.
- domain define el modelo Task y el MetricsCollector.
- infrastructure ejecuta los threads y simula las tareas.

### Frontend (React + Vite)
Estructura:
- pages/: pantallas (Dashboard).
- components/: cards reutilizables.
- services/: llamadas al backend.
- styles/: CSS simple y responsivo.

## Patrones usados
- Singleton: MetricsCollector tiene una sola instancia compartida para almacenar metricas globales.
- Observer inverso: los workers notifican al MetricsCollector cuando inician y terminan una tarea.
- Snapshot: el endpoint toma una copia consistente de metricas con un lock.

## Concurrencia
- Se usan multiples threads y una cola thread-safe.
- Un lock protege el estado interno de MetricsCollector.
- El snapshot toma el lock para evitar lecturas corruptas.

## Flujo del sistema
1. El productor genera tareas dummy y las agrega a la cola.
2. Cada worker toma una tarea, notifica inicio, procesa con sleep y notifica fin.
3. MetricsCollector actualiza cola, workers activos, promedio y trabajos por minuto.
4. El dashboard consulta /admin/metrics cada pocos segundos.

## Explicacion del backend
Carpetas clave:
- backend/presentation/api.py: endpoint /admin/metrics con token simple.
- backend/application/services.py: arranque del WorkerPool.
- backend/domain/metrics.py: Singleton, locks y snapshot de metricas.
- backend/infrastructure/worker_pool.py: threads, cola y simulacion.

Detalles internos:
- MetricsCollector guarda queue_size, active_workers, completed_jobs y tiempos.
- jobs_per_minute se calcula con una lista de timestamps en una ventana de 60s.
- average_processing_time usa total_processing_time / completed_jobs.
- Todos los accesos al estado usan threading.Lock.

## Explicacion del frontend
- Dashboard hace polling cada 3 segundos.
- MetricCard muestra cada metrica en una card.
- metricsApi agrega el header Authorization con el token admin123.
- El panel de ajustes permite modificar workers y tiempos en vivo.

## Como ejecutar el proyecto
### 1) Backend
Desde la carpeta del proyecto:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 2) Frontend
En otra terminal:

```bash
cd frontend
npm install
npm run dev
```

### 3) Ver el dashboard
Abrir http://localhost:5173

## Endpoint administrativo
- URL: GET http://localhost:8000/admin/metrics
- Header: Authorization: Bearer admin123

Ejemplo de respuesta:
```json
{
  "queue_size": 4,
  "active_workers": 2,
  "jobs_per_minute": 15,
  "average_processing_time": 1.24
}
```

## Ajustes en vivo
El dashboard tiene un panel para modificar el comportamiento del sistema.

- GET http://localhost:8000/admin/config
- POST http://localhost:8000/admin/config

Ejemplo de payload:
```json
{
  "desired_workers": 2,
  "producer_interval": 0.3,
  "min_process_time": 1.0,
  "max_process_time": 2.0
}
```
