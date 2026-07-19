/**
 * Display formatters shared across pages.
 *
 * Numeric formatters use IBM Plex Mono so columns of numbers align
 * visually — important for an operations tool where you scan tables.
 */

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || isNaN(seconds)) return "—";
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  if (m < 60) return `${m}m ${s.toString().padStart(2, "0")}s`;
  const h = Math.floor(m / 60);
  const mm = m % 60;
  return `${h}h ${mm.toString().padStart(2, "0")}m`;
}

export function formatTimestamp(d: Date | string | number | null | undefined): string {
  if (d === null || d === undefined) return "never";
  const date = new Date(d);
  if (isNaN(date.getTime())) return "—";
  return date.toLocaleString("en-GB", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function formatRelative(d: Date | string | number | null | undefined): string {
  if (d === null || d === undefined) return "never";
  const date = new Date(d);
  if (isNaN(date.getTime())) return "—";
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months}mo ago`;
  return `${Math.floor(months / 12)}y ago`;
}

export function shortId(id: string | null | undefined): string {
  if (!id) return "—";
  return id.length > 10 ? id.slice(-8) : id;
}

export function truncateUrl(url: string, max = 60): string {
  if (!url) return "—";
  if (url.length <= max) return url;
  return url.slice(0, max - 1) + "…";
}

export function isValidUrl(s: string): boolean {
  try {
    const u = new URL(s);
    return u.protocol === "http:" || u.protocol === "https:";
  } catch {
    return false;
  }
}
