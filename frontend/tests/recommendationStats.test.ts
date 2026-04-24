import test from 'node:test';
import assert from 'node:assert/strict';

import {
  formatRecommendationHeadline,
  formatRecommendationMetrics
} from '../lib/recommendationStats';

test('headline for 0 fresh matches nudges the user about cadence', () => {
  const message = formatRecommendationHeadline(0);
  assert.ok(message.includes('Рынок пока без подходящих для тебя'));
  assert.ok(message.includes('6-12 часов'));
  assert.ok(!message.includes('Найдено совпадений'));
});

test('headline for 1-3 fresh matches uses "Подобрали лучших" phrasing', () => {
  assert.equal(formatRecommendationHeadline(1), 'Подобрали лучших: 1.');
  assert.equal(formatRecommendationHeadline(3), 'Подобрали лучших: 3.');
});

test('headline for 5+ fresh matches uses the same count-based phrasing', () => {
  assert.equal(formatRecommendationHeadline(5), 'Подобрали лучших: 5.');
  assert.equal(formatRecommendationHeadline(42), 'Подобрали лучших: 42.');
});

test('metrics info hides the "already in index" jargon in favor of honest copy', () => {
  const info = formatRecommendationMetrics({ fetched: 43, analyzed: 18, indexed: 0 });
  assert.ok(info.includes('Проверено на HH: 43'));
  assert.ok(info.includes('из них 0 новых'));
  assert.ok(info.includes('остальные ты уже видел'));
  assert.ok(!info.includes('уже в индексе'));
  assert.ok(!info.includes('отфильтровано'));
});

test('metrics info folds indexed-in-this-run into the "new" count', () => {
  const info = formatRecommendationMetrics({ fetched: 50, analyzed: 12, indexed: 6 });
  assert.ok(info.includes('из них 6 новых'));
});

test('metrics info is empty when nothing was fetched (empty HH response)', () => {
  assert.equal(formatRecommendationMetrics({ fetched: 0, analyzed: 0, indexed: 0 }), '');
  assert.equal(formatRecommendationMetrics({}), '');
});
