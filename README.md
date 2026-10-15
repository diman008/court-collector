# Judicial Intelligence (реинжиниринг KAD + Court Collector)

**Статус:** v2.0.0-alpha.1 — безопасный MVP для ручного импорта судебных текстов; не готов к публичному production.

Цель: воспроизводимый анализ судебных материалов с доказательствами, точной цитатой,
документом-источником и датой. Система НЕ решает, было ли нарушение: окончательные
юридические выводы делает эксперт после проверки первоисточников.

## Что уже есть

- Единый формат номеров арбитражных дел (А40-12345/2025), нормализация и поиск по локальной базе.
- Импорт UTF-8 TXT через CLI, приём текста через API, сохранение SHA-256, источник, дата и
  исключение повторных документов в пределах дела.
- Выделение **дословных** упоминаний статей НК РФ с посимвольными смещениями.
- API с обязательным `X-API-Key`; при отсутствующем ключе закрыт, кроме /health.
- SQLite MVP, автоматические тесты и проверка Docker-сборки в PR.
- Не делает сетевых запросов к судебным сайтам, СПАРК или закрытым системам.

## Быстрый старт

Python 3.11+:

```bash
python -m pip install -e ".[test]"
python -m pytest -q
python -m judicial_intelligence.cli --db data/local.db add-case А40-12345/2025 --court "Арбитражный суд"
python -m judicial_intelligence.cli --db data/local.db import-txt А40-12345/2025 ./decision.txt --source-url https://example.org/decision
python -m judicial_intelligence.cli --db data/local.db report А40-12345/2025
```

Локальный API (НЕ публикуйте в интернет без TLS, внешнего контроля доступа и защиты данных):

```bash
export JUDICIAL_API_KEY="replace-with-a-long-random-secret"
export JUDICIAL_DB_PATH="data/judicial.sqlite3"
uvicorn judicial_intelligence.api:app --host 127.0.0.1 --port 8000
```

- `POST /v1/cases`: `{"case_number":"А40-12345/2025"}`
- `POST /v1/cases/{number}/documents`: `{"text":"...","source_kind":"user_provided"}`
- `GET /v1/cases?q=...`: локальный поиск
- `GET /v1/cases/{number}/documents`: метаданные документов
- `GET /v1/cases/{number}/report`: цитаты, offsets, SHA-256, пределы выводов
- `GET /health`: статус сервиса, без доступа к данным

## Границы и история

- `kad` (2025): FastAPI-прокси к недокументированному маршруту КАД с ScraperAPI fallback.
  Этот механизм **не входит** в v2: поддержка, правила доступа и стабильность не подтверждены.
- `court-collector` (2025): шаблон FastAPI/OpenAPI/Playwright без полноценных задач сбора.
  В v2 API переписан и работает; прежние `/start`, `/status`, `/download` не сохраняются.
- Исходный код остаётся в истории Git и в оригинальном репозитории kad до отдельной архивации.
- См. [стратегию](docs/STRATEGY.md), [план миграции](docs/MIGRATION.md) и [безопасность](docs/SECURITY.md).

Ключевой принцип: **лучше честно пометить отсутствие источника, чем выдать фиктивный факт.**
