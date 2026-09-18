# Coach navigation

Primary tabs: home (overview), calendar (existing schedule), groups, more.
More links to existing profile, requests, settings pages. Reports and Premium retain their identifiers and entry points. Player primary navigation stays unchanged.

`navigation.js` uses the existing `?page=` parameter with an allowlist and role checks. `?page=requests` from bot notifications still opens requests. Navigation preserves other URL parameters and the Telegram hash. Browser history supports Back/Forward; Telegram BackButton uses the same back action. A directly opened nested page falls back to More, then Home, without sending the user outside the Mini App. Back first closes an open dialog. In-memory group tabs and calendar day persist during navigation.

Home is an overview of today's session count, pending requests and the next three sessions. The calendar retains attendance, session status, date selection and polling.
