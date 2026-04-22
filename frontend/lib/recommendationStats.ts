export type RecommendationMetrics = {
  fetched?: number;
  analyzed?: number;
  indexed?: number;
};

export function formatRecommendationMetrics(metrics: RecommendationMetrics): string {
  const checked = metrics.fetched || 0;
  const freshSeen = (metrics.analyzed || 0) + (metrics.indexed || 0);
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
    return `Свежего с прошлого раза: ${freshCount}.`;
  }
  return 'Рынок пока без свежих для тебя. Обычно новые появляются раз в 6-12 часов.';
}
