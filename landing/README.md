# TopCoach landing

Independent public website, in the same GitHub repository as the CRM.

## Railway

1. Create a **new service** from `Mankunian/top_coach_bot` (do not replace the bot service).
2. Set **Root Directory** to `/landing`.
3. Set Railway Config File to `/landing/railway.json` (the absolute repository path).
4. Deploy, then generate a public domain. PORT is provided by Railway.
5. No bot token, database credentials, or other CRM variables are needed here.

The Docker build includes only `public/` and the static server. There are no admin routes or credentials yet. Buttons lead to @TopCoachCRM_bot.

## Local preview

`python3 landing/server.py` → http://127.0.0.1:4181/

Responsive layout supports phones, portrait/landscape tablets and desktop.
