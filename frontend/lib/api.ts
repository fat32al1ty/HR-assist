export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  (typeof window !== 'undefined'
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : 'http://localhost:8000');

export const RESUME_LIMIT = 2;

export type ApiErrorShape =
  | string
  | { detail?: unknown; error?: string; message?: string }
  | Array<{ loc?: unknown; msg?: string; type?: string }>;

/**
 * Maps any shape FastAPI or our app might return into a human-readable string.
 */
export function extractErrorMessage(payload: unknown, fallback?: string): string {
  const defaultMsg = fallback ?? 'Запрос не выполнен';

  if (payload === null || payload === undefined) {
    return defaultMsg;
  }

  if (typeof payload === 'string') {
    return payload;
  }

  if (Array.isArray(payload)) {
    // Top-level array of validation objects — not a common FastAPI shape but handle it.
    const msgs = payload
      .filter((item): item is { loc?: unknown; msg?: string } => typeof item === 'object' && item !== null)
      .map((item) => {
        const locPart = formatLoc(item.loc);
        return locPart ? `${locPart}: ${item.msg ?? ''}` : (item.msg ?? '');
      })
      .filter(Boolean);
    return msgs.length > 0 ? msgs.join('; ') : defaultMsg;
  }

  if (typeof payload === 'object') {
    const obj = payload as Record<string, unknown>;

    // { detail: ... }
    if ('detail' in obj) {
      const detail = obj.detail;

      if (typeof detail === 'string') {
        return detail;
      }

      if (Array.isArray(detail)) {
        // FastAPI 422: [{loc, msg, type}, ...]
        const msgs = detail
          .filter((item): item is { loc?: unknown; msg?: string } => typeof item === 'object' && item !== null)
          .map((item) => {
            const locPart = formatLoc(item.loc);
            return locPart ? `${locPart}: ${item.msg ?? ''}` : (item.msg ?? '');
          })
          .filter(Boolean);
        return msgs.length > 0 ? msgs.join('; ') : defaultMsg;
      }

      if (detail !== null && typeof detail === 'object') {
        const detailObj = detail as Record<string, unknown>;
        if (detailObj.error === 'resume_limit_exceeded') {
          const limit = typeof detailObj.limit === 'number' ? detailObj.limit : RESUME_LIMIT;
          return `Достигнут лимит ${limit} профилей. Удалите один, чтобы загрузить новый.`;
        }
        const msg =
          typeof detailObj.message === 'string'
            ? detailObj.message
            : typeof detailObj.error === 'string'
              ? detailObj.error
              : null;
        return msg ?? defaultMsg;
      }

      return defaultMsg;
    }

    // { error, message } top-level
    if ('error' in obj || 'message' in obj) {
      const msg =
        typeof obj.message === 'string'
          ? obj.message
          : typeof obj.error === 'string'
            ? obj.error
            : null;
      return msg ?? defaultMsg;
    }

    return defaultMsg;
  }

  return defaultMsg;
}

function formatLoc(loc: unknown): string {
  if (!Array.isArray(loc)) return '';
  // Strip leading "body" segment
  const parts = loc.filter((p) => p !== 'body').map(String);
  return parts.join('.');
}

/**
 * Typed fetch wrapper. Prepends API_BASE_URL, injects auth header,
 * and throws a human-readable Error on non-ok responses.
 */
export async function apiFetch<T = unknown>(
  path: string,
  init?: RequestInit & { token?: string | null; fallbackError?: string }
): Promise<T> {
  const { token, fallbackError, ...fetchInit } = init ?? {};

  const headers: Record<string, string> = {};

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // Add Content-Type for JSON bodies (not FormData)
  if (fetchInit.body !== undefined && !(fetchInit.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  // Merge caller headers on top
  const callerHeaders = fetchInit.headers
    ? (fetchInit.headers as Record<string, string>)
    : {};

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...fetchInit,
    headers: { ...headers, ...callerHeaders }
  });

  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => ({}));
    const message = extractErrorMessage(payload, fallbackError);
    throw new Error(message);
  }

  if (response.status === 204) {
    return null as T;
  }

  return response.json() as Promise<T>;
}
