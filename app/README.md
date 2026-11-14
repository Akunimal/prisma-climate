# PRISMA web app

Flutter web client for the PRISMA static data tree. It reads only the JSON files
published on GitHub Pages (`data/latest.json`, `data/about.json`,
`data/stations/<id>.json`); there is no server and no API.

## What it shows

- **Stations** — searchable list of the 19 configured stations with their climate
  zone.
- **Forecast** — for the selected station, one chart per variable (`t2m_max`,
  `t2m_min`) with the 10–90 % band, the 25–75 % band and the median, one series
  per model (never pooled); precipitation as the fraction of members at or above
  1 mm and 10 mm per lead day; the last 30 days of SMN observed max/min; the
  issue time in Argentina local time.
- **About / Status** — what the app shows, that the forecasts are raw and
  uncalibrated, that verification is not published before the 15-issue-date gate,
  and the sources and licences from `about.json`.

A `missing_members` case is shown as "no data" and is never interpolated. Every
user-facing string lives in `lib/src/strings.dart`, so another language can be
added without touching the widgets.

## Data base URL

Defaults to the relative `data/` next to the page. Override it at build time:

```bash
flutter build web --dart-define=PRISMA_DATA_BASE_URL=https://host/path/data/
```

An unknown `schema_version` is rejected with a clear message; network and parse
errors are shown to the user, never swallowed.

## Development

```bash
flutter pub get
flutter analyze
flutter test
flutter run -d web-server
```

The charts are drawn with `CustomPainter`; there is no charting dependency.
