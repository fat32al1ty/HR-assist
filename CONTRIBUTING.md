# Contributing

## Development setup

1. Fork/clone репозиторий.
2. Скопируйте `.env.example` в `.env.local`.
3. Запустите:

```powershell
docker compose up -d --build
```

## Branching

- Используйте отдельную ветку на каждую задачу.
- Именуйте ветки понятно: `feature/...`, `fix/...`, `refactor/...`.

## Pull request checklist

- Изменение имеет понятную цель.
- Не содержит секретов и токенов.
- Локально проходят тесты backend.
- Обновлена документация, если менялся behavior API/UI.
- Описаны риски и обратная совместимость.

## Coding standards

- Python: читаемые сервисы, маленькие функции, явные контракты схем.
- TypeScript: типобезопасные DTO и аккуратная обработка ошибок.
- SQLAlchemy: без неявных сайд-эффектов в репозиториях.

## Commit style (recommended)

- `feat: ...`
- `fix: ...`
- `refactor: ...`
- `test: ...`
- `docs: ...`
