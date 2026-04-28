import { API_BASE_URL } from '@/lib/api';

export type Suggestion = {
  value: string;
  frequency: number;
  display_name?: string | null;
};

type SuggestionsResponse = {
  suggestions: Suggestion[];
};

/**
 * Fetch typeahead suggestions for role or domain pills.
 * Throws on non-2xx. Pass an AbortSignal to cancel in-flight requests
 * when the user types faster than the debounce window.
 */
export async function fetchSuggestions(
  type: 'role' | 'domain',
  query: string,
  token: string | null,
  signal?: AbortSignal
): Promise<Suggestion[]> {
  const params = new URLSearchParams({ type, q: query, limit: '20' });
  const response = await fetch(
    `${API_BASE_URL}/api/users/preferences/suggestions?${params.toString()}`,
    {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      signal,
    }
  );
  if (!response.ok) {
    throw new Error(`Suggestions request failed: ${response.status}`);
  }
  const data = (await response.json()) as SuggestionsResponse;
  return data.suggestions;
}

/**
 * Fetch all canonical domain entries (slug → display_name) in one shot.
 * Uses the suggestions endpoint with limit=50 and empty query to get all entries.
 * Returns a map from slug to human-readable display name.
 * Falls back gracefully — if the fetch fails, returns an empty map.
 */
export async function fetchDomainDisplayMap(
  token: string | null
): Promise<Record<string, string>> {
  try {
    const params = new URLSearchParams({ type: 'domain', q: '', limit: '50' });
    const response = await fetch(
      `${API_BASE_URL}/api/users/preferences/suggestions?${params.toString()}`,
      {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      }
    );
    if (!response.ok) return {};
    const data = (await response.json()) as SuggestionsResponse;
    const map: Record<string, string> = {};
    for (const item of data.suggestions) {
      map[item.value] = item.display_name || item.value;
    }
    return map;
  } catch {
    return {};
  }
}
