import { useEffect, useState } from "react";
import MetricCard from "../components/MetricCard";
import { fetchConfig, fetchMetrics, updateConfig } from "../services/metricsApi";

const POLL_INTERVAL_MS = 3000;

export default function Dashboard() {
  const [metrics, setMetrics] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [config, setConfig] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let isMounted = true;

    const loadMetrics = async () => {
      try {
        const data = await fetchMetrics();
        if (isMounted) {
          setMetrics(data);
          setError("");
        }
      } catch (err) {
        if (isMounted) {
          setError("No se pudo cargar metrics. Revisa el backend.");
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    const loadConfig = async () => {
      try {
        const data = await fetchConfig();
        if (isMounted) {
          setConfig({
            desired_workers: data.desired_workers,
            producer_interval: data.producer_interval,
            min_process_time: data.min_process_time,
            max_process_time: data.max_process_time
          });
        }
      } catch (err) {
        if (isMounted) {
          setError("No se pudo cargar configuracion.");
        }
      }
    };

    loadMetrics();
    loadConfig();
    const interval = setInterval(loadMetrics, POLL_INTERVAL_MS);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setConfig((prev) => ({
      ...prev,
      [name]: value === "" ? "" : Number(value)
    }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!config) {
      return;
    }
    setSaving(true);
    try {
      const updated = await updateConfig({
        desired_workers: config.desired_workers,
        producer_interval: config.producer_interval,
        min_process_time: config.min_process_time,
        max_process_time: config.max_process_time
      });
      setConfig(updated);
      setError("");
    } catch (err) {
      setError("No se pudo guardar la configuracion.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="page">
      <header className="hero">
        <div>
          <p className="eyebrow">Admin Dashboard</p>
          <h1>Concurrencia en tiempo real</h1>
          <p className="subtitle">
            Monitoreo simple de workers, cola y tiempos de proceso.
          </p>
        </div>
        <div className="status">
          <span className="pulse" />
          <span>Live</span>
        </div>
      </header>

      {loading && <p className="hint">Cargando metricas...</p>}
      {error && <p className="error">{error}</p>}

      <section className="grid">
        <MetricCard
          label="Workers activos"
          value={metrics ? metrics.active_workers : "-"}
          hint="Threads en ejecucion"
        />
        <MetricCard
          label="Cola"
          value={metrics ? metrics.queue_size : "-"}
          hint="Tareas pendientes"
        />
        <MetricCard
          label="Trabajos por minuto"
          value={metrics ? metrics.jobs_per_minute : "-"}
          hint="Ventana de 60s"
        />
        <MetricCard
          label="Tiempo promedio"
          value={metrics ? `${metrics.average_processing_time}s` : "-"}
          hint="Promedio de proceso"
        />
      </section>

      <section className="panel">
        <div>
          <h2>Ajustes interactivos</h2>
          <p className="panel-hint">
            Modifica la cantidad de workers y la velocidad de tareas.
          </p>
        </div>
        <form className="form" onSubmit={handleSubmit}>
          <label className="field">
            <span>Workers deseados</span>
            <input
              type="number"
              name="desired_workers"
              min="1"
              max="12"
              step="1"
              value={config?.desired_workers ?? ""}
              onChange={handleChange}
            />
          </label>
          <label className="field">
            <span>Intervalo productor (s)</span>
            <input
              type="number"
              name="producer_interval"
              min="0.1"
              max="3"
              step="0.1"
              value={config?.producer_interval ?? ""}
              onChange={handleChange}
            />
          </label>
          <label className="field">
            <span>Tiempo minimo (s)</span>
            <input
              type="number"
              name="min_process_time"
              min="0.1"
              max="5"
              step="0.1"
              value={config?.min_process_time ?? ""}
              onChange={handleChange}
            />
          </label>
          <label className="field">
            <span>Tiempo maximo (s)</span>
            <input
              type="number"
              name="max_process_time"
              min="0.1"
              max="6"
              step="0.1"
              value={config?.max_process_time ?? ""}
              onChange={handleChange}
            />
          </label>
          <button className="button" type="submit" disabled={saving || !config}>
            {saving ? "Guardando..." : "Aplicar cambios"}
          </button>
        </form>
      </section>
    </div>
  );
}
