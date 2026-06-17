#!/usr/bin/env python3
"""
serve.py — a tiny local server so lessons can be *submitted*, not just read.

Lessons are static HTML. On their own a browser can't save your answers to disk
(file:// pages are sandboxed). This server fixes that with the smallest possible
bridge:

  • it serves the repo over http://127.0.0.1:<port>/ (localhost only), so a
    lesson opens at /lessons/0001-....html and its links to reference/ work;
  • it accepts POST /submit — a lesson's "Submit" button sends your answers as
    JSON, and the server writes them to submissions/<lesson>__<timestamp>.json.

It does NOT grade. Grading happens back in Claude Code: you say "grade lesson N",
and the teacher reads the submission file (plus the lesson's rubric) and evaluates
it with full context — your mission, your learning records, your past takes.

Stdlib only — no venv needed.

  python3 scripts/serve.py                          # serve, print the URL
  python3 scripts/serve.py --open lessons/0001-x.html   # also open it in a browser
  python3 scripts/serve.py --port 9000
  python3 scripts/serve.py --stop-when-orphaned     # exit if the launching process dies

Lifecycle: it writes its PID to .server.pid; the SessionEnd hook in
.claude/settings.json stops it when the Claude Code session ends. --stop-when-orphaned
is a backup that exits if the parent process goes away (e.g. the terminal closes).
"""
import argparse
import atexit
import datetime
import http.server
import json
import os
import re
import socketserver
import threading
import time
import webbrowser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUBMISSIONS = os.path.join(ROOT, "submissions")
PIDFILE = os.path.join(ROOT, ".server.pid")


def _safe(name):
    """A filesystem-safe slug for the lesson identifier the page reports."""
    return re.sub(r"[^A-Za-z0-9._-]", "-", (name or "lesson")).strip("-") or "lesson"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def do_POST(self):
        if self.path.rstrip("/") != "/submit":
            self.send_error(404, "only POST /submit is supported")
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, TypeError):
            self.send_error(400, "body must be JSON")
            return

        lesson = _safe(payload.get("lesson"))
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        payload["submitted_at"] = datetime.datetime.now().isoformat(timespec="seconds")
        os.makedirs(SUBMISSIONS, exist_ok=True)
        fname = f"{lesson}__{stamp}.json"
        with open(os.path.join(SUBMISSIONS, fname), "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        print(f"  ✓ saved submissions/{fname}  ({len(payload.get('answers', []))} answers)")
        body = json.dumps({"ok": True, "saved": fname}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # keep the console quiet except for our own prints
        pass


def _watch_parent(httpd):
    """Shut down if the launching process disappears (getppid reparents to 1)."""
    start_ppid = os.getppid()
    if start_ppid <= 1:
        return  # already orphaned/daemonized — can't track a parent
    while True:
        time.sleep(2)
        if os.getppid() != start_ppid:
            print("\nlaunching process exited — stopping server.")
            httpd.shutdown()
            return


def main():
    ap = argparse.ArgumentParser(description="Local lesson server (serve + capture submissions)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--open", dest="open_path", help="relative path of a lesson to open in the browser")
    ap.add_argument("--stop-when-orphaned", action="store_true",
                    help="exit if the process that launched it dies")
    args = ap.parse_args()

    with open(PIDFILE, "w") as f:
        f.write(str(os.getpid()))
    atexit.register(lambda: os.path.exists(PIDFILE) and os.remove(PIDFILE))

    url = f"http://127.0.0.1:{args.port}"
    with socketserver.ThreadingTCPServer(("127.0.0.1", args.port), Handler) as httpd:
        print(f"Serving {ROOT}\n  → {url}")
        print("  POST /submit  → submissions/<lesson>__<timestamp>.json")
        print("  Submit a lesson, then in Claude Code say:  grade the latest submission")
        print("  Ctrl-C to stop.\n")
        if args.open_path:
            webbrowser.open(f"{url}/{args.open_path.lstrip('/')}")
        if args.stop_when_orphaned:
            threading.Thread(target=_watch_parent, args=(httpd,), daemon=True).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped.")


if __name__ == "__main__":
    main()
