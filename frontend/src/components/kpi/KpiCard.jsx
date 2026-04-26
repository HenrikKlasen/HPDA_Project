function KpiCard({ title, value }) {
  return (
    <article className="card">
      <p className="kpi-title">{title}</p>
      <p className="kpi-value">{value}</p>
    </article>
  );
}

export default KpiCard;
