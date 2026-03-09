"""
Credits Overlay — Always-on-top, click-through, transparent window.
Displays remaining credits/time during active Autodarts sessions.

Runs as a separate process on the kiosk PC:
  pythonw credits_overlay.py --board-id BOARD-1 --api http://localhost:8001

Features:
  - Always on top of all windows (including fullscreen Chrome)
  - Click-through on Windows (mouse events pass to underlying windows)
  - Transparent background
  - Polls backend /api/kiosk/{boardId}/overlay every 3s
  - Auto-shows when session active, auto-hides when locked
  - "LETZTES SPIEL" warning with upsell text
"""
import tkinter as tk
import urllib.request
import json
import sys
import argparse
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [Overlay] %(message)s')
logger = logging.getLogger('overlay')

POLL_MS = 3000
WIDTH = 220
HEIGHT = 85
MARGIN = 24
BG_TRANSPARENT = '#010101'  # Color key for transparency


class CreditsOverlay:
    def __init__(self, board_id, api_url):
        self.board_id = board_id
        self.api_url = api_url.rstrip('/')
        self.visible = False
        self.last_data = None

        self.root = tk.Tk()
        self.root.title('Darts Credits')
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.configure(bg=BG_TRANSPARENT)
        self.root.attributes('-transparentcolor', BG_TRANSPARENT)

        # Position: bottom-left corner
        screen_h = self.root.winfo_screenheight()
        x = MARGIN
        y = screen_h - HEIGHT - MARGIN
        self.root.geometry(f'{WIDTH}x{HEIGHT}+{x}+{y}')

        self.canvas = tk.Canvas(
            self.root, width=WIDTH, height=HEIGHT,
            bg=BG_TRANSPARENT, highlightthickness=0,
        )
        self.canvas.pack()

        # Click-through on Windows
        if sys.platform == 'win32':
            self.root.after(100, self._make_click_through)

        # Start hidden
        self.root.withdraw()
        logger.info(f'Overlay initialized: board={board_id}, api={api_url}')

        self._poll()

    def _make_click_through(self):
        """Set extended window style for click-through on Windows."""
        try:
            import ctypes
            import ctypes.wintypes

            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x00080000
            WS_EX_TRANSPARENT = 0x00000020

            self.root.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if not hwnd:
                hwnd = self.root.winfo_id()

            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                hwnd, GWL_EXSTYLE,
                style | WS_EX_LAYERED | WS_EX_TRANSPARENT
            )
            logger.info('Click-through enabled (Win32)')
        except Exception as e:
            logger.warning(f'Click-through setup failed: {e}')

    def _poll(self):
        """Fetch overlay data from backend."""
        try:
            url = f'{self.api_url}/api/kiosk/{self.board_id}/overlay'
            req = urllib.request.Request(url, headers={'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            self._update(data)
        except Exception:
            pass  # Backend not ready or unreachable

        self.root.after(POLL_MS, self._poll)

    def _update(self, data):
        """Update overlay display."""
        if not data.get('visible', False):
            if self.visible:
                self.root.withdraw()
                self.visible = False
            return

        if not self.visible:
            self.root.deiconify()
            self.root.lift()
            self.root.attributes('-topmost', True)
            self.visible = True

        # Skip redraw if data unchanged
        if data == self.last_data:
            return
        self.last_data = data

        self.canvas.delete('all')

        is_last = data.get('is_last_game', False)
        pricing = data.get('pricing_mode', 'per_game')
        credits = data.get('credits_remaining', 0)
        time_left = data.get('time_remaining_seconds')

        # Draw rounded background
        bg = '#7f1d1d' if is_last else '#0a0a0b'
        border = '#ef4444' if is_last else '#27272a'
        self._rounded_rect(1, 1, WIDTH - 1, HEIGHT - 1, 12, bg, border)

        if is_last:
            self.canvas.create_text(
                WIDTH // 2, 30,
                text='\u26A0 LETZTES SPIEL',
                fill='#fca5a5', font=('Segoe UI', 13, 'bold'),
                anchor='center',
            )
            msg = data.get('upsell_message', '')
            if msg:
                self.canvas.create_text(
                    WIDTH // 2, 55,
                    text=msg[:35],
                    fill='#fecaca', font=('Segoe UI', 8),
                    anchor='center',
                )
            price = data.get('upsell_pricing', '')
            if price:
                self.canvas.create_text(
                    WIDTH // 2, 70,
                    text=price[:30],
                    fill='#fca5a5', font=('Segoe UI', 7, 'bold'),
                    anchor='center',
                )
        elif pricing == 'per_time':
            self.canvas.create_text(
                18, 22, text='ZEIT \u00dcBRIG', fill='#71717a',
                font=('Segoe UI', 8, 'bold'), anchor='w',
            )
            ts = self._fmt_time(time_left)
            color = '#f59e0b' if (time_left and time_left < 300) else '#ffffff'
            self.canvas.create_text(
                18, 55, text=ts, fill=color,
                font=('Segoe UI', 24, 'bold'), anchor='w',
            )
        else:
            self.canvas.create_text(
                18, 22, text='SPIELE \u00dcBRIG', fill='#71717a',
                font=('Segoe UI', 8, 'bold'), anchor='w',
            )
            color = '#f59e0b' if credits <= 1 else '#ffffff'
            self.canvas.create_text(
                18, 55, text=str(credits), fill=color,
                font=('Segoe UI', 24, 'bold'), anchor='w',
            )

    def _rounded_rect(self, x1, y1, x2, y2, r, fill, outline):
        """Draw a filled rounded rectangle."""
        # Center
        self.canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline='')
        self.canvas.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline='')
        # Corners
        self.canvas.create_oval(x1, y1, x1 + 2 * r, y1 + 2 * r, fill=fill, outline='')
        self.canvas.create_oval(x2 - 2 * r, y1, x2, y1 + 2 * r, fill=fill, outline='')
        self.canvas.create_oval(x1, y2 - 2 * r, x1 + 2 * r, y2, fill=fill, outline='')
        self.canvas.create_oval(x2 - 2 * r, y2 - 2 * r, x2, y2, fill=fill, outline='')
        # Border line (thin)
        pts = [
            x1 + r, y1, x2 - r, y1,
            x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2,
            x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r,
            x1, y1 + r, x1, y1,
        ]
        self.canvas.create_line(pts, fill=outline, width=1, smooth=True)

    def _fmt_time(self, seconds):
        if seconds is None:
            return '--:--'
        m = int(seconds) // 60
        s = int(seconds) % 60
        return f'{m}:{s:02d}'

    def run(self):
        logger.info('Overlay main loop started')
        self.root.mainloop()


def main():
    parser = argparse.ArgumentParser(description='Darts Kiosk Credits Overlay')
    parser.add_argument('--board-id', default=os.environ.get('BOARD_ID', 'BOARD-1'),
                        help='Board ID to monitor')
    parser.add_argument('--api', default=os.environ.get('API_URL', 'http://localhost:8001'),
                        help='Backend API base URL')
    args = parser.parse_args()

    overlay = CreditsOverlay(args.board_id, args.api)
    overlay.run()


if __name__ == '__main__':
    main()
