# TopCoach Web Admin

## Run and deploy

The existing Python backend serves `/admin` and `/api/admin/*`. Its Docker image
now includes `admin/`. The separate landing service remains static except for
its `/admin` redirect. Telegram routes and frontend assets are unchanged.

1. Configure `ADMIN_USERNAME` and a unique `ADMIN_PASSWORD` (minimum 14 characters)
   on the **backend** using your environment/secret manager. No default credentials.
2. Start `python3 -m backend.server`. Startup initializes admin tables and seeds
   the configured account. Alternatively run `python3 -m backend.admin_auth`.
3. Use `ADMIN_COOKIE_SECURE=true` (default) behind HTTPS in production. For local
   HTTP only, set `ADMIN_COOKIE_SECURE=false`.
4. Configure `ADMIN_URL=https://BACKEND_HOST/admin` on the **landing** service.
5. Open Login on the landing. Deploy both updated services to activate the link.

The account survives removal of seed env variables. Changing the password in env
and restarting updates its PBKDF2 hash and revokes that account's sessions.
Changing username creates another account; remove unused accounts explicitly in
`admin_accounts` and their `admin_sessions` if replacing an administrator.

## Scope and definitions

- Dashboard: registered coaches; registered players and parents; completed sessions;
  recorded payments; daily payment and session charts; current pending requests/groups.
- Profiles, groups, sessions, requests and finances are read-only. Details, search,
  coach/city/status filters, pagination and filtered CSV exports are available.
- Clubs are seeded once from the existing `dist/venues.js` catalog, retaining IDs.
  Admin club edits feed the existing `venues()` API. Existing user profile strings
  remain historical snapshots. No profile, group or notification is rewritten.
- Courts are new child records because the existing model only described clubs.
  They support create/read/update/delete, surface and availability status. Courts
  are not retroactively linked to free-text session locations.
- Club deletion is blocked while referenced by a court or user profile.
- Directory writes are transactional and recorded in `admin_audit`.
- User counts include only `step=done`; players include the `parent` role.
  Registration dates are absent, so user and group counts are all-time snapshots.
- Session period uses session `date`; payment period uses payment `date`; request
  period uses `created` converted to UTC+5. Both boundaries are inclusive.
  Default: 30 days; maximum: 367 days. The UI and CSV share filtering code.
- Money is stored in minor units and displayed/exported as KZT / 100. These are
  payments to coaches, **not TopCoach revenue**. CSV includes period and timezone;
  formula-like text is escaped. Export includes all filtered rows, not only a page.

## Security and storage

Opaque session tokens are hashed in the database and expire after 8 hours.
Cookies use HttpOnly, SameSite=Strict, Secure by default. Mutation endpoints
require JSON, a session CSRF token and a matching Origin when supplied. Login has
persistent limits (10 failed attempts / 15 minutes per socket IP). Forwarded IP
headers are not trusted; reverse proxies may share the limit, so configure a
trusted edge rate limiter for larger deployments. Logout revokes the DB session.
Admin responses disable caching and apply CSP, nosniff and frame protection.
There is no public account registration or frontend password.

The API reuses the shared CRM JSON transaction model. Pagination limits responses,
not DB reads: filtering/aggregation scans that snapshot in memory. For large data
volumes, normalize the CRM tables before adding indexed SQL aggregation. Additive
admin tables work with SQLite and PostgreSQL through the existing adapter.

## Verification

```
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/*.cjs
node --check admin/admin.js
PYTHONPYCACHEPREFIX=/tmp/topcoach-pycache python3 -m compileall -q backend landing
```

There is no Node bundler/build in this project: HTML/CSS/JS ship directly.
