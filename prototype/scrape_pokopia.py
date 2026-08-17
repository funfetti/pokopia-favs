"""
Pokopia data scraper

Scrapes Serebii's Pokemon Pokopia "Favorites" pages, which each list both:
  - the items that carry a given attribute (e.g. "Lots of water")
  - the pokemon that like that attribute

Since every attribute page lists both directions of the relationship, we only
need to hit ~44 pages total (one per attribute) to build the full dataset,
rather than scraping hundreds of individual pokemon/item pages.

Output:
  data/data.json          -- items + pokemon, each tagged with attributes
  data/images/items/*.png -- downloaded item images (served locally, not hotlinked)

Usage:
  pip install requests beautifulsoup4 --break-system-packages
  python scrape_pokopia.py
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://www.serebii.net"
FAVORITES_INDEX = f"{BASE}/pokemonpokopia/favorites.shtml"
FAVORITES_PAGE = f"{BASE}/pokemonpokopia/favorites/{{slug}}.shtml"

OUT_DIR = Path("data")
IMAGES_DIR = OUT_DIR / "images" / "items"
DATA_FILE = OUT_DIR / "data.json"

# Be polite: one request at a time, with a pause between each.
REQUEST_DELAY_SECONDS = 1.5

HEADERS = {
    "User-Agent": "Mozilla/5.0 (personal fan-project data scraper; contact: you@example.com)"
}


def slugify(name: str) -> str:
    """Turn an attribute name like 'Lots of water' into 'lotsofwater',
    matching Serebii's URL scheme. Used both to build fetch URLs and as
    our internal attribute id."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def get_soup(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    time.sleep(REQUEST_DELAY_SECONDS)
    return BeautifulSoup(resp.text, "html.parser")


def get_attribute_names() -> list[str]:
    """Fetch the master list of favorite-attribute names from favorites.shtml."""
    soup = get_soup(FAVORITES_INDEX)

    # The attribute names appear as a flat list of links on the page
    # (e.g. "Lots of water", "Group Activities", "Wobbly stuff", ...).
    # We match links pointing at /pokemonpokopia/favorites/*.shtml
    names = []
    for a in soup.find_all("a", href=True):
        if re.search(r"/pokemonpokopia/favorites/[^/]+\.shtml$", a["href"]):
            text = a.get_text(strip=True)
            if text and text not in names:
                names.append(text)
    return names


def slug_from_href(href: str) -> str:
    """Extract the trailing slug from a serebii href, e.g.
    '/pokemonpokopia/items/whiteboard.shtml' -> 'whiteboard'."""
    return href.rstrip("/").split("/")[-1].replace(".shtml", "")


def download_image(image_url: str, item_slug: str) -> str | None:
    """Download an item image to data/images/items/, skipping if already
    downloaded. Returns the local relative path to store in JSON."""
    if not image_url:
        return None

    ext = Path(image_url).suffix or ".png"
    local_path = IMAGES_DIR / f"{item_slug}{ext}"
    rel_path = f"images/items/{item_slug}{ext}"

    if local_path.exists():
        return rel_path  # already downloaded, don't re-fetch

    try:
        resp = requests.get(image_url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        local_path.write_bytes(resp.content)
        time.sleep(REQUEST_DELAY_SECONDS)
        return rel_path
    except requests.RequestException as e:
        print(f"  ! failed to download image for {item_slug}: {e}")
        return None


def parse_favorites_page(attr_name: str, attr_slug: str, items: dict, pokemon: dict) -> None:
    url = FAVORITES_PAGE.format(slug=attr_slug)
    print(f"Fetching {attr_name} ({url})")
    soup = get_soup(url)

    # --- Items table ---
    # Each item row has: image link, name link (-> item slug), description,
    # category. We find the "List of ... Items" table by locating the
    # heading, then reading the following <table>.
    items_heading = soup.find(
        lambda tag: tag.name in ("h2", "h3") and "Items" in tag.get_text()
    )
    if items_heading:
        table = items_heading.find_next("table")
        if table:
            for row in table.find_all("tr", recursive=False)[1:]:  # skip header row
                cells = row.find_all("td", recursive=False)
                if len(cells) < 3:
                    continue

                name_link = cells[1].find("a")
                if not name_link:
                    continue

                item_slug = slug_from_href(name_link["href"])
                item_name = name_link.get_text(strip=True)

                img_tag = cells[0].find("img")
                image_url = urljoin(BASE, img_tag["src"]) if img_tag else None

                description = cells[2].get_text(strip=True) if len(cells) > 2 else ""

                category = None
                if len(cells) > 3:
                    cat_link = cells[3].find("a")
                    if cat_link:
                        category = cat_link.get_text(strip=True)

                if item_slug not in items:
                    local_image = download_image(image_url, item_slug) if image_url else None
                    items[item_slug] = {
                        "id": item_slug,
                        "name": item_name,
                        "description": description,
                        "category": category,
                        "image": local_image,
                        "attributes": [],
                    }

                if attr_slug not in items[item_slug]["attributes"]:
                    items[item_slug]["attributes"].append(attr_slug)

    # --- Pokemon table ---
    pokemon_heading = soup.find(
        lambda tag: tag.name in ("h2", "h3") and "Pok" in tag.get_text() and "like" in tag.get_text().lower()
    )
    if pokemon_heading:
        table = pokemon_heading.find_next("table")
        if table:
            # Each row has a "Pic" column (image wrapped in a pokedex link,
            # no text) before the "Name" column (same link pattern, but with
            # text) — so among links matching the pokedex-page pattern, take
            # the first one that actually has text, rather than the first
            # match regardless of column.
            pkmn_link_re = re.compile(r"/pokemonpokopia/pokedex/[^/]+\.shtml$")
            for row in table.find_all("tr", recursive=False)[1:]:
                cells = row.find_all("td", recursive=False)
                if len(cells) < 2:
                    continue

                name_link = None
                for cell in cells:
                    for link in cell.find_all("a", href=pkmn_link_re):
                        if link.get_text(strip=True):
                            name_link = link
                            break
                    if name_link:
                        break
                if not name_link:
                    continue

                pkmn_slug = slug_from_href(name_link["href"])
                pkmn_name = name_link.get_text(strip=True)

                if pkmn_slug not in pokemon:
                    pokemon[pkmn_slug] = {
                        "id": pkmn_slug,
                        "name": pkmn_name,
                        "attributes": [],
                    }

                if attr_slug not in pokemon[pkmn_slug]["attributes"]:
                    pokemon[pkmn_slug]["attributes"].append(attr_slug)


def main():
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    print("Fetching attribute list...")
    attribute_names = get_attribute_names()
    print(f"Found {len(attribute_names)} attributes\n")

    items: dict = {}
    pokemon: dict = {}

    for attr_name in attribute_names:
        attr_slug = slugify(attr_name)
        try:
            parse_favorites_page(attr_name, attr_slug, items, pokemon)
        except requests.RequestException as e:
            print(f"  ! failed to fetch {attr_name}: {e}")

    data = {
        "attributes": [
            {"id": slugify(name), "name": name} for name in attribute_names
        ],
        "items": list(items.values()),
        "pokemon": list(pokemon.values()),
    }

    DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"\nDone. {len(items)} items, {len(pokemon)} pokemon written to {DATA_FILE}")
    print(f"Images saved to {IMAGES_DIR}")


if __name__ == "__main__":
    main()
