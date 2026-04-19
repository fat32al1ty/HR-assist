import test from 'node:test';
import assert from 'node:assert/strict';

import {
  excludeFeedbackVacancies,
  normalizeVacancyId,
  removeVacancyFromList,
  removeVacancyMatchEntry
} from '../lib/vacancyMatching';

type Match = {
  vacancy_id: number | string;
  title: string;
};

test('normalizeVacancyId handles number and string ids', () => {
  assert.equal(normalizeVacancyId(123), 123);
  assert.equal(normalizeVacancyId('123'), 123);
  assert.equal(normalizeVacancyId('abc'), 0);
});

test('removeVacancyFromList removes by id even when list has string ids', () => {
  const list: Match[] = [
    { vacancy_id: '101', title: 'A' },
    { vacancy_id: 102, title: 'B' }
  ];
  const next = removeVacancyFromList(list, 101);
  assert.equal(next.length, 1);
  assert.equal(normalizeVacancyId(next[0].vacancy_id), 102);
});

test('excludeFeedbackVacancies removes disliked, selected and hidden ids', () => {
  const source: Match[] = [
    { vacancy_id: 1, title: 'one' },
    { vacancy_id: '2', title: 'two' },
    { vacancy_id: 3, title: 'three' },
    { vacancy_id: 4, title: 'four' }
  ];
  const disliked: Match[] = [{ vacancy_id: 1, title: 'one' }];
  const selected: Match[] = [{ vacancy_id: '2', title: 'two' }];
  const hiddenIds = [3];

  const next = excludeFeedbackVacancies(source, disliked, selected, hiddenIds);
  assert.deepEqual(next.map((item) => normalizeVacancyId(item.vacancy_id)), [4]);
});

test('removeVacancyMatchEntry falls back to source_url+title when id is invalid', () => {
  const list = [
    { vacancy_id: 1, title: 'one', source_url: 'https://hh.ru/vacancy/1' },
    { vacancy_id: 2, title: 'two', source_url: 'https://hh.ru/vacancy/2' }
  ];
  const target = { vacancy_id: 'bad-id', title: 'two', source_url: 'https://hh.ru/vacancy/2' };
  const next = removeVacancyMatchEntry(list, target);
  assert.deepEqual(next.map((item) => normalizeVacancyId(item.vacancy_id)), [1]);
});
