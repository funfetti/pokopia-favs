# Pokopia Favorite Item Matcher — project notes

A personal webapp for Pokémon Pokopia (the Switch 2 life-sim spinoff). Pick a
pokémon, see which items it would like, based on shared attribute tags
(e.g. Magikarp likes "Lots of water" → any item tagged "Lots of water" is a
match, ranked by how many attributes are shared).

**Live site:** https://funfetti.github.io/pokopia-favs/
**GitHub repo:** https://github.com/funfetti/pokopia-favs (public)

## Architecture — deliberately simple, no backend

1. `docs/scrape_pokopia.py` — Python scraper (requests + BeautifulSoup).
   Scrapes Serebii's Pokopia "Favorites" pages, each of which lists both the
   items with a given attribute AND the pokémon that like it — so only ~43
   pages are needed (one per attribute) instead of hundreds of individual
   item/pokémon pages. Writes `docs/data/data.json` + downloads images.
2. `docs/index.html` — static HTML/JS webapp. `fetch('data/data.json')`,
   filter/sort/render client-side. No server, no build step, no framework.

`docs/` (not `prototype/`, which it used to be called) is the GitHub Pages
publish root — Pages only serves from a branch root or `/docs`, not an
arbitrary path, so everything the site needs lives there. The repo root also
has `venv/` (gitignored) and `.claude/launch.json` (local dev preview config).

## Current data state

- **43 attributes, 715 items, 366 pokémon**, all scraped from the live site.
- All 715 item images and all 366 pokémon sprite images downloaded locally
  to `docs/data/images/items/` and `docs/data/images/pokemon/`.
- Each pokémon has an `id`, `name`, `habitat` (ideal habitat, e.g. "Dark"),
  `image`, and `attributes` (list of attribute ids it favorites).
- Each item has `id`, `name`, `description`, `category`, `image`, and
  `attributes` (list of attribute ids it carries).

### Known data caveat: `category` is actually Serebii's "Tag" field

Individual Serebii item pages have both a **Category** (e.g. "Furniture")
and a **Tag** (e.g. "Decoration") field. The favorites pages we scrape only
expose the Tag, not the real Category — so what we call `item.category`
throughout the codebase is really the Tag. Getting the real Category would
mean scraping all ~715 individual item pages separately (not done — flagged
as a comment in `scrape_pokopia.py` near the extraction code). Raw tag
values found: `Decoration` (222), `Toy` (140), `Relaxation` (78), `Road` (8),
and 267 items with no tag at all (genuinely empty on Serebii's own page, not
a scraper bug — verified against live HTML).

The app collapses these into 5 filter categories: **Toy, Decoration,
Relaxation, Small Lost Relic, Other** (Other = Road + untagged items).
"Small Lost Relic" is a manual override — see below.

### Small Lost Relic tagging

`scrape_pokopia.py` has `apply_small_lost_relic_category()`, called at the
end of `main()`. It scrapes `lostrelics.shtml` (Large/Sunken-Large/Small
relic sections all live in **one shared table** with inline `<h3>`
section-header rows, not separate tables — easy to get wrong) and overrides
`category` to `"Small Lost Relic"` for matching item names. Currently 34 of
the 46 small-relic item names match something in our dataset; the other 12
aren't tagged as a favorite by any pokémon on any of the 43 attribute pages,
so they don't exist in `data.json` at all and can never appear in the app
regardless of category (the app only shows items sharing an attribute with
the selected pokémon).

## Scraper usage

```bash
cd docs
source ../venv/bin/activate
python3 scrape_pokopia.py                # full scrape incl. images
python3 scrape_pokopia.py --skip-images   # data.json only, much faster
                                           # (~4 min vs ~70-80 min); rerun
                                           # later without the flag to
                                           # backfill images — already-
                                           # downloaded ones are skipped
```

`REQUEST_DELAY_SECONDS = 5` (polite delay between every request, set per
user request — was 1.5s originally). A full image scrape is slow: ~43 page
fetches + ~1080 image downloads, all serialized with the delay.

Local Python is 3.9 (system default on this Mac), so the script uses
`from __future__ import annotations` to allow modern `X | None` type hints
without requiring 3.10+.

## Local dev / testing

The app needs a real HTTP server — opening `index.html` via `file://`
fails because browsers block `fetch()` on local files (this bit us
repeatedly early on).

```bash
cd docs
python3 -m http.server 8791
# open http://localhost:8791/
```

Note: `preview_start`'s own process-spawn sandbox couldn't access this
project directory (unrelated permission error) — running the server
directly via Bash and attaching `preview_start` to the already-running
`http://localhost:8791` URL is the workaround in use.

## Git / GitHub state

- Repo-local git identity is set to `funfetti <20848423+funfetti@users.noreply.github.com>`
  (global git config elsewhere still says "Stephanie Ho" — deliberately not
  touched). All commit history was rewritten early on to scrub the real name
  before the first push (safe to do since nothing had been pushed yet).
- `gh` CLI is authenticated as `funfetti` over HTTPS.
- Pages source: `main` branch, `/docs` folder ("Deploy from a branch", no
  Actions workflow needed).
- GitHub's Pages API occasionally 503s transiently (both on `gh repo create`
  and on deployment) — not a real outage, just retry (an empty commit + push
  is a reliable way to force a fresh deployment attempt if `gh run rerun`
  itself 503s).
- **As of the last session, commit `d7f01a4` is local-only, not yet pushed.**
  Check `git log origin/main..main` / `git status` to see if that's still
  true.

## Feature history (roughly chronological)

- Core matcher UI: type-to-filter pokémon search, matched items ranked by
  shared-attribute count, colored attribute pills/tags.
- Header image (`pokopia-fav-header.png`, user-supplied), dark purple theme,
  light-blue/light-purple link colors.
- Category filter: multiselect dropdown with a "select all" checkbox
  (right-aligned above the item list).
- Real data pipeline: small 2-page test scrape → full 43-page scrape →
  full image scrape (items then pokémon sprites added in a follow-up).
- Ideal habitat display, Serebii deep links (attribute pills → favorites
  page, pokémon image → pokedex page, item image → item page), all
  `target="_blank"`.
- Dynamic per-attribute colors (hash id → HSL) replacing an 11-entry
  hand-picked map that left most of the 43 real attributes gray.
- Restructured `prototype/` → `docs/` + `pokopia_matcher_demo.html` →
  `index.html` for GitHub Pages.
- Pushed to GitHub, Pages enabled, verified live.
- Mobile fixes: added missing `<html>/<head>` + viewport meta tag (root
  cause of "tiny" rendering — page had no doctype/head at all before this),
  ~35-40% font-size bump across the board.
- Category cleanup (Other bucket) + Small Lost Relic tagging (this session).

## Open items / possible next steps

- Push `d7f01a4` (and anything after) to GitHub.
- A sort-by-category feature was discussed then explicitly retracted by the
  user — not implemented, don't assume it's wanted unless asked again.
- Real Category field (vs. current Tag-as-category) would need scraping all
  715 individual item pages — not done, flagged as a known gap.
- 12 Small Lost Relic items exist on Serebii but not in our dataset (no
  favorited-by relationship captured on the 43 attribute pages).
