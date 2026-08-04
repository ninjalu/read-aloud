"""Warren Buffett's Berkshire Hathaway shareholder letters -> a private podcast.

A standalone companion to podcast.py that builds a SEPARATE feed (its own R2
token-prefix, cover and episodes.json) from a local library folder, so it never
touches the iCloud ReadAloud folder or the personal Read Aloud feed.

Pipeline:
  fetch    download every letter (HTML 1977-2003, PDF 2004-2024), extract the
           prose, strip the financial tables, write berkshire/text/YYYY.txt
  sample   quick voice A/B: synth a snippet of one year in several voices
  synth    for each cleaned letter without an MP3, synthesize + register +
           publish incrementally (resumable, oldest-first pubDates)
  publish  rebuild feed.xml and upload to R2 (no synth)

Config: berkshire_config.json next to this file (gitignored - shares the R2
credentials with podcast_config.json but a fresh token = a distinct feed).
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import unicodedata

import trafilatura

import podcast
from tts_core import synth_to_mp3

HERE = os.path.dirname(os.path.abspath(__file__))
LIBRARY = os.path.join(HERE, "berkshire", "audio")
RAW = os.path.join(HERE, "berkshire", "raw")
TEXT = os.path.join(HERE, "berkshire", "text")
CONFIG_PATH = os.path.join(HERE, "berkshire_config.json")

BASE = "https://www.berkshirehathaway.com/letters/"
# year -> source filename on berkshirehathaway.com. .html = web page, .pdf = PDF.
LETTERS = {y: f"{y}.html" for y in range(1977, 2004)}
# 1998-2003 are landing pages; the real letter lives at a PDF whose name varies.
LETTERS.update({y: f"{y}pdf.pdf" for y in range(1998, 2004)})
LETTERS.update({1999: "final1999pdf.pdf", 2003: "2003ltr.pdf"})
LETTERS.update({y: f"{y}ltr.pdf" for y in range(2004, 2025)})


# ---------------------------------------------------------------- config

def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


# ---------------------------------------------------------------- fetch

def _http_get(url: str) -> bytes:
    """Fetch bytes, decompressing per Content-Encoding.

    berkshirehathaway.com sits behind Sucuri, which serves the HTML pages
    Brotli-encoded regardless of Accept-Encoding, so we decode it ourselves.
    """
    import gzip
    import urllib.request
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        "Accept-Encoding": "br, gzip, identity",
    })
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
        enc = (resp.headers.get("Content-Encoding") or "").lower()
    if enc == "br":
        import brotli
        data = brotli.decompress(data)
    elif enc == "gzip":
        data = gzip.decompress(data)
    return data


def fetch_raw(year: int) -> str:
    """Download the source once into berkshire/raw/, return the local path."""
    src = LETTERS[year]
    ext = ".pdf" if src.endswith(".pdf") else ".html"
    dst = os.path.join(RAW, f"{year}{ext}")
    if os.path.exists(dst) and os.path.getsize(dst) > 0:
        return dst
    data = _http_get(BASE + src)
    with open(dst, "wb") as f:
        f.write(data)
    return dst


# ---------------------------------------------------------------- clean

URL_RE = re.compile(r"https?://\S+|www\.\S+")
LEADER_RE = re.compile(r"\.{3,}")           # "......" table leaders
MULTISPACE_RE = re.compile(r" {2,}")


def _strip_emoji(s: str) -> str:
    out = []
    for ch in s:
        cat = unicodedata.category(ch)
        # Drop symbols/other-format/private-use; keep letters, numbers, punct, space.
        if cat.startswith(("So", "Sk", "Cf", "Co", "Cs")):
            continue
        out.append(ch)
    return "".join(out)


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    # Curly quotes / dashes -> plain (em dash -> " - ", house style + reads as a pause).
    text = (text.replace("’", "'").replace("‘", "'")
                .replace("“", '"').replace("”", '"')
                .replace("—", " - ").replace("–", "-")
                .replace("…", "...").replace("\xa0", " "))
    return text


def _alpha_words(line: str) -> int:
    return len(re.findall(r"[A-Za-z]{3,}", line))


COLGAP_RE = re.compile(r"\S {3,}\S")              # internal aligned-column gap


def _is_table_line(line: str) -> bool:
    """True for financial-table rows / leader lines that read as gibberish aloud.

    Deliberately conservative - the old letters are hard-wrapped, so a short
    prose line can carry a big figure ("Operating earnings ... $21,904,000, or
    $22.54 per"). Only drop lines with STRONG tabular structure, and never drop
    a line that reads like a sentence (>=6 real words).
    """
    s = line.strip()
    if not s:
        return False
    if LEADER_RE.search(s):                        # "Revenues ...... 1,234"
        return True
    digits = sum(c.isdigit() for c in s)
    words = _alpha_words(s)
    if digits and words == 0:                      # pure number / symbol row
        return True
    if digits == 0:                                # prose or heading, keep
        return False
    if words >= 6:                                 # reads like a sentence, keep
        return False
    # Aligned columns (multiple values separated by wide gaps) + few words.
    if COLGAP_RE.search(s) and words <= 5:
        return True
    # Number-dominated stub: 1-2 words, mostly digits.
    nonspace = len(s.replace(" ", ""))
    if words <= 2 and digits / max(nonspace, 1) > 0.30:
        return True
    return False


HEADER_JUNK = re.compile(
    r"^\s*(BERKSHIRE HATHAWAY INC\.?|To the Shareholders of Berkshire Hathaway"
    r"|Page \d+|\d+\s*$|[A-Z]\.?-?\d+\s*$)\s*$")


def clean_text(raw_text: str) -> str:
    text = _normalize(_strip_emoji(raw_text))
    text = URL_RE.sub(" ", text)
    kept = []
    for line in text.splitlines():
        if HEADER_JUNK.match(line):
            continue
        if _is_table_line(line):
            continue
        line = MULTISPACE_RE.sub(" ", line).rstrip()
        kept.append(line)
    # Collapse 3+ blank lines to a single paragraph break.
    out = "\n".join(kept)
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    return out


def extract_html(path: str) -> str:
    with open(path, "rb") as f:
        html = f.read()
    txt = trafilatura.extract(
        html, include_comments=False, include_tables=False,
        include_links=False, favor_recall=True)
    if not txt or len(txt) < 500:
        # Fallback: crude tag strip for the very old, sparsely-marked-up pages.
        import html as _html
        raw = html.decode("latin-1", "ignore")
        raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
        raw = re.sub(r"(?s)<[^>]+>", "\n", raw)
        txt = _html.unescape(raw)
    return clean_text(txt)


def extract_pdf(path: str) -> str:
    out = subprocess.run(["pdftotext", "-layout", path, "-"],
                         capture_output=True, text=True, check=True).stdout
    return clean_text(out)


def cmd_fetch(years: list[int]) -> None:
    os.makedirs(RAW, exist_ok=True)
    os.makedirs(TEXT, exist_ok=True)
    for y in years:
        try:
            path = fetch_raw(y)
            txt = extract_pdf(path) if path.endswith(".pdf") else extract_html(path)
            words = len(txt.split())
            with open(os.path.join(TEXT, f"{y}.txt"), "w") as f:
                f.write(txt)
            print(f"  {y}: {words:>6,} words  ({os.path.basename(path)})")
        except Exception as e:  # noqa
            print(f"  {y}: FAILED - {e}")


# ---------------------------------------------------------------- registry

def _pubdate(year: int) -> str:
    """Letters ship in late Feb of the following year -> chronological ordering."""
    return f"{year + 1}-02-28T14:00:00+00:00"


def register(year: int, filename: str, dur: float, description: str,
             voice: str) -> None:
    episodes = podcast.load_registry(LIBRARY)
    episodes = [e for e in episodes if e["filename"] != filename]
    path = os.path.join(LIBRARY, filename)
    episodes.append({
        "filename": filename,
        "title": f"{year} - Berkshire Hathaway Shareholder Letter",
        "duration_sec": round(dur, 1),
        "size_bytes": os.path.getsize(path) if os.path.exists(path) else 0,
        "source_url": BASE + LETTERS[year],
        "description": description,
        "voice": voice,
        "date": _pubdate(year),
    })
    podcast.save_registry(LIBRARY, episodes)


# ---------------------------------------------------------------- synth

def cmd_synth(years: list[int], voice: str, do_publish: bool = True) -> None:
    os.makedirs(LIBRARY, exist_ok=True)
    # "done" = local MP3 still present OR already uploaded to R2 (size on record,
    # local file cleared by cleanup_synced) - so a restart resumes, not repeats.
    done = {e["filename"] for e in podcast.load_registry(LIBRARY)
            if os.path.exists(os.path.join(LIBRARY, e["filename"])) or e.get("size_bytes")}
    for y in years:
        tpath = os.path.join(TEXT, f"{y}.txt")
        if not os.path.exists(tpath):
            print(f"  {y}: no text (run fetch first), skipping")
            continue
        fname = f"berkshire-{y}.mp3"
        if fname in done:
            print(f"  {y}: already synthesized, skipping")
            continue
        with open(tpath) as f:
            text = f.read().strip()
        if not text:
            print(f"  {y}: empty text, skipping")
            continue
        title = f"{y} - Berkshire Hathaway Shareholder Letter"
        out = os.path.join(LIBRARY, fname)
        print(f"  {y}: synthesizing {len(text.split()):,} words -> {fname} ...",
              flush=True)
        try:
            _, dur = synth_to_mp3(text, voice, out, title=title,
                                  author="Warren Buffett")
            register(y, fname, dur, text[:300].strip(), voice)
            print(f"  {y}: done ({dur/60:.1f} min audio)", flush=True)
            if do_publish:
                cmd_publish()
        except Exception as e:  # noqa - keep the batch alive; resume handles it
            print(f"  {y}: FAILED - {e}", flush=True)
            if os.path.exists(out):
                os.remove(out)


# ---------------------------------------------------------------- publish

def cmd_publish() -> None:
    cfg = load_config()
    podcast.scan_library(LIBRARY)
    _ensure_cover()
    podcast.generate_feed(LIBRARY, cfg)
    if podcast.upload_ready(cfg):
        try:
            podcast.upload(LIBRARY, cfg)
            podcast.cleanup_synced(LIBRARY, cfg)
        except Exception as e:  # noqa
            print(f"  ! upload failed: {e}")
    else:
        print("  (no R2 credentials - feed built locally only)")


def _ensure_cover() -> None:
    """Copy the Berkshire cover into the library if present at repo root."""
    src = os.path.join(HERE, "berkshire_cover.jpg")
    dst = os.path.join(LIBRARY, "cover.jpg")
    if os.path.exists(src):
        import shutil
        shutil.copyfile(src, dst)


# ---------------------------------------------------------------- sample

def cmd_sample(year: int, voices: list[str]) -> None:
    """Synth a short snippet of one year in several voices for a quick A/B."""
    tpath = os.path.join(TEXT, f"{year}.txt")
    with open(tpath) as f:
        text = f.read().strip()
    snippet = text[:1500]
    outdir = os.path.join(HERE, "berkshire", "samples")
    os.makedirs(outdir, exist_ok=True)
    for v in voices:
        out = os.path.join(outdir, f"sample_{year}_{v}.mp3")
        _, dur = synth_to_mp3(snippet, v, out, title=f"{year} sample {v}")
        print(f"  {v}: {out}  ({dur:.0f}s)")


# ---------------------------------------------------------------- cli

def parse_years(spec: str) -> list[int]:
    if not spec or spec == "all":
        return sorted(LETTERS)
    out = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return [y for y in out if y in LETTERS]


def main():
    ap = argparse.ArgumentParser(description="Berkshire letters -> private podcast.")
    ap.add_argument("command", choices=["fetch", "synth", "publish", "sample"])
    ap.add_argument("--years", default="all",
                    help="e.g. 1977 | 1977-1985 | 1977,1980,2020 | all")
    ap.add_argument("--voice", default="am_michael",
                    help="Kokoro voice (default am_michael)")
    ap.add_argument("--voices", default="am_michael,bm_lewis,am_adam",
                    help="[sample] comma list of voices to A/B")
    ap.add_argument("--no-publish", action="store_true",
                    help="[synth] skip the per-letter R2 upload")
    args = ap.parse_args()

    if args.command == "fetch":
        cmd_fetch(parse_years(args.years))
    elif args.command == "synth":
        cmd_synth(parse_years(args.years), args.voice,
                  do_publish=not args.no_publish)
    elif args.command == "publish":
        cmd_publish()
    elif args.command == "sample":
        yr = parse_years(args.years)[0]
        cmd_sample(yr, [v.strip() for v in args.voices.split(",")])


if __name__ == "__main__":
    main()
