#!/bin/bash
# Auto-publish watcher: launchd fires this on any change to the iCloud
# ReadAloud folder. It debounces, then runs `podcast-sync` only if there is an
# MP3 newer than episodes.json — so the feed rebuild (which rewrites feed.xml /
# episodes.json in the same watched folder) can't retrigger an infinite loop.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
LIB="$HOME/Library/Mobile Documents/com~apple~CloudDocs/ReadAloud"
LOG="$HERE/podcast-sync-watch.log"
LOCKDIR="$HERE/.podcast-sync-watch.lock"

log() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >>"$LOG"; }

# Collapse a burst of change events; never run two syncs at once.
# mkdir is atomic on macOS (no flock). Stale locks >10 min are cleared.
if [ -d "$LOCKDIR" ] && [ -z "$(find "$LOCKDIR" -maxdepth 0 -mmin +10 2>/dev/null)" ]; then
  log "another run in progress — skipping"; exit 0
fi
rm -rf "$LOCKDIR" 2>/dev/null || true
mkdir "$LOCKDIR" 2>/dev/null || { log "lock race — skipping"; exit 0; }
trap 'rm -rf "$LOCKDIR"' EXIT

# Let iCloud finish writing a (possibly large) MP3 before we scan.
sleep 20

reg="$LIB/episodes.json"
# Any .mp3 newer than the registry means there's something unpublished.
if [ -f "$reg" ] && [ -z "$(find "$LIB" -maxdepth 1 -name '*.mp3' -newer "$reg" -print -quit 2>/dev/null)" ]; then
  exit 0   # nothing new — this event was our own feed rewrite (or noise)
fi

log "new MP3 detected — running podcast-sync"
if "$HERE/podcast-sync" >>"$LOG" 2>&1; then
  log "sync OK"
else
  log "sync FAILED (exit $?)"
fi
