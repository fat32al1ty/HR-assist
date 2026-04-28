import { API_BASE_URL } from '@/lib/api';

export type Suggestion = {
  value: string;
  frequency: number;
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
