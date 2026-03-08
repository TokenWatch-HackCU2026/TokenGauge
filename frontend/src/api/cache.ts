const PREFIX = "tg_cache_";
const DEFAULT_TTL_MS = 5 * 60 * 1000; // 5 minutes

interface Entry<T> {
  data: T;
  savedAt: number;
}

export function saveCache<T>(key: string, data: T): void {
  try {
    localStorage.setItem(PREFIX + key, JSON.stringify({ data, savedAt: Date.now() } satisfies Entry<T>));
  } catch {}
}

export function loadCache<T>(key: string, maxAgeMs = DEFAULT_TTL_MS): T | undefined {
  try {
    const raw = localStorage.getItem(PREFIX + key);
    if (!raw) return undefined;
    const entry: Entry<T> = JSON.parse(raw);
    if (Date.now() - entry.savedAt > maxAgeMs) return undefined;
    return entry.data;
  } catch {
    return undefined;
  }
}
