export function formatPercent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

export function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function shortHash(value: string) {
  return `${value.slice(0, 7)}…${value.slice(-5)}`;
}

export function formatDelta(before: number, after: number) {
  const delta = (after - before) * 100;
  const sign = delta > 0 ? "+" : "";
  return `${sign}${delta.toFixed(1)} pt`;
}

export function formatDuration(startedAt: string | null, finishedAt: string | null) {
  if (!startedAt) return "—";
  const end = finishedAt ? new Date(finishedAt).getTime() : Date.now();
  const seconds = (end - new Date(startedAt).getTime()) / 1000;
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
}

/** Sort any run record newest-first without mutating the source array. */
export function sortByCreatedAt<T extends { created_at: string }>(records: T[]) {
  return [...records].sort(
    (left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime(),
  );
}
