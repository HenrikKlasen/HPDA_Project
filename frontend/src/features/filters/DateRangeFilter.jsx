function DateRangeFilter({ value, onChange }) {
  return (
    <div className="filters">
      <label htmlFor="period">Period:</label>
      <select id="period" value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="7d">Last 7 days</option>
        <option value="30d">Last 30 days</option>
        <option value="90d">Last 90 days</option>
      </select>
    </div>
  );
}

export default DateRangeFilter;
