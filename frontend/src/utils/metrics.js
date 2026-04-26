export function formatPercent(value) {
  return `${Number(value).toFixed(2)}%`;
}

export function formatDuration(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}m ${secs}s`;
}
