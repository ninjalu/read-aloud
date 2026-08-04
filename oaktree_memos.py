"""Howard Marks / Oaktree memos -> a private podcast, one episode per year.

Companion to podcast.py and berkshire_letters.py: a SEPARATE feed (own R2
token, cover, episodes.json) built from Oaktree's single "Complete Collection"
PDF (~1,640 pages, ~160 memos, 1990-2025). The collection is split on each
memo's "From: ... Marks" header, each memo is dated by the dates in its header
(carried forward across the strictly-chronological sequence), and memos are
grouped into one episode per calendar year.

Pipeline:
  fetch    download the complete-collection PDF into oaktree/raw/
  split    pdftotext -> detect memos -> assign years -> write oaktree/text/YYYY.txt
  synth    synth every year without an MP3, register + publish incrementally
  publish  rebuild feed.xml + upload to R2
  sample   quick voice A/B on one year

Config: oaktree_config.json next to this file (gitignored; shares the R2
credentials with the other feeds but a fresh token = a distinct podcast).
"""
import argparse
import json
import os
import re
import subprocess
from collections import Counter

import podcast
from berkshire_letters import clean_text, _http_get
from tts_core import synth_to_mp3

HERE = os.path.dirname(os.path.abspath(__file__))
LIBRARY = os.path.join(HERE, "oaktree", "audio")
RAW = os.path.join(HERE, "oaktree", "raw")
TEXT = os.path.join(HERE, "oaktree", "text")
CONFIG_PATH = os.path.join(HERE, "oaktree_config.json")

PDF_URL = ("https://www.oaktreecapital.com/docs/default-source/memos/"
           "the-complete-collection.pdf?sfvrsn=58102966_5")

MONTHS = ("January|February|March|April|May|June|July|August|September"
          "|October|November|December")
DATE_RE = re.compile(rf"({MONTHS})\s+(?:\d{{1,2}},\s+)?((?:19|20)\d{{2}})", re.I)
FROM_RE = re.compile(r"from:\s*howard.*marks", re.I)
MEMO_TO_RE = re.compile(r"^\s*(memo to:|to:)\s*(oaktree|tcw|clients)", re.I)
RE_TITLE_RE = re.compile(r"^\s*(?:re|subject):\s*(.+?)\s*$", re.I)
HEADER_LINE_RE = re.compile(
    r"^\s*(memo to:|to:|from:|date:|re:|subject:|table of contents)", re.I)
YEAR_ONLY_RE = re.compile(r"^\s*(19|20)\d{2}\s*$")
# Running page line "<year> Oaktree Capital Management, L.P.  <n>  All Rights
# Reserved" - repeats on every page; the year is the authoritative memo year.
COPYRIGHT_RE = re.compile(r"((?:19|20)\d{2})\s+Oaktree Capital Management", re.I)
BOILER_RE = re.compile(r"oaktree capital management|all rights reserved", re.I)
DISCLAIMER_RE = re.compile(r"this memorandum expresses the views", re.I)


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


# ---------------------------------------------------------------- fetch

def cmd_fetch() -> None:
    os.makedirs(RAW, exist_ok=True)
    dst = os.path.join(RAW, "collection.pdf")
    if os.path.exists(dst) and os.path.getsize(dst) > 1_000_000:
        print(f"  already downloaded: {dst} ({os.path.getsize(dst):,} bytes)")
        return
    print("  downloading complete-collection PDF ...")
    with open(dst, "wb") as f:
        f.write(_http_get(PDF_URL))
    print(f"  saved {dst} ({os.path.getsize(dst):,} bytes)")


# ---------------------------------------------------------------- split

def _memo_title(chunk: list[str]) -> str:
    for ln in chunk[:20]:
        m = RE_TITLE_RE.match(ln)
        if m and len(m.group(1)) > 1:
            return re.sub(r"\s+", " ", m.group(1)).strip(" .")
    return "Untitled memo"


def _memo_year(scan_lines: list[str], prev: int) -> int:
    """Year from the per-page copyright line (authoritative); fall back to the
    first header/footer date, then to the previous memo's year."""
    yrs = [int(m.group(1)) for m in COPYRIGHT_RE.finditer("\n".join(scan_lines))]
    yrs = [y for y in yrs if 1990 <= y <= 2026]
    if yrs:
        return Counter(yrs).most_common(1)[0][0]
    for pool in (scan_lines[:15], scan_lines[-15:], scan_lines):
        ds = [int(m.group(2)) for m in DATE_RE.finditer("\n".join(pool))]
        ds = [y for y in ds if 1990 <= y <= 2026]
        if ds:
            return ds[0]
    return prev


def _spoken(chunk: list[str], title: str) -> str:
    """Drop headers, page boilerplate and the trailing legal disclaimer; lead
    with a spoken memo title."""
    body = []
    for ln in chunk:
        if DISCLAIMER_RE.search(ln):        # end-of-collection legalese -> stop
            break
        if HEADER_LINE_RE.match(ln) or YEAR_ONLY_RE.match(ln):
            continue
        if BOILER_RE.search(ln):            # "<yr> Oaktree Capital Management ..."
            continue
        if re.match(r"^\s*Howard\s+S?\.?\s*Marks\s*$", ln, re.I):
            continue
        body.append(ln)
    cleaned = clean_text("\n".join(body))
    return f"Memo: {title}.\n\n{cleaned}"


def cmd_split() -> None:
    os.makedirs(TEXT, exist_ok=True)
    pdf = os.path.join(RAW, "collection.pdf")
    if not os.path.exists(pdf):
        print("  no PDF - run fetch first"); return
    print("  extracting text (pdftotext -layout) ...")
    raw = subprocess.run(["pdftotext", "-layout", pdf, "-"],
                         capture_output=True, text=True, check=True).stdout
    lines = raw.splitlines()

    # Memo boundaries = "From: ... Marks" lines; skip the 2 front-matter blocks
    # (the cover and the anthology intro). Extend each boundary up to the memo's
    # "Memo to:" preamble so the header (and its date) rides with the right memo.
    froms = [i for i, l in enumerate(lines) if FROM_RE.search(l)]
    froms = froms[2:]
    starts = []
    for fi in froms:
        b = fi
        for j in range(fi - 1, max(fi - 6, -1), -1):
            if MEMO_TO_RE.match(lines[j]):
                b = j
                break
        starts.append(b)
    starts.append(len(lines))

    prev, memos = 1990, []
    for k in range(len(starts) - 1):
        chunk = lines[starts[k]:starts[k + 1]]
        # Scan a few lines earlier too: a memo's first-page copyright line sits
        # just above its "Memo to:" header.
        scan = lines[max(starts[k] - 3, 0):starts[k + 1]]
        title = _memo_title(chunk)
        year = _memo_year(scan, prev)
        prev = year
        memos.append((year, title, _spoken(chunk, title)))

    # Group by year -> one text file + a titles manifest per year.
    by_year: dict[int, list] = {}
    for year, title, text in memos:
        by_year.setdefault(year, []).append((title, text))

    manifest = {}
    for year in sorted(by_year):
        items = by_year[year]
        body = "\n\n\n".join(t for _, t in items)
        with open(os.path.join(TEXT, f"{year}.txt"), "w") as f:
            f.write(body)
        manifest[year] = [t for t, _ in items]
    with open(os.path.join(TEXT, "_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\n  {len(memos)} memos across {len(by_year)} years:")
    for year in sorted(by_year):
        words = len(open(os.path.join(TEXT, f"{year}.txt")).read().split())
        print(f"    {year}: {len(by_year[year]):>2} memo(s), {words:>6,} words")


# ---------------------------------------------------------------- registry

def _load_manifest() -> dict:
    p = os.path.join(TEXT, "_manifest.json")
    return json.load(open(p)) if os.path.exists(p) else {}


def register(year: int, filename: str, dur: float, titles: list[str],
             voice: str) -> None:
    episodes = podcast.load_registry(LIBRARY)
    episodes = [e for e in episodes if e["filename"] != filename]
    path = os.path.join(LIBRARY, filename)
    desc = f"Howard Marks memos from {year}: " + "; ".join(titles) + "."
    episodes.append({
        "filename": filename,
        "title": f"{year} - Howard Marks Memos",
        "duration_sec": round(dur, 1),
        "size_bytes": os.path.getsize(path) if os.path.exists(path) else 0,
        "source_url": "https://www.oaktreecapital.com/insights/memos",
        "description": desc,
        "voice": voice,
        "date": f"{year}-06-30T12:00:00+00:00",
    })
    podcast.save_registry(LIBRARY, episodes)


# ---------------------------------------------------------------- synth

def cmd_synth(years: list[int], voice: str, do_publish: bool = True) -> None:
    os.makedirs(LIBRARY, exist_ok=True)
    manifest = _load_manifest()
    # "done" = local MP3 present OR already on R2 (size recorded) -> resumable.
    done = {e["filename"] for e in podcast.load_registry(LIBRARY)
            if os.path.exists(os.path.join(LIBRARY, e["filename"])) or e.get("size_bytes")}
    avail = sorted(int(y) for y in manifest) if not years else years
    for y in avail:
        tpath = os.path.join(TEXT, f"{y}.txt")
        if not os.path.exists(tpath):
            print(f"  {y}: no text (run split first), skipping"); continue
        fname = f"oaktree-{y}.mp3"
        if fname in done:
            print(f"  {y}: already synthesized, skipping"); continue
        text = open(tpath).read().strip()
        if not text:
            print(f"  {y}: empty, skipping"); continue
        titles = manifest.get(str(y), [])
        out = os.path.join(LIBRARY, fname)
        print(f"  {y}: synthesizing {len(titles)} memo(s), "
              f"{len(text.split()):,} words -> {fname} ...", flush=True)
        try:
            _, dur = synth_to_mp3(text, voice, out,
                                  title=f"{y} - Howard Marks Memos",
                                  author="Howard Marks")
            register(y, fname, dur, titles, voice)
            print(f"  {y}: done ({dur/60:.1f} min)", flush=True)
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
    src = os.path.join(HERE, "oaktree_cover.jpg")
    dst = os.path.join(LIBRARY, "cover.jpg")
    if os.path.exists(src):
        import shutil
        shutil.copyfile(src, dst)


# ---------------------------------------------------------------- sample

def cmd_sample(year: int, voices: list[str]) -> None:
    text = open(os.path.join(TEXT, f"{year}.txt")).read().strip()[:1500]
    outdir = os.path.join(HERE, "oaktree", "samples")
    os.makedirs(outdir, exist_ok=True)
    for v in voices:
        out = os.path.join(outdir, f"sample_{year}_{v}.mp3")
        _, dur = synth_to_mp3(text, v, out, title=f"{year} sample {v}")
        print(f"  {v}: {out}  ({dur:.0f}s)")


# ---------------------------------------------------------------- cli

def parse_years(spec: str) -> list[int]:
    if not spec or spec == "all":
        return []
    out = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-"); out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def main():
    ap = argparse.ArgumentParser(description="Oaktree memos -> private podcast.")
    ap.add_argument("command", choices=["fetch", "split", "synth", "publish", "sample"])
    ap.add_argument("--years", default="all", help="e.g. 1990 | 1990-1995 | all")
    ap.add_argument("--voice", default="am_michael")
    ap.add_argument("--voices", default="am_michael,am_eric,bm_lewis")
    ap.add_argument("--no-publish", action="store_true")
    args = ap.parse_args()

    if args.command == "fetch":
        cmd_fetch()
    elif args.command == "split":
        cmd_split()
    elif args.command == "synth":
        cmd_synth(parse_years(args.years), args.voice,
                  do_publish=not args.no_publish)
    elif args.command == "publish":
        cmd_publish()
    elif args.command == "sample":
        cmd_sample(parse_years(args.years)[0], [v.strip() for v in args.voices.split(",")])


if __name__ == "__main__":
    main()
