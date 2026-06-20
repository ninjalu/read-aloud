"""Local Kokoro TTS server for Read Aloud.

Loads the Kokoro model once and serves audio over HTTP so the native app can
request a sentence (for live playback) or a whole article (for MP3 export).

  GET  /health                               -> "ok"
  POST /speak?voice=&speed=    (body=text)   -> audio/wav   (one sentence)
  POST /export?voice=&title=   (body=text)   -> audio/mpeg  (whole article MP3)
"""
import os
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import tts_core

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # quiet

    def do_GET(self):
        if urlparse(self.path).path == "/health":
            self._send(200, b"ok", "text/plain")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        parsed = urlparse(self.path)
        q = parse_qs(parsed.query)
        length = int(self.headers.get("Content-Length", 0))
        text = self.rfile.read(length).decode("utf-8", "ignore").strip()
        if not text:
            self._send(400, b"empty text", "text/plain")
            return
        voice = q.get("voice", ["bm_lewis"])[0]
        try:
            speed = float(q.get("speed", ["1.0"])[0])
        except ValueError:
            speed = 1.0
        try:
            if parsed.path == "/speak":
                self._send(200, tts_core.synth_wav_bytes(text, voice, speed), "audio/wav")
            elif parsed.path == "/export":
                title = q.get("title", [None])[0]
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as t:
                    out = t.name
                try:
                    tts_core.synth_to_mp3(text, voice, out, speed=speed, title=title)
                    with open(out, "rb") as f:
                        data = f.read()
                finally:
                    if os.path.exists(out):
                        os.unlink(out)
                self._send(200, data, "audio/mpeg")
            else:
                self._send(404, b"not found", "text/plain")
        except Exception as e:  # noqa
            self._send(500, str(e).encode(), "text/plain")

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    try:
        tts_core.get_pipeline("bm_lewis")  # warm the default voice
    except Exception as e:
        print(f"warm-up failed: {e}", file=sys.stderr)
    print(f"Kokoro TTS server ready on http://127.0.0.1:{PORT}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
