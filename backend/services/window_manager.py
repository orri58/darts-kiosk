"""
Window Manager — OS-level kiosk window management.

On Windows: Uses Win32 API (ctypes) to hide/restore the kiosk Chrome window.
On other platforms: No-op (graceful fallback).

The kiosk Chrome window is identified by its document.title which the React app
sets to a stable value ('DartsKiosk'). This title is used by EnumWindows to find
the correct HWND.

Includes retry logic: Chrome in kiosk mode may take a moment to render the page
and set the window title. The hide function retries up to 3 times with 1s delay.

Also manages the credits overlay process lifecycle:
  - kill_overlay_process() terminates any running credits_overlay.py process.
  - minimize_observer_window() hides the Autodarts/Chrome observer window.
"""
import sys
import asyncio
import logging
import subprocess

logger = logging.getLogger(__name__)

KIOSK_WINDOW_TITLE = 'DartsKiosk'
OVERLAY_WINDOW_TITLE = 'Darts Overlay'
OVERLAY_PROCESS_NAME = 'credits_overlay'
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


async def minimize_observer_window():
    """Minimize all Chrome/Autodarts windows that are NOT the DartsKiosk window."""
    if sys.platform != 'win32':
        logger.debug("[WindowMgr] Not Windows — skip minimize_observer")
        return False

    logger.info("[WindowMgr] AUTODARTS_WINDOW_HIDE start")
    result = await asyncio.to_thread(_win32_minimize_non_kiosk_chrome)
    if result:
        logger.info("[WindowMgr] AUTODARTS_WINDOW_HIDE success")
    else:
        logger.info("[WindowMgr] AUTODARTS_WINDOW_HIDE no windows found to minimize")
    return result


async def force_kiosk_foreground():
    """
    Hard foreground enforcement: restore + maximize + SetForegroundWindow.
    Called as a second pass after a short delay to guarantee kiosk is on top.
    """
    if sys.platform != 'win32':
        logger.debug("[WindowMgr] Not Windows — skip force_kiosk_foreground")
        return

    logger.info("[WindowMgr] KIOSK_FOCUS_RESTORE start")
    found = await asyncio.to_thread(_win32_force_foreground, KIOSK_WINDOW_TITLE)
    if found:
        logger.info("[WindowMgr] KIOSK_FOCUS_RESTORE success")
    else:
        logger.warning("[WindowMgr] KIOSK_FOCUS_RESTORE failed — window not found")


async def ensure_autodarts_foreground():
    """
    Ensure the Autodarts Chrome window is visible and in the foreground.
    Used ONLY on the keep-alive path (credits remain after match end).
    Does NOT touch the kiosk window.
    """
    if sys.platform != 'win32':
        logger.debug("[WindowMgr] Not Windows — skip ensure_autodarts_foreground")
        return True

    logger.info("[WindowMgr] AUTODARTS_WINDOW_FOREGROUND start")
    found = await asyncio.to_thread(_win32_foreground_autodarts)
    if found:
        logger.info("[WindowMgr] AUTODARTS_WINDOW_FOREGROUND success")
    else:
        logger.warning("[WindowMgr] AUTODARTS_WINDOW_FOREGROUND: no autodarts window found")
    return found


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
        all_chrome_titles = []

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
            # Log all Chrome-related windows for diagnostics
            if 'chrome' in title.lower() or 'autodarts' in title.lower() or pattern.lower() in title.lower():
                all_chrome_titles.append(title)
            if pattern.lower() in title.lower():
                if 'autodarts' in title.lower():
                    logger.info(f"[WindowMgr] SKIP (autodarts): '{title}'")
                    return True
                logger.info(f"[WindowMgr] SW_HIDE: '{title}'")
                user32.ShowWindow(hwnd, SW_HIDE)
                found = True
            return True

        user32.EnumWindows(WNDENUMPROC(callback), 0)
        logger.info(f"[WindowMgr] hide_by_title('{pattern}'): found={found}, chrome_windows={all_chrome_titles}")
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
        all_chrome_titles = []

        def callback(hwnd, _lparam):
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            # Log all Chrome-related windows for diagnostics
            if 'chrome' in title.lower() or 'autodarts' in title.lower() or pattern.lower() in title.lower():
                all_chrome_titles.append(title)
            if pattern.lower() in title.lower():
                if 'autodarts' not in title.lower():
                    targets.append((hwnd, title))
            return True

        user32.EnumWindows(WNDENUMPROC(callback), 0)
        logger.info(f"[WindowMgr] restore_by_title('{pattern}'): targets={len(targets)}, chrome_windows={all_chrome_titles}")

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


def _win32_minimize_non_kiosk_chrome():
    """Find and minimize all Chrome/Autodarts windows that are NOT DartsKiosk."""
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        SW_MINIMIZE = 6

        WNDENUMPROC = ctypes.WINFUNCTYPE(
            wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
        )

        minimized = []

        def callback(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            title_lower = title.lower()

            # Target: visible Chrome/Autodarts windows that are NOT the kiosk
            is_chrome = 'chrome' in title_lower or 'autodarts' in title_lower
            is_kiosk = KIOSK_WINDOW_TITLE.lower() in title_lower

            if is_chrome and not is_kiosk:
                logger.info(f"[WindowMgr] AUTODARTS_WINDOW_HIDE: minimizing '{title}'")
                user32.ShowWindow(hwnd, SW_MINIMIZE)
                minimized.append(title)
            return True

        user32.EnumWindows(WNDENUMPROC(callback), 0)
        logger.info(f"[WindowMgr] minimize_non_kiosk_chrome: minimized={len(minimized)} titles={minimized}")
        return len(minimized) > 0

    except Exception as e:
        logger.warning(f"[WindowMgr] minimize_non_kiosk_chrome failed: {e}")
        return False


def _win32_force_foreground(pattern):
    """Hard foreground: find kiosk window, show + maximize + SetForegroundWindow + BringWindowToTop."""
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
        final_visible = []

        def callback(hwnd, _lparam):
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            if pattern.lower() in title.lower() and 'autodarts' not in title.lower():
                targets.append((hwnd, title))
            if user32.IsWindowVisible(hwnd) and ('chrome' in title.lower() or pattern.lower() in title.lower()):
                final_visible.append(title)
            return True

        user32.EnumWindows(WNDENUMPROC(callback), 0)

        for hwnd, title in targets:
            logger.info(f"[WindowMgr] KIOSK_FOCUS_RESTORE: forcing foreground '{title}'")
            user32.ShowWindow(hwnd, SW_SHOW)
            user32.ShowWindow(hwnd, SW_SHOWMAXIMIZED)
            try:
                # Alt-key trick to allow SetForegroundWindow
                user32.keybd_event(0x12, 0, 0, 0)   # Alt down
                user32.SetForegroundWindow(hwnd)
                user32.keybd_event(0x12, 0, 2, 0)   # Alt up
                # Also BringWindowToTop as extra enforcement
                user32.BringWindowToTop(hwnd)
            except Exception:
                pass

        if final_visible:
            logger.info(f"[WindowMgr] FINAL_VISIBLE_WINDOW titles={final_visible}")
        if targets:
            logger.info(f"[WindowMgr] FINAL_FOREGROUND_WINDOW title={targets[0][1]}")

        return len(targets) > 0

    except Exception as e:
        logger.warning(f"[WindowMgr] force_foreground failed: {e}")
        return False


def _win32_foreground_autodarts():
    """Find Autodarts Chrome window, restore if minimized, bring to foreground.
    Does NOT touch the kiosk window."""
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        SW_RESTORE = 9

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
            title_lower = title.lower()

            # Target: Chrome/Autodarts windows that are NOT the kiosk
            is_chrome = 'chrome' in title_lower or 'autodarts' in title_lower
            is_kiosk = KIOSK_WINDOW_TITLE.lower() in title_lower

            if is_chrome and not is_kiosk:
                targets.append((hwnd, title))
            return True

        user32.EnumWindows(WNDENUMPROC(callback), 0)

        for hwnd, title in targets:
            logger.info(f"[WindowMgr] AUTODARTS_WINDOW_FOREGROUND: forcing foreground '{title}'")
            # SW_RESTORE handles both minimized and normal state
            user32.ShowWindow(hwnd, SW_RESTORE)
            try:
                user32.keybd_event(0x12, 0, 0, 0)   # Alt down
                user32.SetForegroundWindow(hwnd)
                user32.keybd_event(0x12, 0, 2, 0)   # Alt up
                user32.BringWindowToTop(hwnd)
            except Exception:
                pass

        return len(targets) > 0

    except Exception as e:
        logger.warning(f"[WindowMgr] foreground_autodarts failed: {e}")
        return False


async def kill_overlay_process():
    """
    Terminate the credits_overlay.py process.
    On Windows: uses taskkill by window title, then falls back to process name.
    On Linux: uses pkill.
    """
    if sys.platform == 'win32':
        killed = await asyncio.to_thread(_win32_kill_overlay)
        if killed:
            logger.info("[WindowMgr] Overlay process terminated (Win32)")
        else:
            logger.info("[WindowMgr] No overlay process found to kill")
    else:
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ['pkill', '-f', OVERLAY_PROCESS_NAME],
                capture_output=True, timeout=5,
            )
            if result.returncode == 0:
                logger.info("[WindowMgr] Overlay process terminated (Linux)")
            else:
                logger.info("[WindowMgr] No overlay process found (Linux)")
        except Exception as e:
            logger.warning(f"[WindowMgr] Overlay kill failed (Linux): {e}")


def _win32_kill_overlay():
    """Kill overlay process on Windows via taskkill."""
    try:
        # First try by window title
        r = subprocess.run(
            ['taskkill', '/F', '/FI', f'WINDOWTITLE eq {OVERLAY_WINDOW_TITLE}'],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5,
        )
        if r.returncode == 0:
            return True

        # Fallback: kill by command line pattern
        r = subprocess.run(
            ['wmic', 'process', 'where',
             f"CommandLine like '%{OVERLAY_PROCESS_NAME}%'",
             'call', 'terminate'],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5,
        )
        return r.returncode == 0
    except Exception as e:
        logger.warning(f"[WindowMgr] Win32 overlay kill failed: {e}")
        return False
