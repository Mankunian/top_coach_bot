# TopCoach CRM 🎾

Telegram-бот и Mini App для теннисных тренеров, игроков и родителей.

## Текущий этап

- `dist/index.html` — интерактивный прототип CRM: группы, ученики, заявки, часы, оплаты, календарь и тарифы. Данные хранятся локально в браузере.
- `backend/` — регистрация через Telegram, справочники городов/кортов, сохранение профилей в SQLite, проверка Telegram initData.
- `dist/mini.html` — серверный профиль после регистрации через бота.
- `Dockerfile` и `railway.json` — конфигурация первого развёртывания.

Полная CRM ещё не подключена к серверной базе. Следующий этап: PostgreSQL, API для CRM, серверные уведомления и списания. Не использовать локальный прототип как источник реальных оплат.

## Запуск

Python 3.9+; внешние Python-зависимости не нужны.

```sh
python3 -m backend.server
```

API и интерфейс: http://127.0.0.1:8080 . Без BOT_TOKEN отправки в Telegram отключены. Переменные перечислены в `.env.example`; файл `.env` автоматически не загружается. Секреты передавайте через окружение, не коммитьте.

Для отдельного фронта:

```sh
python3 -m http.server 4173 --bind 127.0.0.1 --directory dist
```

## Проверки

```sh
python3 -m unittest discover -s tests -v
node --check dist/app.js
```

Требования: [docs/requirements.md](docs/requirements.md). Настройка бота, переменных и постоянного тома Railway: [docs/telegram-railway.md](docs/telegram-railway.md).
