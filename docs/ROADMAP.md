# HR Assist — Roadmap

**Статус (2026-04-28):** IT-MVP закрыт релизом `v0.14.0`, шлифовка UX подбора в `v0.15.0`, явное управление ролями/доменами в `v0.16.0`, отказ от auto-pin + multi-facet expansion + feedback loop в `v0.17.0`, дроп `/audit` в `v0.18.0`. Phase 6 (search architecture rework) — стартовала с `v0.19.0` (instant-snapshot persistence). Дальше — `v0.20-v0.22` по плану `.claude/skills/product-roadmap/phase-6-search-architecture-rework.md`.

Полный план и принципы — в [`.claude/skills/product-roadmap/SKILL.md`](../.claude/skills/product-roadmap/SKILL.md).

## Для кого продукт

HR Assist — AI-ассистент для **соискателя** в IT. Не инструмент для рекрутёров: находит подходящие вакансии, объясняет почему они подходят, помогает писать отклики и вести воронку.

Заменяем на рынке:
- **hh.ru Premium** (~5 000 ₽/мес) — подсветка откликов, advanced-поиск.
- **Карьерных консультантов** (10–30 000 ₽ разово) — анализ резюме, сопроводительные письма, объяснение требований.
- **AI-агрегаторы уровня getmatch** — умный ранжир поверх нескольких источников.

## Последние релизы

### `v0.19.0` — Persistence fix для instant-результатов (2026-04-28)
Phase 6, шаг 1. Кнопка «Подбор» возвращает Stage 1 instant-матчи мгновенно, но они не персистились — refresh страницы поднимал `restoreRecommendationState` → `/recommend/latest` → возвращал последний deep_scan job, и хороший instant-результат заменялся худшим Stage 2. Фикс: instant-эндпоинт после успешного ответа пишет в `recommendation_jobs` строку со `status='completed'` через новый helper `record_instant_recommendation_snapshot` (sync, без воркера). Stage 1 и Stage 2 могут гонять — побеждает последний-завершённый. Никакой миграции (используем существующий status path), полностью совместимо с v0.18. Eval: 2 новых теста (refresh-after-instant возвращает те же matches; пустой instant тоже персистится). Подготавливает почву для v0.20 (полный decouple deep_scan от кнопки поиска).

### `v0.18.0` — Drop `/audit` (2026-04-28)
Страница аудита резюме (Phase 5.0/5.0.1) удалена. Причина: на не-engineering резюме фича выдавала ложные сигналы — Senior PM с 13 годами видел медианную ЗП 170к (engineering global median fallback), «топ-N навыков рынка» содержал Kafka/Kubernetes для PM-роли, а онбординг-вопросы (которые ДОЛЖНЫ были триггериться у PM) фронт не отрисовывал. Лучше убрать чем имитировать работу. Удалены: route `/audit` + компоненты, `resume_audit` сервис + кеш, `onboarding_questions` + YAML, admin-эндпоинты, eval-фикстуры. **Оставлены** (используются другими фичами): `salary_predictor`/`salary_baseline`/`track_classifier`/`llm_cost_accounting`. **БД**: таблицы `resume_audits` + `resume_clarifications` остаются (no destructive migration), орфаны.

### `v0.17.0` — Откат auto-pin, multi-facet discovery, feedback loop (2026-04-28)
Раскат v0.16.0 показал, что auto-pin (запись `analysis.target_role/domains` в `User.preferred_*` при первом сохранении) **отравлял** persistence у пользователей. У `fat32al1ty` после первого save оказались `preferred_titles=['product', 'Владелец продукта', 'Менеджер проектов', 'Руководитель AI-проектов и IT-платформ / AI Product Manager']` — query "Владелец продукта Менеджер проектов Project Manager ИТ" → HH вернул 208 вакансий не-IT product-менеджеров → pre-filter уронил 205, matcher выкинул 3, **0 матчей**. Независимая product-analyst-сессия подтвердила: фикс — backend, не UI.

**Tier 1 (фикс).** Auto-pin убран на фронте: `localRoles + autoDetected` union больше не пишется в БД, `preferred_*` пишется ТОЛЬКО когда юзер явно отредактировал пилюли. Серверный validator на `_validate_titles` (в `UserPreferencesUpdate` и `PreferenceOverrides`) режет noise: items < 4 символов и blocklist generic-stems (`product`, `manager`, `lead`, `head`, `director`, `specialist`, `engineer`, `developer`, `analyst`) без квалификатора. `_build_discovery_query` перестал брать `preferred_titles[:2]` — теперь все, словесный cap честно режет в конце. Логирование `discovery_query_noisy_pref` для уже-заражённых юзеров без destructive миграции.

**Tier 1.5 (UX).** Pills демотированы в `<details>` "Дополнительные фильтры (необязательно)", свёрнуто по умолчанию, с подсказкой что AI и так подбирает по резюме. Над матчами — read-only summary "Подбираем для тебя: {role} · {seniority} · {top 3 domains}" + ссылка на `/audit` для коррекции резюме (скрывается, если у юзера активный `preferred_titles` override).

**Tier 2 (multi-facet expansion).** `_build_deep_scan_queries` дополнен 3 facet-вариантами от **независимых** сигналов резюме: `role_family` отдельно, top-3 hard_skills отдельно, `role_family + top skill` combo. Дедуп по case-insensitive перед `[:max_queries=6]`. Pre-filter audit (B5): `_looks_unlikely_stack` смотрит на vacancy.title, не на query, `_has_sufficient_skill_overlap` фильтрует по навыкам, не по роли — обе совместимы со skill-only facet. Counter `multi_facet_queries_generated` в admin-телеметрии.

**Tier 3 (feedback loop).** Новый `feedback_signal_extractor.get_negative_term_set()` берёт до 30 dislikes (≤30d), агрегирует токены из `vacancy_profile.must_have_skills + nice_to_have_skills`, вычитает `resume.hard_skills`, возвращает top-N с freq≥2. Кеш 5 мин per `(user_id, resume_id)`. ScoringStage применяет `−0.02` за каждый пересекающийся токен (cap `−0.06`) — никогда не дропает. Counter `negative_term_penalty_applied`. Гейт через `settings.preference_decay_enabled` (по умолчанию off — оператор включает в `.env.local`). Магнитуды откалиброваны ниже `+0.03 DOMAIN_BOOST`, `+0.05 TITLE_BOOST_PARTIAL`.

### `v0.16.0` — Явное управление ролями и доменами поиска (2026-04-28)
В сайдбаре `/` появились две группы редактируемых пилюль: **Роли** (до 5) и **Домены** (до 3). Значения, выдранные из резюме, помечены серым (`auto`), вручную добавленные — акцентом (`pinned`). Inline-typeahead подсказывает варианты из частотного индекса по `vacancy_profiles`. Кнопка «Сохранить и обновить подбор» делает PATCH `/users/me/preferences` и сразу запускает instant-first refresh с новыми фильтрами. Новая колонка `users.preferred_domains` (миграция `0035`), новый эндпоинт `GET /users/preferences/suggestions?type=role|domain&q=…&limit=…` (5-мин кеш). `_build_discovery_query` уважает оба override'а; matcher применяет soft-boost `+0.03` к vacancy.score, если `vacancy.domains ∩ preferred_domains ≠ ∅` — никогда не отбраковывает. Новый счётчик `domain_preference_boost_applied` в admin-телеметрии. Eval: 16 новых тестов (PATCH semantics + cap + clear + suggestions sort/prefix/auth + discovery query + matcher boost). Designer ввёл 16 новых семантических токенов (`pill-auto-*`, `pill-pinned-*`, `combobox-*`, `unsaved-indicator-fg`) + анимации `pill-in/pill-out` с `prefers-reduced-motion`-гвардом.

### `v0.15.0` — UX подбора: instant-first + partial-on-timeout (2026-04-28)
Кнопка «Подбор» больше не зависает на «10%» по 7 минут. Двухэтапный flow: (1) синхронный `POST /vacancies/recommend/instant/{resume_id}` отдаёт матчи из уже прогретого индекса за ≤5 c — пользователь сразу видит список; (2) фоновый deep-scan запускается без блокирующего спиннера, тонкий индикатор сверху списка показывает «ищем ещё», результаты доливаются по завершении. Дефолты payload бэк-side: `use_prefetched_index=true, discover_count=40` (было `false/100`). Server timeout снижен 420→180 c, при срабатывании внутреннего runtime budget (150 c) job завершается `completed` с флагом `metrics.partial=true` — фронт рисует баннер «это часть результатов, обновите через 1–2 минуты» вместо ошибки. Janitor в `vacancy_warmup` раз в цикл подметает зомби-jobs (`status=running` старше timeout). Eval: 11 новых тестов (instant happy/cold/404/no-HH-call + partial flag round-trip + sweeper).

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
| UX — Instant-first matching | `v0.15.0` | 2026-04-28 | Двухэтапный подбор: instant ≤5 c из индекса + фоновый deep-scan без блок-спиннера, partial-on-timeout. |
| UX — Editable role/domain pills | `v0.16.0` | 2026-04-28 | Пилюли ролей и доменов в сайдбаре, typeahead из vacancy_profiles, soft-boost +0.03 в matcher'е. |
| Matching — auto-pin off + multi-facet + feedback | `v0.17.0` | 2026-04-28 | Откат auto-pin, noise blocklist, 3 facet-query от резюме, negative-term penalty от dislikes. |

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
