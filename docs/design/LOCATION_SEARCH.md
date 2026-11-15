# Place search and GPS — design note (T36)

Status: specification only. No code, data or workflow changes in this document.
Owner decisions recorded 2026-11-14 (D1–D4).

## 1. Purpose and non-goals

**Purpose.** Let a user find a place (town, locality) by name on the Stations screen and
see which of the 19 PRISMA stations is nearest, how far it is, and jump to that
station's forecast. Optionally use the browser's geolocation for the same flow.

**Non-goals.**
- Street-address geocoding.
- Runtime calls to external geocoding services.
- A forecast "for the town": the forecast shown is always the station's forecast,
  labelled as such.
- Storing or transmitting the user's location.
- Any skill number (CRPS, CRPSS, Brier, reliability, coverage, leaderboard).

## 2. Place search

The existing Stations search field is extended: it matches station names (as today)
and places from the shipped gazetteer. Results are grouped as "Stations" and "Places".
Matching is case-insensitive and accent-insensitive (reuse the existing normaliser).
Duplicate place names are disambiguated by province/first-level division.

Ranking: exact match first, then prefix match, then by population (or another ranking
field) descending. Ties broken alphabetically by place name then province.

Choosing a place shows: the nearest station, the distance, the warning when it applies
(see 5), and a "View forecast" button that opens that station's forecast through the
existing navigation path. On the map it shows the place, the station and the link
between them.

## 3. Gazetteer data

Proposed location in the static data tree: `data/places/<country>.json` (for example
`data/places/ar.json`), one file per country. The app loads it lazily on the first
search; it is not fetched at startup.

Fields per record: `name`, `admin1` (province/first-level division), `lat`, `lon`,
`population` (or `rank` when population is unavailable). The file also carries a top-level
`attribution` string and `source` identifier.

Size budget: keep each country file small enough for a phone (target under a few MB
compressed by the browser; for Argentina target under 2 MB). If a source has too many
records, filter to populated places above a threshold and document it.

Generation: a repository script (under `scripts/`) reads the chosen source, normalises
names and provinces, writes `data/places/<country>.json`. Attribution is shown in the
About screen and next to the data, reusing the existing attribution pattern.

A new country adds its own file under `data/places/` plus a registry entry; no code
change is required. The schema change is additive: a new optional tree under `data/`,
no change to `latest.json`, `about.json` or `stations/*.json`. `docs/SITE_DATA.md`
will need a new section describing `data/places/<country>.json`.

## 4. Nearest-station function

Great-circle (haversine) distance in kilometres between the place/user point and each
station; the station with the minimum distance wins. Ties are broken by station name
then station id for determinism. Inputs: a point (lat, lon) and the station list;
output: the station and the distance.

Distance alone is a weak proxy in mountainous terrain (a nearby station on the other
side of a ridge). Optional station elevation (from the region config or the gazetteer)
may later improve the message; this stage only displays distance.

## 5. Honesty rules

- Distance is always visible, never hidden.
- Above 100 km (single configurable constant `kNearestStationWarningKm`) a clear
  warning is shown.
- English labels (to be translated through the glossary):
  - "Nearest station: {station}"
  - "Distance: {km} km"
  - "No station within 100 km — the forecast is for the nearest station, which may
    not represent your location."
- The station forecast is never relabelled as the place's or user's forecast.
- If the place or the user is far outside the covered region, show the nearest
  station with the distance and the warning; do not refuse or fabricate.

## 6. GPS

A "Use my location" button on the Stations screen (list and map views). Geolocation is
requested only when the user presses it, via the browser geolocation API over HTTPS.
Coarse accuracy is sufficient. States to handle, with messages:

- Permission denied: "Location permission denied. Search for a place instead."
- Unavailable: "Location is not available on this device."
- Timeout: "Could not get your location. Try again or search for a place."
- Outside the covered region: show the nearest station, distance and warning.

The user's position is shown on the map. Nothing is persisted, logged or sent.

## 7. Privacy

Nothing leaves the device for place search or GPS. Map tiles are requested from the
tile provider (OpenStreetMap) as already documented in `docs/MAP_TILES.md`. The
following sentence is added to the About screen: "Place search and location stay on
this device; only map tiles are requested from the map provider."

## 8. Localization

New strings in all 10 locales. New glossary terms: nearest station, distance, place,
location. All new terms go into `docs/APP_GLOSSARY.md` before translation.

## 9. Tests required

- Unit tests: haversine distance, nearest station (including ties), search
  normalisation and ranking.
- Widget tests with an injected fake location provider, including denied and timeout
  states.
- Localization parity (all 10 locales carry the new keys).
- Real-browser checks with a simulated location.

## 10. Acceptance criteria

- [x] Gazetteer file loads lazily and search works offline after first load.
- [x] Place search returns grouped results with correct ranking.
- [x] Nearest station and distance shown; warning above the constant.
- [x] "View forecast" opens the correct station.
- [x] Map shows place, station and link.
- [x] GPS button works only on press; denied/unavailable/timeout handled.
- [x] User position shown on map and not persisted.
- [x] All 10 locales carry the new strings.
- [x] `flutter analyze` and `flutter test` green.

### Verification status (2026-11-15)

- `flutter analyze`: no issues. `flutter test`: 89/89. Backend `ruff` + `pytest`: clean.
  Widget coverage now includes the map's place/user marker with its link line to the
  nearest station, "View forecast" from a place card opening that station, and a failed
  place load that is reported and retried on the next query.
- Real browser (MiMo embedded WebView2, `flutter build web --release` served
  locally with the shipped `data/places/`): the app boots on the real gazetteer,
  the hint reads "Search stations or places", and **"Use my location" was driven
  end-to-end with a CDP-simulated position** (−31.42, −64.18): nearest station
  Buenos Aires, 637 km, the 100 km warning, and "View forecast" rendered — the
  same 637.0 km the app's own `nearestStation` returns for that point.
- Place-search typing could not be driven in that WebView2 session: Flutter web
  ignores synthetic DOM/`Input.insertText` text. Grouping and ranking are covered
  by widget tests, and the shipped `data/places/ar.json` was exercised directly
  with the app's Dart code (14,888 places; "cordoba" → Córdoba/Cordoba,
  "la paz" → Entre Rios then Mendoza by population). A typed search in a real
  browser remains unverified; the widget tests stand in for it.


## 11. Risks

- Gazetteer size and download cost on phones.
- Duplicate place names and ambiguous provinces.
- Sparse station coverage (large distances, frequent warnings).
- Permission UX on mobile browsers.
- Keeping the gazetteer current without a runtime service.

## 12. Entry and exit conditions

Entry condition: station map (T35) merged and gazetteer source verified.
Exit condition: acceptance checklist above all checked.
