# Map tiles (T35)

## Provider

OpenStreetMap standard raster tiles, served from `tile.openstreetmap.org`.

- Tile URL template: `https://tile.openstreetmap.org/{z}/{x}/{y}.png`
- Attribution (verbatim, all locales): `© OpenStreetMap contributors`
  linking to `https://www.openstreetmap.org/copyright`.
- "Report a map problem" link: `https://www.openstreetmap.org/fixthemap`.

## Policy (read 2026-11-14)

Source: <https://operations.osmfoundation.org/policies/tiles/> (Tile Usage Policy,
OSMF Operations Working Group). Quoted sentences relied on:

- Attribution requirement: "Provide visible licence attribution, following the
  Attribution Guidelines." / "Show OpenStreetMap licence attribution clearly on
  the map (typically bottom-right)." / "Do not hide attribution beneath UI,
  behind toggles, or off-screen."
- Referer (web only): "Browsers are expected to send a valid `Referer` header."
- Referrer-Policy: "Do not set a restrictive Referrer-Policy that prevents the
  `Referer` header being sent on requests to tile.openstreetmap.org."
- User-Agent: "Send a clear, unique User-Agent string that names your app and
  optionally includes a contact URL or email." / "Browsers will use the browser's
  default `User-Agent`."
- Heavy use: "heavy or inappropriate use harms others' ability to edit and view
  the map. We may block access, without notice, if your usage degrades the
  service."
- Bulk downloading / prefetching: "Bulk downloading is any pre-emptive fetching
  of tiles other than those a user is actively viewing." / "Bulk downloading
  ('scrape') tiles or offer prefetch features." (prohibited) / "Normal
  interactive viewing by a human where the client requests only the tiles needed
  for the current viewport (with modest, short-range look-ahead typical of
  browsers)." (permitted).
- Cache headers: "Honour server caching headers (`Cache-Control`, `Expires`,
  `Etag`). If your cache cannot read them, cache each tile for at least 7 days."
  / "Do not bypass caches. Never send `Cache-Control: no-cache`, `Pragma: no-cache`,
  or similar no-cache headers by default."
- Hard-coding the tile URL: "Avoid hard-coding the tile URL; allow switching
  without needing a software update." (recommended) — implemented via
  `--dart-define=PRISMA_TILE_URL`.
- Report a map problem: "Add a 'Report a map issue' link to
  https://www.openstreetmap.org/fixthemap." (recommended).
- Offline use is not permitted on tile.openstreetmap.org.

## Technical check (2026-11-14)

- `app/web/index.html` declares no `Referrer-Policy` meta tag, so the browser
  sends its default `Referer` (policy satisfied).
- A direct tile request with a `Referer` and a non-generic `User-Agent` returned
  `HTTP/1.1 200 OK`, `Content-Type: image/png`, `Content-Length: 20361`,
  `Access-Control-Allow-Origin: *`, `Cache-Control: max-age=94339, ...`.
  Tile URL used for the check: `https://tile.openstreetmap.org/5/9/21.png`.
- Tile rendering by Flutter web is exercised by the Part 4 browser run (real
  tiles, 200 status, no CORS failure).

## Configuration

Single source of truth: `app/lib/src/map_tiles.dart`
(`kPrismaTileUrlTemplate`, `kPrismaTileAttribution`, `kPrismaTileUserAgent`),
overridable with `--dart-define=PRISMA_TILE_URL=...`. No tile URL is scattered
through widgets. Zoom is limited to 3..10 and rotation is disabled to respect
the policy; no prefetching or bulk loading is performed and the browser's
default caching is left untouched.
