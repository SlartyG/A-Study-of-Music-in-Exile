#!/usr/bin/env python3
"""
Genius lyrics parser — A Study of Music in Exile

Phase 1: Collect all song metadata via Genius API (~5 min)
Phase 2: Fetch lyrics via Playwright connected to existing Chrome — N parallel tabs

Usage:
  python3 -u parse_lyrics.py                   # Both phases, 4 tabs
  python3 -u parse_lyrics.py --meta            # Phase 1 only
  python3 -u parse_lyrics.py --lyrics          # Phase 2 only, 4 tabs
  python3 -u parse_lyrics.py --lyrics --workers 6   # Phase 2, 6 parallel tabs

How it works:
  - Connects to the already-running Chrome managed by the browse CLI daemon
    (port found automatically via the daemon PID file).
  - Uses the existing browser context which already has Cloudflare clearance —
    no CAPTCHA solving needed at all.
  - N tabs open simultaneously, each processes one song at a time.
  - Every fetched song is written + flushed to songs.jsonl immediately.
  - On restart, already-written song_ids are skipped (resume-safe).
"""

import asyncio
import csv
import json
import random
import re
import subprocess
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
DATA_DIR   = BASE_DIR / "data"
CSV_FILE   = DATA_DIR / "sample_musicians.csv"
META_FILE  = DATA_DIR / "song_list.jsonl"
SONGS_FILE = DATA_DIR / "songs.jsonl"

BROWSE = Path(
    "/Users/aleksandrveselov/.cursor/plugins/cache/cursor-public"
    "/browse/release_v0.2.4/node_modules/.bin/browse"
)
GENIUS_API = "https://api.genius.com"

# ── Helpers ────────────────────────────────────────────────────────────────────
def load_env(key: str) -> str:
    with open(BASE_DIR / ".env") as f:
        for line in f:
            line = line.strip()
            if line.startswith(key + "="):
                return line.split("=", 1)[1]
    raise ValueError(f"{key} not found in .env")


def api_get(endpoint: str, params: dict = None) -> dict:
    token = load_env("GENIUS_ACCESS_TOKEN")
    url = GENIUS_API + endpoint
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}", "User-Agent": "MusicInExile/1.0"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)["response"]


def get_period(components: dict | None, reloc_date: str) -> str:
    if not components or not components.get("year"):
        return "unknown"
    y, m, d = components["year"], components.get("month") or 1, components.get("day") or 1
    return "after" if f"{y:04d}-{m:02d}-{d:02d}" >= reloc_date else "before"


def get_browse_cdp_url(session: str = "default") -> str | None:
    """
    Find the CDP WebSocket URL for the browse daemon's Chrome instance.
    Tries the specified session first, then falls back to any live session.
    Reads the daemon PID file → finds Chrome child process → reads its debug port.
    """
    import tempfile, http.client
    tmp = Path(tempfile.gettempdir())

    def _try_session(sess: str) -> str | None:
        pid_file = tmp / f"browse-{sess}.pid"
        if not pid_file.exists():
            return None
        try:
            daemon_pid = int(pid_file.read_text().strip())
        except (ValueError, OSError):
            return None

        result = subprocess.run(
            ["ps", "-A", "-o", "pid=,ppid=,args="],
            capture_output=True,
        )
        lines = result.stdout.decode("latin-1").split("\n")
        for line in lines:
            parts = line.split(None, 2)
            if len(parts) < 3:
                continue
            pid, ppid, args = parts
            if ppid.strip() != str(daemon_pid):
                continue
            m = re.search(r"--remote-debugging-port=(\d+)", args)
            if not m:
                continue
            port = int(m.group(1))
            try:
                conn = http.client.HTTPConnection("localhost", port, timeout=3)
                conn.request("GET", "/json/version")
                data = json.loads(conn.getresponse().read())
                ws = data.get("webSocketDebuggerUrl")
                if ws:
                    return ws
            except Exception:
                pass
        return None

    # Try requested session first, then any *.pid file
    ws = _try_session(session)
    if ws:
        return ws
    for pid_file in tmp.glob("browse-*.pid"):
        sess = pid_file.stem.replace("browse-", "")
        ws = _try_session(sess)
        if ws:
            print(f"  (using browse session '{sess}' instead of '{session}')")
            return ws
    return None


# ── Phase 1: Collect metadata ──────────────────────────────────────────────────
def load_artists() -> dict:
    artists: dict = {}
    with open(CSV_FILE, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            gid = row["genius_id"].strip()
            if not gid:
                continue
            if gid not in artists:
                artists[gid] = {
                    "genius_id": int(gid),
                    "reloc_date": row["дата_релокации"],
                    "row_ids": [],
                    "pseudonyms": [],
                }
            artists[gid]["row_ids"].append(row["id"])
            artists[gid]["pseudonyms"].append(row["псевдоним"])
    return artists


def collect_metadata():
    artists = load_artists()
    print(f"Phase 1 — collecting metadata for {len(artists)} artists\n")

    done: set[int] = set()
    if META_FILE.exists():
        with open(META_FILE, encoding="utf-8") as f:
            for line in f:
                try:
                    done.add(json.loads(line)["song_id"])
                except Exception:
                    pass
        print(f"  Resuming: {len(done)} songs already in metadata file\n")

    total_new = 0
    with open(META_FILE, "a", encoding="utf-8") as out:
        for gid, meta in artists.items():
            print(f"  [{meta['genius_id']}] {', '.join(meta['pseudonyms'])}")
            page, artist_new = 1, 0
            while True:
                resp = api_get(
                    f"/artists/{meta['genius_id']}/songs",
                    {"per_page": 50, "sort": "release_date", "page": page},
                )
                songs = resp.get("songs", [])
                if not songs:
                    break
                for s in songs:
                    if s["id"] in done:
                        continue
                    record = {
                        "song_id": s["id"],
                        "title": s.get("title", ""),
                        "artist_genius_id": meta["genius_id"],
                        "artist_pseudonyms": meta["pseudonyms"],
                        "csv_row_ids": meta["row_ids"],
                        "reloc_date": meta["reloc_date"],
                        "release_date_components": s.get("release_date_components"),
                        "release_date_for_display": s.get("release_date_for_display"),
                        "period": get_period(s.get("release_date_components"), meta["reloc_date"]),
                        "url": s.get("url", ""),
                        "genius_path": s.get("path", ""),
                    }
                    out.write(json.dumps(record, ensure_ascii=False) + "\n")
                    done.add(s["id"])
                    artist_new += 1
                if len(songs) < 50:
                    break
                page += 1
                time.sleep(0.25)
            print(f"    +{artist_new} new songs")
            total_new += artist_new
            time.sleep(0.3)

    print(f"\nPhase 1 done. Total songs: {len(done)} (+{total_new} new)\n")
    return len(done)


# ── Phase 2: Playwright async lyrics fetcher ───────────────────────────────────
LYRICS_JS = """() => {
    const containers = document.querySelectorAll('[data-lyrics-container="true"]');
    const getText = el => {
        let t = '';
        for (const n of el.childNodes) {
            if (n.nodeName === 'BR') { t += '\\n'; }
            else if (n.nodeType === 3) { t += n.textContent; }
            else if (!['SCRIPT','STYLE','A'].includes(n.nodeName)) { t += getText(n); }
        }
        return t;
    };
    const lyrics = Array.from(containers).map(getText).join('\\n').trim();
    return ({ containers: containers.length, lyrics });
}"""


async def fetch_song(page, url: str, nav_sem: asyncio.Semaphore) -> str | None:
    """
    Fetch lyrics for one URL.

    Uses a shared semaphore to limit simultaneous navigations to Genius.
    "Burrr!" is a genuine Genius 404 — treated as no-lyrics immediately.
    wait_for_selector ensures lyrics are in DOM before we evaluate
    (some pages need a moment for SSR hydration).
    """
    try:
        async with nav_sem:
            await page.goto(url, timeout=20000, wait_until="domcontentloaded")

        title = await page.title()
        if "Burrr" in title or "Page not found" in title:
            return None  # dead URL

        # Wait for lyrics container — fast on SSR pages, skips gracefully on instrumentals
        try:
            await page.wait_for_selector("[data-lyrics-container]", timeout=4000)
        except Exception:
            pass

        result = await page.evaluate(LYRICS_JS)
        if isinstance(result, dict) and result.get("containers", 0) > 0:
            return result.get("lyrics") or None
    except Exception:
        pass
    return None


async def tab_worker(
    worker_id: int,
    context,
    songs: list[dict],
    out_file,
    write_lock: asyncio.Lock,
    stats: dict,
    stats_lock: asyncio.Lock,
    nav_sem: asyncio.Semaphore,
):
    page = await context.new_page()
    # Stagger tab startup slightly
    await asyncio.sleep(worker_id * 0.3)
    try:
        for song in songs:
            url = song.get("url", "")
            lyrics = await fetch_song(page, url, nav_sem) if url else None

            record = {
                **song,
                "has_lyrics": bool(lyrics),
                "lyrics": lyrics,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "worker": worker_id,
            }
            async with write_lock:
                out_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                out_file.flush()

            async with stats_lock:
                stats["done"] += 1
                if lyrics:
                    stats["ok"] += 1
                done_n  = stats["done"]
                total   = stats["total"]
                ok      = stats["ok"]
                elapsed = time.monotonic() - stats["start"]
                rate    = done_n / elapsed if elapsed > 0 else 0.001
                eta     = int((total - done_n) / rate)
                pct     = ok * 100 // done_n if done_n else 0
                print(
                    f"\r  [{done_n:5d}/{total}]  "
                    f"lyrics {ok}/{done_n} ({pct}%)  "
                    f"rate {rate:.1f}/s  "
                    f"ETA {eta//3600}h{(eta%3600)//60:02d}m   ",
                    end="", flush=True,
                )
    finally:
        await page.close()


async def _run_playwright(todo: list[dict], num_workers: int):
    from playwright.async_api import async_playwright

    cdp_url = get_browse_cdp_url("default")
    if not cdp_url:
        print(
            "\nERROR: Could not find running Chrome CDP endpoint.\n"
            "Make sure the browse default session is active (run any browse command first).\n"
        )
        sys.exit(1)

    print(f"  Connecting to Chrome via CDP: {cdp_url[:60]}...")

    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(cdp_url)
        context = browser.contexts[0]  # existing context already has CF clearance

        # Split songs evenly across workers
        n = len(todo)
        chunks = [todo[i::num_workers] for i in range(num_workers)]

        write_lock  = asyncio.Lock()
        stats_lock  = asyncio.Lock()
        # Limit simultaneous navigations. More than ~4 concurrent
        # causes Chrome to slow down per-page rendering significantly.
        nav_sem = asyncio.Semaphore(min(num_workers, 4))
        stats = {
            "done": 0, "ok": 0,
            "total": n,
            "start": time.monotonic(),
        }

        with open(SONGS_FILE, "a", encoding="utf-8") as out_file:
            await asyncio.gather(*(
                tab_worker(wid, context, chunks[wid], out_file, write_lock, stats, stats_lock, nav_sem)
                for wid in range(num_workers)
                if chunks[wid]
            ), return_exceptions=True)

        # Disconnect (does not close the browser we don't own)


def fetch_all_lyrics(num_workers: int = 4):
    if not META_FILE.exists():
        print("No metadata file found. Run Phase 1 first (--meta).")
        sys.exit(1)

    songs: list[dict] = []
    with open(META_FILE, encoding="utf-8") as f:
        for line in f:
            try:
                songs.append(json.loads(line))
            except Exception:
                pass

    done: set[int] = set()
    if SONGS_FILE.exists():
        with open(SONGS_FILE, encoding="utf-8") as f:
            for line in f:
                try:
                    done.add(json.loads(line)["song_id"])
                except Exception:
                    pass

    todo = [s for s in songs if s["song_id"] not in done and s.get("url")]
    total = len(todo)

    if total == 0:
        print("Nothing to do — all songs already processed.")
        return

    effective_par = min(num_workers, 15)
    secs_est = total * 3.0 / effective_par
    print(
        f"Phase 2 — Playwright parallel lyrics fetch\n"
        f"  Songs total : {len(songs)}\n"
        f"  Already done: {len(done)}\n"
        f"  To fetch    : {total}\n"
        f"  Tabs        : {num_workers}\n"
        f"  Est. time   : {int(secs_est)//3600}h {(int(secs_est)%3600)//60}m\n"
    )

    asyncio.run(_run_playwright(todo, num_workers))

    with open(SONGS_FILE, encoding="utf-8") as f:
        final_ok = sum(1 for line in f if json.loads(line).get("has_lyrics"))
    print(f"\n\nPhase 2 done. {final_ok} songs with lyrics → {SONGS_FILE}\n")


# ── Entry point ────────────────────────────────────────────────────────────────
def main():
    args = sys.argv[1:]
    run_meta   = "--lyrics" not in args
    run_lyrics = "--meta"   not in args

    num_workers = 4
    if "--workers" in args:
        idx = args.index("--workers")
        num_workers = int(args[idx + 1])

    DATA_DIR.mkdir(exist_ok=True)

    if run_meta:
        collect_metadata()

    if run_lyrics:
        fetch_all_lyrics(num_workers)

    print("All done.")


if __name__ == "__main__":
    main()
