# Длительность и несколько групп

Существующая JSON-модель CRM сохранена. Group.durationMinutes: integer minutes 60-1440, default 60. Session.durationMinutes — снимок длительности при генерации; ends = begins + durationMinutes * 60.

Автомиграция group-duration-v1 при initialize(): старые группы получают 60, длительность старых тренировок определяется из begins/ends без изменения времени и истории. PostgreSQL защищён существующей транзакционной advisory lock.

API action group принимает durationMinutes и необязательный members: number[]. Новый edit_group принимает id, name, durationMinutes и members для добавления. Изменение длительности обновляет только scheduled тренировки, которые ещё не начались. Исторические и начавшиеся не меняются.

Many-to-many представлен существующими group.members, содержащими Telegram ID единственных записей users. Один ID разрешён в нескольких группах; внутри группы и занятия повтор не добавляется. Принимаются только одобренные ученики тренера. Индивидуальная группа по-прежнему ограничена одним учеником. Добавление участников и уведомления транзакционны.

Billing uses actual session minutes (ends - begins). Calculations round the compatible hour balance to whole minutes before subtracting. Absent students are not charged; insufficient balances are capped at zero. Existing completed charges remain unchanged. The minimum is 60 minutes, including 90-minute sessions. Migration group-duration-min60-v1 upgrades short test group defaults and future sessions to 60 minutes while preserving started/completed sessions.

Проверки: python3 -m unittest discover -s tests -q; node --test tests/test_session_status.cjs; node --check dist/live.js; node --check dist/app.js; git diff --check. TypeScript, lint и отдельного build pipeline в репозитории нет.
