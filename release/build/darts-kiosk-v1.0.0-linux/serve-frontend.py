#!/usr/bin/env python3
"""Simple static file server for the pre-built frontend."""
import http.server
import os
import sys

PORT = int(os.environ.get("FRONTEND_PORT", "3000"))
BUILD_DIR = os.path.join(os.path.dirname(__file__), "frontend", "build")

class SPAHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BUILD_DIR, **kwargs)

    def do_GET(self):
        # SPA: serve index.html for all non-file routes
        path = os.path.join(BUILD_DIR, self.path.lstrip("/"))
        if not os.path.isfile(path) and not self.path.startswith("/api"):
            self.path = "/index.html"
        return super().do_GET()

if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", PORT), SPAHandler)
    print(f"Frontend serving {BUILD_DIR} on port {PORT}")
    server.serve_forever()
