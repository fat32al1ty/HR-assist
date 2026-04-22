/**
 * Client-side telemetry for match impressions / clicks / dwell (Phase 2.6).
 *
 * Impressions are persisted server-side — this module only emits clicks
 * and dwell. Fire-and-forget fetch; a network failure here must never
 * surface to the user. Dedupe is per-mount, keyed by
 * `${run_id}::${vacancy_id}::${kind}`.
 */

type ClickKind = 'open_card' | 'open_source' | 'apply' | 'like' | 'dislike';

type ClickPayload = {
  vacancy_id: number;
  click_kind: ClickKind;
  match_run_id?: string | null;
  resume_id?: number | null;
  position?: number | null;
};

type DwellPayload = {
  match_run_id: string;
  rows: { vacancy_id: number; ms: number }[];
};

const clickDedupe = new Set<string>();

async function postJson(url: string, body: unknown): Promise<void> {
  try {
    await fetch(url, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      keepalive: true,
    });
  } catch {
    // Swallow — telemetry must never break the UI.
  }
}

export function trackClick(payload: ClickPayload): void {
  const key = `${payload.match_run_id ?? 'no-run'}::${payload.vacancy_id}::${payload.click_kind}`;
  if (clickDedupe.has(key)) {
    return;
  }
  clickDedupe.add(key);
  void postJson('/api/telemetry/click', payload);
}

export function flushDwell(payload: DwellPayload): void {
  if (!payload.match_run_id || payload.rows.length === 0) {
    return;
  }
  void postJson('/api/telemetry/dwell', payload);
}

/**
 * Observe viewport dwell-time for a set of match cards.
 *
 * Returns a disposer that flushes any unsent ms on teardown. The
 * observer itself emits a batched flush whenever the accumulated dwell
 * is meaningful (≥ 1s) per card or when the tab loses visibility.
 */
export function createDwellTracker(opts: {
  getRunId: () => string | null;
  flushThresholdMs?: number;
}): {
  observe: (vacancyId: number, el: Element) => void;
  unobserve: (vacancyId: number) => void;
  dispose: () => void;
} {
  const threshold = opts.flushThresholdMs ?? 1000;
  const accum = new Map<number, number>();
  const visibleSince = new Map<number, number>();
  const nodes = new Map<number, Element>();

  const flush = () => {
    const runId = opts.getRunId();
    if (!runId) {
      accum.clear();
      return;
    }
    const now = Date.now();
    for (const [vacId, since] of visibleSince.entries()) {
      accum.set(vacId, (accum.get(vacId) ?? 0) + (now - since));
      visibleSince.set(vacId, now);
    }
    const rows = [...accum.entries()]
      .filter(([, ms]) => ms >= threshold)
      .map(([vacancy_id, ms]) => ({ vacancy_id, ms }));
    if (rows.length === 0) {
      return;
    }
    flushDwell({ match_run_id: runId, rows });
    for (const row of rows) {
      accum.delete(row.vacancy_id);
    }
  };

  const io = new IntersectionObserver((entries) => {
    const now = Date.now();
    for (const entry of entries) {
      const vacIdAttr = entry.target.getAttribute('data-vacancy-id');
      if (!vacIdAttr) continue;
      const vacId = Number(vacIdAttr);
      if (!Number.isFinite(vacId)) continue;
      if (entry.isIntersecting) {
        visibleSince.set(vacId, now);
      } else {
        const since = visibleSince.get(vacId);
        if (since !== undefined) {
          accum.set(vacId, (accum.get(vacId) ?? 0) + (now - since));
          visibleSince.delete(vacId);
        }
      }
    }
  }, { threshold: 0.4 });

  const onVisibility = () => {
    if (document.visibilityState === 'hidden') {
      flush();
    }
  };
  document.addEventListener('visibilitychange', onVisibility);
  window.addEventListener('beforeunload', flush);

  const periodic = window.setInterval(flush, 15_000);

  return {
    observe(vacancyId, el) {
      nodes.set(vacancyId, el);
      io.observe(el);
    },
    unobserve(vacancyId) {
      const el = nodes.get(vacancyId);
      if (el) io.unobserve(el);
      nodes.delete(vacancyId);
    },
    dispose() {
      flush();
      io.disconnect();
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('beforeunload', flush);
      window.clearInterval(periodic);
    },
  };
}

export function resetTelemetryDedupe(): void {
  clickDedupe.clear();
}
