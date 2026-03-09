"""
Window Manager — OS-level kiosk window management.

On Windows: Uses Win32 API (ctypes) to hide/restore the kiosk Chrome window.
On other platforms: No-op (graceful fallback).

The kiosk Chrome window is identified by its document.title which the React app
sets to a stable value ('DartsKiosk'). This title is used by EnumWindows to find
the correct HWND.

Includes retry logic: Chrome in kiosk mode may take a moment to render the page
and set the window title. The hide function retries up to 3 times with 1s delay.
"""
import sys
import asyncio
import logging

logger = logging.getLogger(__name__)

KIOSK_WINDOW_TITLE = 'DartsKiosk'
MAX_RETRIES = 3
RETRY_DELAY = 1.0


async def hide_kiosk_window():
    """Hide the kiosk Chrome window so Autodarts is visible. Retries on failure."""
    if sys.platform != 'win32':
        logger.debug("[WindowMgr] Not Windows — skip hide")
        return

    for attempt in range(1, MAX_RETRIES + 1):
        found = await asyncio.to_thread(_win32_hide_by_title, KIOSK_WINDOW_TITLE)
        if found:
            logger.info(f"[WindowMgr] Kiosk window hidden (attempt {attempt})")
            return
        if attempt < MAX_RETRIES:
            logger.info(f"[WindowMgr] Kiosk window not found (attempt {attempt}/{MAX_RETRIES}), retrying in {RETRY_DELAY}s...")
            await asyncio.sleep(RETRY_DELAY)

    logger.warning(f"[WindowMgr] Could not find kiosk window after {MAX_RETRIES} attempts")


async def restore_kiosk_window():
    """Restore the kiosk Chrome window to fullscreen foreground. Retries on failure."""
    if sys.platform != 'win32':
        logger.debug("[WindowMgr] Not Windows — skip restore")
        return

    for attempt in range(1, MAX_RETRIES + 1):
        found = await asyncio.to_thread(_win32_restore_by_title, KIOSK_WINDOW_TITLE)
        if found:
            logger.info(f"[WindowMgr] Kiosk window restored (attempt {attempt})")
            return
        if attempt < MAX_RETRIES:
            logger.info(f"[WindowMgr] Hidden kiosk window not found (attempt {attempt}/{MAX_RETRIES}), retrying...")
            await asyncio.sleep(RETRY_DELAY)

    logger.warning(f"[WindowMgr] Could not find hidden kiosk window after {MAX_RETRIES} attempts")


# ─── Win32 Implementation ────────────────────────────────────────────

def _win32_hide_by_title(pattern):
    """Find and HIDE (not minimize) the kiosk window. Returns True if found."""
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
                if 'autodarts' in title.lower():
                    return True
                logger.info(f"[WindowMgr] SW_HIDE: '{title}'")
                user32.ShowWindow(hwnd, SW_HIDE)
                found = True
            return True

        user32.EnumWindows(WNDENUMPROC(callback), 0)
        return found

    except Exception as e:
        logger.warning(f"[WindowMgr] Hide failed: {e}")
        return False


def _win32_restore_by_title(pattern):
    """Find and restore the kiosk window. Returns True if found."""
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
            logger.info(f"[WindowMgr] Restoring: '{title}'")
            user32.ShowWindow(hwnd, SW_SHOW)
            user32.ShowWindow(hwnd, SW_SHOWMAXIMIZED)
            try:
                user32.keybd_event(0x12, 0, 0, 0)  # Alt down
                user32.SetForegroundWindow(hwnd)
                user32.keybd_event(0x12, 0, 2, 0)  # Alt up
            except Exception:
                pass

        return len(targets) > 0

    except Exception as e:
        logger.warning(f"[WindowMgr] Restore failed: {e}")
        return False
