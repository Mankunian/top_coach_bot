# Длительность и несколько групп

Существующая JSON-модель CRM сохранена. Group.durationMinutes: 30/60/90/120, default 60. Session.durationMinutes — снимок длительности при генерации; ends = begins + durationMinutes * 60.

Автомиграция group-duration-v1 при initialize(): старые группы получают 60, длительность старых тренировок определяется из begins/ends без изменения времени и истории. PostgreSQL защищён существующей транзакционной advisory lock.

API action group принимает durationMinutes и необязательный members: number[]. Новый edit_group принимает id, name, durationMinutes и members для добавления. Изменение длительности обновляет только scheduled тренировки, которые ещё не начались. Исторические и начавшиеся не меняются.

Many-to-many представлен существующими group.members, содержащими Telegram ID единственных записей users. Один ID разрешён в нескольких группах; внутри группы и занятия повтор не добавляется. Принимаются только одобренные ученики тренера. Индивидуальная группа по-прежнему ограничена одним учеником. Добавление участников и уведомления транзакционны.

Баланс общий для пары тренер/ученик. Текущее правило списания 1 часа за посещение сохранено; пропорциональная длительности тарификация не входит в это изменение.

Проверки: python3 -m unittest discover -s tests -q; node --test tests/test_session_status.cjs; node --check dist/live.js; node --check dist/app.js; git diff --check. TypeScript, lint и отдельного build pipeline в репозитории нет.
