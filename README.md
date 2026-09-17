# TopCoach CRM 🎾

Telegram-бот и Mini App для теннисных тренеров, игроков и родителей.

## Текущий этап

- `dist/index.html` — интерактивный прототип CRM: группы, ученики, заявки, часы, оплаты, календарь и тарифы. Данные хранятся локально в браузере.
- `backend/` — регистрация через Telegram, справочники городов/кортов, сохранение профилей в SQLite, проверка Telegram initData.
- `dist/mini.html` — серверный профиль после регистрации через бота.
- `Dockerfile` и `railway.json` — конфигурация первого развёртывания.

Серверная CRM подключена к PostgreSQL через DATABASE_URL: реальные заявки, группы, ученики, оплаты, календарь и уведомления. /mini.html и корневой URL API открывают серверную версию без моков. Инструкция проверки: [docs/production-crm.md](docs/production-crm.md). Отдельный index.html остаётся дизайн-прототипом для локального сервера 4173.

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

## Лендинг и настройки

- Отдельный лендинг: `landing/`, запуск `python3 landing/server.py`, http://127.0.0.1:4181/ . Для Railway создайте отдельный сервис с Root Directory `/landing` и Config File `/landing/railway.json`.
- Профиль → Настройки: напоминание за 1 или 3 часа, русский / қазақша / English.
- Переводы: `dist/locales/ru.json`, `en.json`, `kaz.json`. Язык сохраняется в профиле тренера.
- Минимум тренировки 60 минут; 90 минут разрешены. Остаток в боте отображается в часах и минутах.
