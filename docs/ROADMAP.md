# HR Assist — Roadmap

**Статус (2026-04-24):** публичный план развития пересматривается.

После релиза `v0.8.0` (Phase 2.8 — Serious product polish) мы сознательно сбросили forward-looking часть roadmap — дальнейшие фазы (Retention, Value-Add, Infra, Quality) отменены в прежнем виде и будут переработаны под свежие вводные. Этот файл временно удерживает только историю того, что уже в проде.

## Для кого продукт

HR Assist — AI-ассистент для **соискателя**. Мы не инструмент для рекрутёров: мы находим подходящие вакансии, объясняем, почему они подходят, помогаем писать отклики и вести воронку.

Чем заменяем на рынке:

- hh.ru Premium (~5 000 ₽/мес) — подсветка откликов, advanced-поиск.
- Карьерных консультантов (10–30 000 ₽ разово) — анализ резюме, сопроводительные письма, объяснение требований.
- AI-агрегаторы уровня getmatch — умный ранжир поверх нескольких источников.

Монетизация, маркетинг и миграции инфраструктуры в этот roadmap **не входят** — это отдельные плоскости.

## Что уже в проде

| # | Фаза | Релиз | Одним предложением |
|---|------|-------|--------------------|
| 0 | Foundation | `v0.1.0` (2026-04-21) | Закрыли безопасность, лимиты бюджета и аудит до того, как пошли делать фичи. |
| 1 | Actionability | `v0.2.0` (2026-04-21) | Превратили «посмотреть 20 вакансий» в «подать отклик, вести воронку, понять почему подходит». |
| 1.7 | Matching quality + multi-profile | `v0.3.0` (2026-04-21) | Подняли релевантность подбора и разрешили до 2 параллельных профилей-резюме у одного пользователя. |
| 1.8 | Matching relevance hardening | `v0.4.0` (2026-04-21) | Починили кросс-доменный шум: senior-IT резюме больше не ловит стройку, авто и юристов из-за общих русских слов. |
| 1.9 | Freshness + accuracy + agency | `v0.5.0` (2026-04-21) | Каждое «Обновить подбор» приносит свежее, «не хватает» перестал врать, юзер может отметить «у меня это есть». |
| 2.0 | First-run rescue | `v0.6.0` (2026-04-22) | Холодный старт расширен 18 → 40 вакансий + HH и LLM в параллель + two-tier output + одна кнопка вместо трёх. |
| 2.1–2.7 | Matching quality overhaul | `v0.7.0` (2026-04-22) | Шумовой гейт + eval-харнесс + разбивка матчера на стадии + MMR + ESCO-гейт ролей + cross-encoder/LLM-rerank + телеметрия + скелет зарплатного предиктора. |
| 2.8 | Serious product polish | `v0.8.0` (2026-04-22) | Полировка продукта до «серьёзно выглядит»: Tailwind+shadcn фундамент, честные auth-ошибки, админ-сплит, роут-сплит, линейный главный поток, Kanban переверстан, дизайн-проход. |
| 3.0 | Privacy minimization (Level A) | `v0.9.0` (2026-04-23) | PII-scrubber на входе в LLM; `resumes.extracted_text` удалён, оригинальный файл стирается сразу после анализа, `storage_path` обнуляется; из Qdrant payload убраны `candidate_name` и `canonical_text`; `original_filename` санитизируется до `resume.{ext}`. Подробности — [`PRIVACY.md`](../PRIVACY.md). |
| 3.1 | Admin overview | `v0.9.1` (2026-04-24) | `/api/admin/overview`: всего пользователей / активные за 24 ч / всего резюме / всего вакансий (+индексированные) / топ-10 искомых ролей / список активных фоновых подборов. `POST /api/admin/jobs/{job_id}/cancel` — админ останавливает подбор любого пользователя. `users.last_login_at` + touch на логине. |
| 3.2 | Funnel observability + dedup | `v0.9.2` (2026-04-24) | Полная воронка подбора без «молчаливых дропов»: 26 причин отсева разложены по трём уровням (пре-фильтр / LLM / матчер), персистятся в `recommendation_jobs.metrics`, визуализируются waterfall-UI в админке (`GET /api/admin/jobs/{id}/funnel`). HH-пагинация рано останавливается, если ≥90% URL на странице уже в индексе (`pages_truncated_by_indexed`). `user_vacancy_seen` (14-дневное окно под флагом `feature_exclude_seen_enabled`) исключает недавно показанные вакансии из нового подбора — повторные «подобрать» не гонят один и тот же топ-N. |
| 3.3 | Admin activity stats | `v0.9.3` (2026-04-24) | Новая таблица `user_login_events` фиксирует каждый успешный логин; админка показывает DAU/WAU/MAU + 14-дневные графики регистраций и логинов (`activity` в `AdminOverviewRead`). `users.last_login_at` давал только последнюю точку — теперь настоящий time-series. |
| 3.4 | Funnel pre-analyze drops | `v0.9.4` (2026-04-24) | Закрыты два silent drop'а в `discover_and_index_vacancies`: (а) URL, отброшенные из-за LLM-бюджета `max_analyzed`, теперь считаются в `fetched_dropped_analyzed_budget`; (б) внутри-job дубликаты URL — в `fetched_dedup_within_job`. Оба ключа зарегистрированы в `_METRIC_INT_FIELDS` и появляются в admin waterfall. |
| 4.0 | ResumeVacancyScore cache | `v0.10.0` (2026-04-24) | Новая таблица `resume_vacancy_scores(resume_id, vacancy_id, pipeline_version, similarity_score, vector_score, computed_at, scores_json)` кэширует финальный hybrid-score матчера. При "Обновить подбор" кандидаты, уже посчитанные в предыдущем прогоне, не гоняются повторно через cross-encoder / LLM rerank — TTL 7 дней, инвалидация на re-analyze резюме. Pipeline version `"3.0"` (bump'ается при breaking changes матчера). |
| 4.1 | Source adapters re-activation | `v0.10.1` (2026-04-24) | `search_vacancies` перешёл с hardcoded "только HH API" на feature-flag aggregator: `feature_superjob_enabled`, `feature_habr_enabled`, `feature_public_sources_enabled` (все default `False` — безопасный выкат). Админ-эндпоинт `POST /api/admin/vacancy-sources/probe` запускает каждый источник по тестовому запросу и возвращает counts — позволяет убедиться, что адаптер живой, до включения флага. Исключение в одном источнике не роняет остальные. |
| 4.2 | Salary predictor activation | `v0.10.2` (2026-04-24) | `salary_predictor.predict()` теперь реально вызывается в `persist_vacancy_profile` — как только корпус нарастёт до MIN_CORPUS=1000 и LightGBM будет обучен, `predicted_salary_*` колонки начнут заполняться автоматически. Добавлен baseline (median-by-role, feature_salary_baseline_enabled, default off) на случай когда LightGBM ещё не готов. Админ-эндпоинты: `GET /api/admin/salary-predictor/status` (counts + model version) и `POST /api/admin/salary-predictor/backfill` (применить predictor ко всем существующим профилям без predicted). |
| 4.3 | Warm-run widening + best-of-market fallback | `v0.11.0` (2026-04-24) | Подбор больше не теряет «лучшую работу из исторических»: когда warm-run не набирает `target_match_count` high-quality совпадений, deep-scan повторяется с `date_from=None` (до 2 запросов) — HH отдаёт вакансии, опубликованные до прошлого захода юзера. Бюджеты warm-run расширены: `WARM_MAX_OPENAI_ANALYZED` 18→50, `INTERACTIVE_MAX_DEEP_QUERIES` 3→6, `match_limit` default 20→40, `min_prefetched_matches` 8→10. Новая метрика `cursor_fallback_queries_run` в воронке. Фронт переверстан под пагинацию: 10 карточек сразу + кнопка «Показать ещё 10» (до 40); заголовок честный `Подобрали лучших: N` вместо вводящего в заблуждение `Свежего с прошлого раза`; в `formatRecommendationMetrics` убран двойной счёт `analyzed + indexed` → только `indexed`. |

## Что дальше

Следующий план собирается отдельно под свежие вводные от продакт-оунера. Этот файл обновится, когда план будет зафиксирован.

## Как читать этот файл

- Версия `vX.Y.Z` — публичный git-тег, связанный с релизом.
- История отдельных PR — в CHANGELOG и в комментариях к релизам на GitHub.
- Продукт в закрытой бете; версия намеренно меньше 1.0.

## Вклад в проект

Правила для контрибьюторов: [CONTRIBUTING.md](CONTRIBUTING.md)
