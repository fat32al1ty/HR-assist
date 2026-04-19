export type VacancyLike = {
  vacancy_id: number | string;
};

export type VacancyMatchLike = VacancyLike & {
  source_url?: string | null;
  title?: string | null;
};

export function normalizeVacancyId(value: number | string): number {
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : 0;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function removeVacancyFromList<T extends VacancyLike>(list: T[], vacancyId: number | string): T[] {
  const target = normalizeVacancyId(vacancyId);
  return list.filter((item) => normalizeVacancyId(item.vacancy_id) !== target);
}

export function removeVacancyMatchEntry<T extends VacancyMatchLike>(list: T[], target: VacancyMatchLike): T[] {
  const targetId = normalizeVacancyId(target.vacancy_id);
  return list.filter((item) => {
    const itemId = normalizeVacancyId(item.vacancy_id);
    if (targetId > 0 && itemId === targetId) {
      return false;
    }
    if (targetId <= 0 && item.source_url === target.source_url && item.title === target.title) {
      return false;
    }
    return true;
  });
}

export function excludeFeedbackVacancies<T extends VacancyLike>(
  list: T[],
  disliked: VacancyLike[],
  selected: VacancyLike[],
  hiddenIds: number[] = []
): T[] {
  if (list.length === 0) {
    return list;
  }
  const excludedIds = new Set<number>([
    ...disliked.map((item) => normalizeVacancyId(item.vacancy_id)),
    ...selected.map((item) => normalizeVacancyId(item.vacancy_id)),
    ...hiddenIds.map((item) => normalizeVacancyId(item))
  ]);
  if (excludedIds.size === 0) {
    return list;
  }
  return list.filter((item) => !excludedIds.has(normalizeVacancyId(item.vacancy_id)));
}
