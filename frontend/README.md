# HR-Assist — AI-powered job search assistant

> Загружаешь резюме — получаешь отранжированный список вакансий, честный разбор «чего хватает» и «чего нет», и воронку откликов без ручной рутины.

**Живой продукт:** конкурирует с hh.ru Premium, карьерными коучами и getmatch как персональный AI-ассистент для соискателей.

---

## Что умеет

| Фича | Детали |
|---|---|
| **AI-подбор вакансий** | Семантический поиск по Qdrant — не по ключевым словам, а по смыслу резюме. Персональный профиль предпочтений обновляется с каждым лайком/дизлайком. |
| **Анализ резюме** | GPT-4o разбирает загруженный PDF/DOCX: роль, грейд, опыт, hard/soft skills, сильные стороны, зоны роста, риски. |
| **Трекер откликов** | Kanban-доска статусов (откликнулся → ответили → пригласили → отказали). Вакансии из подбора не дублируются в выдаче после отклика. |
| **AI сопроводительное письмо** | Генерация и редактирование cover letter прямо в карточке отклика. |
| **Профиль предпочтений** | Формат работы, переезд, желаемые должности, зарплатная вилка — учитываются при следующем подборе. |
| **Decay-взвешенный профиль** | Старые лайки/дизлайки затухают по экспоненте, свежий фидбэк весит больше. |

---

## Стек

| Слой | Технологии |
|---|---|
| Frontend | Next.js 15 · TypeScript · Tailwind CSS v4 · shadcn/ui |
| Backend | FastAPI · SQLAlchemy · Alembic · slowapi |
| AI | OpenAI GPT-4o (анализ, cover letter) · text-embedding-3-small (семантика) |
| Vector DB | Qdrant |
| Database | PostgreSQL |
| Инфраструктура | Docker Compose · GitHub Actions CI/CD · Ubuntu VPS |

---

## Быстрый старт (локально)

```bash
git clone https://github.com/fat32al1ty/HR-assist.git
cd HR-assist

# Создайте .env.local с вашими ключами
docker compose up -d --build
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000/docs
```

Минимальный `.env.local`:
```
OPENAI_API_KEY=sk-...
POSTGRES_USER=hr
POSTGRES_PASSWORD=hr
POSTGRES_DB=hrdb
SECRET_KEY=your-secret-key
```

---

## Архитектура

```
browser
  └─ Next.js (port 3000)
       └─ FastAPI (port 8000)
            ├─ PostgreSQL  — пользователи, резюме, отклики, фидбэк
            └─ Qdrant      — векторы вакансий + профили предпочтений
```

Alembic-миграции применяются автоматически при старте контейнера бэкенда.

---

## CI / CD

- **CI** (`.github/workflows/ci.yml`): ruff lint/format · pytest · tsc + eslint · docker build
- **CD** (`.github/workflows/cd.yml`): push в `master` → SSH на VPS → `git reset --hard` + `docker compose up -d --build`

Локальный quality gate перед push:

```bash
ruff format --check backend/app/ && ruff check backend/app/
docker compose exec -T backend python -m pytest -q
cd frontend && tsc --noEmit && eslint .
```

---

## Changelog

### v0.8.1 — UI/UX polish (2026-04-23)

**Исправления логики:**
- Вакансии с активными откликами больше не попадают повторно в раздел подбора

**Раздел откликов (`/applications`):**
- Карточки переоформлены в стиле подбора: белый фон, тень, `radius-lg`
- Убраны горизонтальные разделители внутри карточек

**Главная страница — workspace:**
- Межколоночный gap и gap между карточками увеличены (больше воздуха между зонами)
- Padding карточек снижен на ~15% (компактнее при том же объёме информации)
- Верхний padding страницы уменьшен
- Развёрнутое резюме: убраны серые разделители между разделами, добавлена кнопка «Свернуть» снизу
- Поля «Желаемые должности» и зарплата — обычный вес шрифта вместо жирного
- Опечатка «Мое» → «Моё»

**Подвал:**
- Добавлена ссылка на GitHub

### v0.8.0 — Phase 2.8 serious product polish

Канбан-трекер откликов, decay-взвешенный профиль предпочтений, дизайн-система на 10 темах.

### v0.7.0 и ранее

См. `git log`.

---

## Лицензия

MIT
