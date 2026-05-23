export default function MetricCard({ label, value, hint }) {
  return (
    <article className="card">
      <div className="card-top">
        <p className="card-label">{label}</p>
        <span className="card-value">{value}</span>
      </div>
      <p className="card-hint">{hint}</p>
    </article>
  );
}
