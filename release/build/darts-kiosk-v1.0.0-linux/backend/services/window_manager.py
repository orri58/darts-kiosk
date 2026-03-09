"""
Window Manager — OS-level kiosk window management.

On Windows: Uses Win32 API (ctypes) to hide/restore the kiosk Chrome window.
On other platforms: No-op (graceful fallback).

The kiosk Chrome window is identified by its document.title which the React app
sets to a stable value ('DartsKiosk'). This title is used by EnumWindows to find
the correct HWND.

Flow:
  1. Board unlocked → observer launches Autodarts Chrome
  2. After successful launch → hide_kiosk_window() hides the kiosk Chrome
  3. Session ends → observer closes Autodarts Chrome
  4. After cleanup → restore_kiosk_window() restores kiosk Chrome to fullscreen
"""
import sys
import asyncio
import logging

logger = logging.getLogger(__name__)

# The kiosk React page sets document.title = 'DartsKiosk'
# Chrome kiosk mode uses this as the window title
KIOSK_WINDOW_TITLE = 'DartsKiosk'


async def hide_kiosk_window():
    """Hide the kiosk Chrome window so Autodarts is visible."""
    if sys.platform != 'win32':
        logger.debug("[WindowMgr] Not Windows — skip hide")
        return
    await asyncio.to_thread(_win32_hide_by_title, KIOSK_WINDOW_TITLE)


async def restore_kiosk_window():
    """Restore the kiosk Chrome window to fullscreen foreground."""
    if sys.platform != 'win32':
        logger.debug("[WindowMgr] Not Windows — skip restore")
        return
    await asyncio.to_thread(_win32_restore_by_title, KIOSK_WINDOW_TITLE)


# ─── Win32 Implementation ────────────────────────────────────────────

def _win32_hide_by_title(pattern):
    """Find and HIDE (not minimize) the kiosk window."""
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        SW_HIDE = 0

        WNDENUMPROC = ctypes.WINFUNCTYPE(
            wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
        )

        found = False

        def callback(hwnd, _lparam):
            nonlocal found
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            if pattern.lower() in title.lower():
                # Don't hide Autodarts windows
                if 'autodarts' in title.lower():
                    return True
                logger.info(f"[WindowMgr] Hiding kiosk window: '{title}'")
                user32.ShowWindow(hwnd, SW_HIDE)
                found = True
            return True

        user32.EnumWindows(WNDENUMPROC(callback), 0)

        if not found:
            logger.warning(f"[WindowMgr] No window found matching '{pattern}'")

    except Exception as e:
        logger.warning(f"[WindowMgr] Hide failed: {e}")


def _win32_restore_by_title(pattern):
    """Find and restore the kiosk window to maximized foreground."""
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        SW_SHOW = 5
        SW_SHOWMAXIMIZED = 3

        WNDENUMPROC = ctypes.WINFUNCTYPE(
            wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
        )

        targets = []

        def callback(hwnd, _lparam):
            # Check ALL windows (including hidden ones)
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            if pattern.lower() in title.lower():
                if 'autodarts' not in title.lower():
                    targets.append((hwnd, title))
            return True

        user32.EnumWindows(WNDENUMPROC(callback), 0)

        for hwnd, title in targets:
            logger.info(f"[WindowMgr] Restoring kiosk window: '{title}'")
            user32.ShowWindow(hwnd, SW_SHOW)
            user32.ShowWindow(hwnd, SW_SHOWMAXIMIZED)

            # Bring to foreground (workaround for Windows restriction)
            try:
                # Simulate Alt key press to allow SetForegroundWindow
                user32.keybd_event(0x12, 0, 0, 0)  # Alt down
                user32.SetForegroundWindow(hwnd)
                user32.keybd_event(0x12, 0, 2, 0)  # Alt up
            except Exception:
                pass

        if not targets:
            logger.warning(f"[WindowMgr] No hidden window found matching '{pattern}'")

    except Exception as e:
        logger.warning(f"[WindowMgr] Restore failed: {e}")
