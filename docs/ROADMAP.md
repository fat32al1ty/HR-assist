# HR Assist — Roadmap

**Статус (2026-04-25):** IT-MVP закрыт релизом `v0.14.0`. Дальше — `v1.0.0` (Phase 5.3, domain expansion), запускается только после подтверждения PMF в IT.

Полный план и принципы — в [`.claude/skills/product-roadmap/SKILL.md`](../.claude/skills/product-roadmap/SKILL.md).

## Для кого продукт

HR Assist — AI-ассистент для **соискателя** в IT. Не инструмент для рекрутёров: находит подходящие вакансии, объясняет почему они подходят, помогает писать отклики и вести воронку.

Заменяем на рынке:
- **hh.ru Premium** (~5 000 ₽/мес) — подсветка откликов, advanced-поиск.
- **Карьерных консультантов** (10–30 000 ₽ разово) — анализ резюме, сопроводительные письма, объяснение требований.
- **AI-агрегаторы уровня getmatch** — умный ранжир поверх нескольких источников.

## Последние релизы

### `v0.14.0` — Phase 5.2 — Стратегия отклика на конкретную вакансию (2026-04-25)
По кнопке «Стратегия» открывается страница, где LLM (или template fallback) объясняет: что в твоём опыте релевантно этой вакансии, чего не хватает и как это компенсировать в письме, плюс готовый draft сопроводительного на ≤ 1200 символов. Каждую карточку можно пометить «не я / не правда» — корректировки идут в `recommendation_corrections` для будущего ranker'а. Cost-cap $0.05/DAU/день общий с `/audit`.

### `v0.13.0` — Phase 5.1 — Треки подбора: точка / вырост / стрейч (2026-04-25)
Подбор больше не плоский список. Каждая вакансия классифицируется детерминированным правилом (vector_score + разница seniority + overlap навыков) в один из 3 треков и попадает в свою collapsible-секцию. Над каждой секцией — editorial-строка вида «70% требуют Kafka — у тебя её нет». В стрейче — CTA «Показать вакансии с мягкими требованиями».

### `v0.12.1` — Phase 5.0.1 — Починка `/audit` (2026-04-25)
Страница `/audit` перестала быть пустой: skill gaps читал не тот ключ vacancy_profile (`required_skills` вместо `must_have_skills`), market salary падал в `None` без обученного LightGBM (добавлен median-by-role fallback), sample_size считал все вакансии вместо bucket по role+seniority.

### `v0.12.0` — Phase 5.0 — Market-grounded resume audit (2026-04-25)
Новая страница `/audit`: как мы прочитали резюме (роль/грейд/альтернативы), market-salary band для роли+гео, топ-5 skill gaps от рынка, проблемы качества резюме (правила). 30 IT-специфичных вопросов в YAML с trigger-условиями; LLM-классификатор за флагом, дефолт — детерминированные правила. Cost cap $0.05/DAU/день с template fallback.

### `v0.11.0` — Phase 4.3 — Best-of-market fallback (2026-04-24)
Подбор не теряет «лучшее историческое»: если warm-run не набирает high-quality target, deep-scan повторяется без `date_from`. Бюджеты warm-run расширены (analyzed 18→50, deep queries 3→6, match_limit 20→40). Фронт переверстан под пагинацию 10+10.

## Что уже в проде

| Фаза | Релиз | Дата | Суть |
|---|---|---|---|
| 0 — Foundation | `v0.1.0` | 2026-04-21 | Безопасность, лимиты бюджета, аудит — до фич. |
| 1 — Actionability | `v0.2.0` | 2026-04-21 | «Посмотреть 20» → «подать, вести, понять». |
| 1.7 — Matching + multi-profile | `v0.3.0` | 2026-04-21 | ↑ релевантность, до 2 резюме у юзера. |
| 1.8 — Cross-domain noise gate | `v0.4.0` | 2026-04-21 | Senior-IT не ловит стройку/юристов из-за общих русских слов. |
| 1.9 — Freshness + agency | `v0.5.0` | 2026-04-21 | «Обновить» приносит свежее, ✓/✗ override на карточке. |
| 2.0 — First-run rescue | `v0.6.0` | 2026-04-22 | Cold pool 18→40, two-tier output, одна кнопка. |
| 2.1–2.7 — Matching overhaul | `v0.7.0` | 2026-04-22 | Eval-harness в CI, MMR, ESCO-гейт, cross-encoder/LLM rerank. |
| 2.8 — Serious product polish | `v0.8.0` | 2026-04-22 | Tailwind+shadcn, admin-сплит, линейный flow, Kanban. |
| 3.0 — Privacy Level A | `v0.9.0` | 2026-04-23 | PII-scrubber, удаление оригиналов и `extracted_text`. |
| 3.1 — Admin overview | `v0.9.1` | 2026-04-24 | `/admin/overview`, отмена чужих job'ов, `last_login_at`. |
| 3.2 — Funnel observability | `v0.9.2` | 2026-04-24 | 26 reasons в waterfall, `user_vacancy_seen` 14d. |
| 3.3 — Admin activity stats | `v0.9.3` | 2026-04-24 | `user_login_events`, DAU/WAU/MAU + 14d-графики. |
| 3.4 — Funnel pre-analyze drops | `v0.9.4` | 2026-04-24 | Закрыли 2 silent drop'а в discover. |
| 4.0 — Matcher score cache | `v0.10.0` | 2026-04-24 | `resume_vacancy_scores` TTL 7d, не гоним rerank повторно. |
| 4.1 — Source adapters | `v0.10.1` | 2026-04-24 | Feature-flag aggregator + `/admin/vacancy-sources/probe`. |
| 4.2 — Salary predictor | `v0.10.2` | 2026-04-24 | LightGBM + median-by-role baseline + admin endpoints. |
| 4.3 — Best-of-market fallback | `v0.11.0` | 2026-04-24 | Cursor-free deep-scan, warm-run бюджеты ↑, пагинация UI. |
| 5.0 — Market audit + Q&A | `v0.12.0` | 2026-04-25 | `/audit` (4 блока), 30 онбординг-вопросов, cost cap $0.05/DAU. |
| 5.0.1 — Audit data pipe fixes | `v0.12.1` | 2026-04-25 | Skill gaps / market salary / sample_size перестали быть пустыми. |
| 5.1 — Track segmentation | `v0.13.0` | 2026-04-25 | 3 трека (точка/вырост/стрейч), gap-analysis из рынка. |
| 5.2 — Per-vacancy strategy | `v0.14.0` | 2026-04-25 | Стратегия отклика + cover letter + recommendation corrections. |

## Что дальше

**`v1.0.0` — Phase 5.3 — Domain expansion (PMF-gated).** Расширение на Healthcare и Finance: domain classifier (zero-shot LLM), отдельные taxonomy + onboarding YAML на каждый домен, salary baselines, domain-aware UI. Запускается **только после подтверждения PMF в IT**:

- WAU/MAU ≥ 0.35
- NPS ≥ +20 (N=50)
- Audit-applied ≥ 40% **и** apply-after-strategy ≥ 30%

Если 2 из 3 не выполнены — фаза откладывается, чиним IT-MVP. С N=1 dogfood'а PMF-gate физически не проходим — ждём реальных юзеров.

После `v1.0.0` продукт выходит из закрытой беты.

## Как читать этот файл

- Версия `vX.Y.Z` — публичный git-тег.
- Подробные release notes — в `release-notes/vX.Y.Z.md` и в GitHub Releases.
- Продукт в закрытой бете; версия намеренно меньше 1.0.

## Вклад в проект

Правила для контрибьюторов: [CONTRIBUTING.md](../CONTRIBUTING.md)
