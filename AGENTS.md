# readaloud

Native macOS app that reads web articles aloud using Kokoro, an open-source neural TTS model running locally. Paste a URL, get clean text extraction, hear it read in a natural voice. Exports to MP3 for iPhone.

## Stack
- Swift (macOS native UI)
- Python 3.12 (Kokoro TTS engine, article extraction)
- Kokoro 0.9.4 (local neural TTS, no API keys needed)
- Mozilla Readability.js (article text extraction)
- espeak-ng (phoneme generation for Kokoro)
- ffmpeg (MP3 encoding)

## Entry Points
- `./build.sh run` - compile and launch the macOS app
- `python3 readaloud-export.py` - batch export articles to MP3
- The app itself: ReadAloud.app

## Key Directories
```
ReadAloud/           - Swift source for the macOS app
build/               - build output
export/              - MP3 export output
build.sh             - compile script
readaloud-export.py  - batch CLI export tool
requirements.txt     - Python deps (kokoro, readability, etc.)
```

## Setup
```bash
brew install espeak-ng ffmpeg
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
./build.sh run
```

## Features
- URL paste -> clean text extraction
- Play/pause/skip-by-sentence, speed control, click-to-jump highlighting
- 8 voice options (default: Lewis, British male)
- MP3 export to iCloud Drive (syncs to iPhone Files app)
- No internet required after model download

## Current State
- Functional, actively used
- macOS 14+ on Apple Silicon required
- Large repo (38K files including venv and build artifacts)
- Git remote: github.com/ninjalu/read-aloud.git

## Related
- Web dashboard previously on port 8770 (moved to avoid clash with Mission Control on 8765)

<!-- BEGIN build-bridge — generated section, re-run ~/.claude/portable/build-bridge.py. Edit ABOVE this line. -->

## Project info (auto-detected)

**Stack:** Python, Shell, Swift
**Files:** ~200

**Entry points:**
- `./build.sh`

**Structure:**
```
berkshire/
  audio/
    cover.jpg
    episodes.json
    feed.xml
  raw/
    1977.html
    1978.html
    1979.html
    1980.html
    1981.html
    1982.html
    1983.html
    1984.html
    1985.html
    1986.html
    1987.html
    1988.html
    1989.html
    1990.html
    1991.html
    1992.html
    1993.html
    1994.html
    1995.html
    1996.html
    1997.html
    1998.html
    1998.pdf
    1999.html
    1999.pdf
    2000.html
    2000.pdf
    2001.html
    2001.pdf
    2002.html
    2002.pdf
    2003.html
    2003.pdf
    2004.pdf
... (truncated)
```

**Git:** branch: `main` | last commit: 2026-08-21 | 1 uncommitted | remote: https://github.com/ninjalu/read-aloud.git

## AI-agent bridge (Codex / open-source)

Working notes for any AI agent (Codex, open-source, etc.) in this directory.

### Memory for this project
No project memory has been recorded yet. As facts accumulate they will live at:
`/Users/luluo/.claude/projects/-Users-luluo-luluo-readaloud/memory/MEMORY.md` (read it first once it exists).

### Full protocol + skills catalog
See the global bridge at `/Users/luluo/AGENTS.md` for the memory read/write protocol,
the catalog of all 23 skills, and how to invoke them.

<!-- END build-bridge -->
