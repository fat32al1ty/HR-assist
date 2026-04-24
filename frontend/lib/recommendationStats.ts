export type RecommendationMetrics = {
  fetched?: number;
  analyzed?: number;
  indexed?: number;
};

export function formatRecommendationMetrics(metrics: RecommendationMetrics): string {
  const checked = metrics.fetched || 0;
  const freshSeen = metrics.indexed || 0;  // только реально добавленные в индекс на этом проходе
  if (checked === 0) {
    return '';
  }
  return (
    `Проверено на HH: ${checked} вакансий, ` +
    `из них ${freshSeen} новых (остальные ты уже видел).`
  );
}

export function formatRecommendationHeadline(freshCount: number): string {
  if (freshCount > 0) {
    return `Подобрали лучших: ${freshCount}.`;
  }
  return 'Рынок пока без подходящих для тебя. Обычно новые появляются раз в 6-12 часов.';
}
