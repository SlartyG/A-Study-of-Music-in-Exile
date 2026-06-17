#!/usr/bin/env python3
"""
Fetch artist photos from Wikipedia (Wikimedia Commons).
CC-licensed images, suitable for non-commercial research with attribution.
Saves to web/public/images/ and updates artists_meta.json.

Uses curl for HTTP requests (Python SSL cert verification fails on this machine).
"""

import json, os, time, re, subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "../web/public/images")
ARTISTS_JSON = os.path.join(BASE_DIR, "../web/public/data/artists_meta.json")

WIKI_TITLES = {
    "Noize MC":           ("ru", "Noize MC"),
    "Oxxxymiron":         ("ru", "Oxxxymiron"),
    "Лу (Louna)":         ("ru", "Louna"),
    "Монеточка":          ("ru", "Монеточка"),
    "Анастасия Креслина": ("en", "IC3PEAK"),
    "FACE":               ("en", "FACE (rapper)"),
    "Земфира":            ("ru", "Земфира"),
    "Шура Би-2":          ("ru", "Би-2 (группа)"),
    "Арсений Морозов":    None,
    "Айгель Гайсина":     ("ru", "Айгель Гайсина"),
    "Моргенштерн":        ("en", "Morgenshtern (rapper)"),
    "Кирилл Иванов":      ("ru", "СБПЧ"),
    "Гречка":             ("ru", "Гречка (певица)"),
    "Борис Гребенщиков":  ("ru", "Борис Гребенщиков"),
    "Максим Покровский":  ("ru", "Покровский, Максим Сергеевич"),
    "Максим Леонидов":    ("ru", "Леонидов, Максим Леонидович"),
    "Вера Мусаелян":      ("ru", "АлоэВера"),
    "Вася Обломов":       ("ru", "Вася Обломов"),
    "Виктор Ужаков":      ("en", "Ploho"),
    "Kate NV":            ("en", "Kate NV"),
    "Ushko":              None,
}

UA = "MusicExileResearch/1.0 (non-commercial academic project)"


def curl_get_json(url: str) -> dict | None:
    """Fetch JSON via curl (bypasses Python SSL cert issues)."""
    try:
        result = subprocess.run(
            ["curl", "-s", "-k", "--max-time", "12",
             "-A", UA, url],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        return json.loads(result.stdout)
    except Exception as e:
        print(f"\n  curl error: {e}", end="")
        return None


def curl_download(url: str, dest: str) -> bool:
    """Download file via curl."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        result = subprocess.run(
            ["curl", "-s", "-k", "--max-time", "20",
             "-A", UA, "-o", dest, url],
            capture_output=True, timeout=25
        )
        return result.returncode == 0 and os.path.exists(dest) and os.path.getsize(dest) > 500
    except Exception as e:
        print(f"\n  curl download error: {e}", end="")
        return False


def fetch_thumb_url(lang: str, title: str) -> str | None:
    import urllib.parse
    encoded = urllib.parse.quote(title.replace(" ", "_"), safe="")
    data = curl_get_json(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{encoded}")
    if not data:
        return None
    thumb = data.get("thumbnail") or data.get("originalimage")
    if thumb:
        return thumb["source"]
    return None


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(ARTISTS_JSON, encoding="utf-8") as f:
        artists = json.load(f)

    found = {}
    missing = []

    for idx, artist in enumerate(artists):
        pseudo = artist["pseudonym"]
        entry = WIKI_TITLES.get(pseudo, "MISSING")

        if entry == "MISSING":
            print(f"[WARN] {pseudo} not in map")
            missing.append(pseudo)
            continue

        if entry is None:
            print(f"[{idx:02d}] {pseudo:30s} — no Wikipedia page, skipping")
            missing.append(pseudo)
            continue

        lang, title = entry
        print(f"[{idx:02d}] {pseudo:30s} ", end="", flush=True)

        img_url = fetch_thumb_url(lang, title)
        if not img_url:
            print("no thumbnail")
            missing.append(pseudo)
            time.sleep(0.5)
            continue

        ext = img_url.rsplit(".", 1)[-1].split("?")[0].lower()
        if ext not in ("jpg", "jpeg", "png", "webp"):
            ext = "jpg"

        # Unique filename: index-based to avoid Cyrillic slug collisions
        fname = f"artist_{idx:02d}.{ext}"
        dest = os.path.join(OUTPUT_DIR, fname)

        if os.path.exists(dest) and os.path.getsize(dest) > 500:
            print(f"cached  {fname}")
            found[pseudo] = f"/images/{fname}"
            time.sleep(0.1)
            continue

        ok = curl_download(img_url, dest)
        if ok:
            kb = os.path.getsize(dest) // 1024
            print(f"✓  {fname}  ({kb} KB)")
            found[pseudo] = f"/images/{fname}"
        else:
            print("download failed")
            missing.append(pseudo)

        time.sleep(0.5)

    print("\n" + "=" * 60)
    print(f"Downloaded: {len(found)}/{len(artists)}")
    if missing:
        print(f"Missing ({len(missing)}): {', '.join(missing)}")

    # Patch artists_meta.json
    updated = 0
    for artist in artists:
        p = found.get(artist["pseudonym"])
        if p:
            if artist.get("photo") != p:
                artist["photo"] = p
                updated += 1
        else:
            artist.pop("photo", None)

    with open(ARTISTS_JSON, "w", encoding="utf-8") as f:
        json.dump(artists, f, ensure_ascii=False, indent=2)

    print(f"Updated artists_meta.json (+{updated} photo paths).")


if __name__ == "__main__":
    main()
