"""Batch-export web articles to MP3 in a Kokoro voice.

Examples:
  ./export https://example.com/article
  ./export url1 url2 url3 --voice bm_george
  ./export --file urls.txt --out ~/Desktop/listening
"""
import argparse
import os
import re
import sys

import trafilatura

from tts_core import synth_to_mp3


def default_outdir() -> str:
    """Prefer an iCloud Drive folder (auto-syncs to the iPhone Files app)."""
    icloud_root = os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs")
    base = os.path.join(icloud_root, "ReadAloud") if os.path.isdir(icloud_root) \
        else os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")
    os.makedirs(base, exist_ok=True)
    return base


def safe_name(s: str) -> str:
    s = re.sub(r"[^\w\s-]", "", s).strip()[:80]
    return re.sub(r"\s+", "_", s) or "article"


def fetch_article(url: str):
    html = trafilatura.fetch_url(url)
    if not html:
        return None, None
    text = trafilatura.extract(html, include_comments=False, include_tables=False)
    meta = trafilatura.extract_metadata(html)
    title = (meta.title if meta and meta.title else None) or "Article"
    return title, text


def main():
    ap = argparse.ArgumentParser(description="Export web articles to MP3 (Kokoro TTS).")
    ap.add_argument("urls", nargs="*", help="article URLs")
    ap.add_argument("--file", help="text file with one URL per line (# comments ok)")
    ap.add_argument("--voice", default="bm_lewis", help="Kokoro voice (default bm_lewis)")
    ap.add_argument("--out", default=None, help="output directory")
    args = ap.parse_args()

    urls = list(args.urls)
    if args.file:
        with open(args.file) as f:
            urls += [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    if not urls:
        ap.error("give at least one URL or --file")

    outdir = args.out or default_outdir()
    os.makedirs(outdir, exist_ok=True)
    print(f"Output : {outdir}")
    print(f"Voice  : {args.voice}\n")

    ok = 0
    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] {url}")
        try:
            title, text = fetch_article(url)
        except Exception as e:  # noqa
            print(f"   ! fetch failed: {e}\n")
            continue
        if not text:
            print("   ! couldn't extract article text, skipping\n")
            continue
        out = os.path.join(outdir, safe_name(title) + ".mp3")
        print(f"   → {title}")
        try:
            _, dur = synth_to_mp3(text, args.voice, out, title=title)
            print(f"   ✓ {os.path.basename(out)}  ({dur/60:.1f} min)\n")
            ok += 1
        except Exception as e:  # noqa
            print(f"   ! synthesis failed: {e}\n")

    print(f"Done — {ok}/{len(urls)} exported to {outdir}")


if __name__ == "__main__":
    main()
