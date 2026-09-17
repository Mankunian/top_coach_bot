# Coach preferences

Profile → Settings: reminderHours (1 or 3, default 3), language (ru/en/kaz, default ru). Saved in the existing users JSON via authenticated `POST /api/action` action `settings`. Only the current coach can save preferences. Profile saves preserve concurrent preference changes.

Reminder time is selected by the session's coach and applies to coach and students. Each session gets one advance reminder, even after changing settings. Start/completion notifications are unchanged. Previously queued messages keep their original text; new messages use recipient language. Students retain Russian until player language settings are added.

`dist/locales/{ru,en,kaz}.json` are shared frontend/backend catalogs. `dist/i18n.js` translates static template fragments and labels; substitutions containing user names, notes and addresses remain untouched. Calendar locale follows the selection; Kazakh uses the browser locale kk-KZ. Coach bot notifications and /start menu use the persisted language.

Durations must be whole minutes between 60 and 1440. 90 minutes is valid. Migration `group-duration-min60-v1` upgrades short test defaults and future sessions, preserving started and completed ones. Bot balances use hours/minutes with Russian plural forms.

The independent landing is under `/landing`; see its README for Railway deployment. No administrator login is implemented at this stage.
