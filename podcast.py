"""Personal podcast feed for Read Aloud exports.

Turns the folder of exported MP3s into a private podcast: an `episodes.json`
registry, a podcast RSS `feed.xml`, and an upload step that mirrors the lot to
a Cloudflare R2 bucket. Follow the feed URL in Apple Podcasts via
Library -> ... -> "Follow a Show by URL".

Commands:
  python podcast.py init             write a podcast_config.json template
  python podcast.py sync             scan library, rebuild feed, upload
  python podcast.py rebuild          scan library + rebuild feed (no upload)

Config lives in podcast_config.json next to this file (gitignored - it holds
the R2 credentials and the secret feed token). See SETUP_PODCAST.md.
"""
import argparse
import datetime
import email.utils
import json
import mimetypes
import os
import re
import secrets
import shutil
import subprocess
import sys
from urllib.parse import quote
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "podcast_config.json")
COVER_SRC = os.path.join(HERE, "icon_master.png")
REGISTRY = "episodes.json"

FFPROBE = shutil.which("ffprobe") or next(
    (p for p in ("/opt/homebrew/bin/ffprobe", "/usr/local/bin/ffprobe") if os.path.exists(p)),
    "ffprobe",
)


# ---------------------------------------------------------------- config

CONFIG_TEMPLATE = {
    "feed_title": "Lu's Read Aloud",
    "feed_author": "Read Aloud",
    "feed_description": "Private audio feed of articles, read by Kokoro.",
    "token": "",           # secret path segment; `init` fills this in
    "base_url": "",        # e.g. https://pub-xxxxxxxx.r2.dev  (R2 public dev URL, NO trailing slash)
    "bucket": "readaloud",
    "endpoint_url": "",    # e.g. https://<account-id>.r2.cloudflarestorage.com
    "access_key_id": "",
    "secret_access_key": "",
}


def load_config() -> dict | None:
    if not os.path.exists(CONFIG_PATH):
        return None
    with open(CONFIG_PATH) as f:
        return json.load(f)


def upload_ready(cfg: dict | None) -> bool:
    return bool(cfg) and all(
        cfg.get(k) for k in ("token", "base_url", "bucket", "endpoint_url",
                             "access_key_id", "secret_access_key")
    )


def cmd_init() -> None:
    if os.path.exists(CONFIG_PATH):
        print(f"config already exists: {CONFIG_PATH}")
        return
    cfg = dict(CONFIG_TEMPLATE)
    cfg["token"] = secrets.token_urlsafe(16)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)
    print(f"Wrote {CONFIG_PATH}")
    print("Fill in base_url, endpoint_url, access_key_id, secret_access_key")
    print("from your Cloudflare R2 bucket (see SETUP_PODCAST.md).")


# ---------------------------------------------------------------- registry

def default_library() -> str:
    icloud = os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs/ReadAloud")
    return icloud if os.path.isdir(icloud) else os.path.join(HERE, "exports")


def load_registry(library: str) -> list[dict]:
    path = os.path.join(library, REGISTRY)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return []


def save_registry(library: str, episodes: list[dict]) -> None:
    with open(os.path.join(library, REGISTRY), "w") as f:
        json.dump(episodes, f, indent=2, ensure_ascii=False)


def register_episode(library: str, filename: str, title: str,
                     duration_sec: float, source_url: str = "",
                     description: str = "", voice: str = "") -> None:
    """Add (or refresh) one episode in the registry. Called by the export CLI."""
    episodes = load_registry(library)
    episodes = [e for e in episodes if e["filename"] != filename]
    episodes.append({
        "filename": filename,
        "title": title,
        "duration_sec": round(duration_sec, 1),
        "source_url": source_url,
        "description": description,
        "voice": voice,
        "date": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    })
    save_registry(library, episodes)


def probe(path: str) -> tuple[float, str]:
    """Return (duration_sec, id3_title) for an MP3 via ffprobe."""
    out = subprocess.run(
        [FFPROBE, "-v", "quiet", "-print_format", "json",
         "-show_format", path],
        capture_output=True, text=True, check=True,
    ).stdout
    fmt = json.loads(out).get("format", {})
    dur = float(fmt.get("duration", 0))
    title = (fmt.get("tags") or {}).get("title", "")
    return dur, title


def scan_library(library: str) -> list[dict]:
    """Pick up MP3s that aren't in the registry yet (e.g. in-app exports)."""
    episodes = load_registry(library)
    known = {e["filename"] for e in episodes}
    added = 0
    for name in sorted(os.listdir(library)):
        if not name.lower().endswith(".mp3") or name in known:
            continue
        path = os.path.join(library, name)
        try:
            dur, title = probe(path)
        except Exception as e:  # noqa
            print(f"  ! skipping {name}: ffprobe failed ({e})")
            continue
        mtime = datetime.datetime.fromtimestamp(
            os.path.getmtime(path), datetime.timezone.utc)
        episodes.append({
            "filename": name,
            "title": title or re.sub(r"[_-]+", " ", name[:-4]).strip(),
            "duration_sec": round(dur, 1),
            "source_url": "",
            "description": "",
            "voice": "",
            "date": mtime.isoformat(),
        })
        added += 1
    # drop registry entries whose file has gone
    episodes = [e for e in episodes
                if os.path.exists(os.path.join(library, e["filename"]))]
    save_registry(library, episodes)
    if added:
        print(f"  + registered {added} new MP3(s) from the library folder")
    return episodes


# ---------------------------------------------------------------- feed

def _rfc822(iso: str) -> str:
    dt = datetime.datetime.fromisoformat(iso)
    return email.utils.format_datetime(dt)


def _hms(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def generate_feed(library: str, cfg: dict) -> str:
    """Write feed.xml into the library folder; return its path."""
    episodes = sorted(load_registry(library), key=lambda e: e["date"], reverse=True)
    base = cfg["base_url"].rstrip("/") + "/" + cfg["token"] if cfg.get("base_url") \
        else "https://example.invalid/feed"
    title = escape(cfg.get("feed_title", "Read Aloud"))
    author = escape(cfg.get("feed_author", "Read Aloud"))
    desc = escape(cfg.get("feed_description", ""))
    now = email.utils.format_datetime(
        datetime.datetime.now(datetime.timezone.utc))

    items = []
    for e in episodes:
        url = f"{base}/audio/{quote(e['filename'])}"
        size = os.path.getsize(os.path.join(library, e["filename"]))
        body = escape(e.get("description") or e.get("source_url") or e["title"])
        link = escape(e.get("source_url") or base)
        items.append(f"""    <item>
      <title>{escape(e["title"])}</title>
      <guid isPermaLink="false">{escape(e["filename"])}</guid>
      <pubDate>{_rfc822(e["date"])}</pubDate>
      <link>{link}</link>
      <description>{body}</description>
      <enclosure url="{escape(url)}" length="{size}" type="audio/mpeg"/>
      <itunes:duration>{_hms(e["duration_sec"])}</itunes:duration>
    </item>""")

    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>{title}</title>
    <link>{escape(base)}</link>
    <language>en</language>
    <description>{desc}</description>
    <lastBuildDate>{now}</lastBuildDate>
    <itunes:author>{author}</itunes:author>
    <itunes:image href="{escape(base + '/cover.jpg')}"/>
    <itunes:explicit>false</itunes:explicit>
    <itunes:block>Yes</itunes:block>
{os.linesep.join(items)}
  </channel>
</rss>
"""
    path = os.path.join(library, "feed.xml")
    with open(path, "w") as f:
        f.write(feed)
    print(f"  feed.xml written ({len(episodes)} episode(s))")
    return path


def ensure_cover(library: str) -> str | None:
    """Create cover.jpg (1400x1400) in the library from the app icon."""
    dst = os.path.join(library, "cover.jpg")
    if os.path.exists(dst) or not os.path.exists(COVER_SRC):
        return dst if os.path.exists(dst) else None
    try:
        subprocess.run(
            ["sips", "-z", "1400", "1400", "-s", "format", "jpeg",
             COVER_SRC, "--out", dst],
            check=True, capture_output=True)
        return dst
    except Exception as e:  # noqa
        print(f"  ! cover art skipped: {e}")
        return None


# ---------------------------------------------------------------- upload

def upload(library: str, cfg: dict) -> None:
    """Mirror feed.xml, cover.jpg and registered MP3s to the R2 bucket."""
    import boto3  # deferred: only needed once credentials exist

    s3 = boto3.client(
        "s3",
        endpoint_url=cfg["endpoint_url"],
        aws_access_key_id=cfg["access_key_id"],
        aws_secret_access_key=cfg["secret_access_key"],
        region_name="auto",
    )
    prefix = cfg["token"]
    existing = set()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=cfg["bucket"], Prefix=prefix + "/"):
        existing.update(o["Key"] for o in page.get("Contents", []))

    def put(local: str, key: str, always: bool = False):
        if not always and key in existing:
            return False
        ctype = mimetypes.guess_type(local)[0] or "application/octet-stream"
        if local.endswith(".xml"):
            ctype = "application/rss+xml"
        s3.upload_file(local, cfg["bucket"], key,
                       ExtraArgs={"ContentType": ctype})
        return True

    sent = 0
    for e in load_registry(library):
        if put(os.path.join(library, e["filename"]),
               f"{prefix}/audio/{e['filename']}"):
            sent += 1
            print(f"  ^ uploaded {e['filename']}")
    cover = os.path.join(library, "cover.jpg")
    if os.path.exists(cover):
        put(cover, f"{prefix}/cover.jpg", always=True)
    put(os.path.join(library, "feed.xml"), f"{prefix}/feed.xml", always=True)
    print(f"  ^ feed.xml uploaded ({sent} new episode(s))")
    print(f"\nFeed URL:  {cfg['base_url'].rstrip('/')}/{prefix}/feed.xml")


# ---------------------------------------------------------------- publish

def publish(library: str | None = None) -> None:
    """Scan -> feed -> upload. Safe to call after every export."""
    library = library or default_library()
    cfg = load_config() or dict(CONFIG_TEMPLATE)
    scan_library(library)
    ensure_cover(library)
    generate_feed(library, cfg)
    if upload_ready(cfg):
        try:
            upload(library, cfg)
        except Exception as e:  # noqa
            print(f"  ! upload failed: {e}")
    else:
        print("  (no R2 credentials in podcast_config.json - feed built "
              "locally only; see SETUP_PODCAST.md)")


def main():
    ap = argparse.ArgumentParser(description="Private podcast feed for Read Aloud.")
    ap.add_argument("command", choices=["init", "sync", "rebuild", "add"])
    ap.add_argument("--library", default=None, help="MP3 folder (default: iCloud ReadAloud)")
    ap.add_argument("--file", default="", help="[add] MP3 in the library to register + publish")
    ap.add_argument("--title", default="", help="[add] episode title (defaults to the MP3 ID3 title)")
    ap.add_argument("--url", default="", help="[add] source article URL to record on the episode")
    ap.add_argument("--voice", default="", help="[add] voice used, for the episode record")
    args = ap.parse_args()

    if args.command == "init":
        cmd_init()
        return

    library = args.library or default_library()
    os.makedirs(library, exist_ok=True)
    print(f"Library: {library}")
    if args.command == "rebuild":
        cfg = load_config() or dict(CONFIG_TEMPLATE)
        scan_library(library)
        ensure_cover(library)
        generate_feed(library, cfg)
    elif args.command == "add":
        # Register ONE just-exported file with its source URL, then publish. Used by
        # the app's "Export MP3" so an in-app export lands in the feed in one step,
        # source link intact (the plain folder-sweep in `sync` can't know the URL).
        if not args.file:
            ap.error("add requires --file")
        path = args.file if os.path.isabs(args.file) else os.path.join(library, args.file)
        if not os.path.exists(path):
            ap.error(f"file not found: {path}")
        dur, id3_title = probe(path)
        register_episode(library, os.path.basename(path),
                         args.title or id3_title or os.path.basename(path),
                         dur, source_url=args.url, voice=args.voice)
        publish(library)
    else:  # sync
        publish(library)


if __name__ == "__main__":
    main()
