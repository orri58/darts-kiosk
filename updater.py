#!/usr/bin/env python3
"""
Darts Kiosk — External Updater
===============================
Standalone script that performs the actual file replacement during an update.
This script is launched by the backend as a SEPARATE PROCESS and takes over
after the backend has prepared the update (downloaded, backed up, staged).

Usage:
    python updater.py <manifest_path>

Manifest JSON fields:
    action            : "install_update" or "rollback"
    staging_dir       : path to extracted update files (install_update only)
    backup_path       : path to the app backup zip
    project_root      : path to the application root
    target_version    : version being installed (install_update only)
    health_check_url  : URL for post-update health check
    version_check_url : URL for version verification
    protected_paths   : list of paths that must NEVER be overwritten

Steps (install_update):
    1. Wait for backend to stop accepting requests
    2. Stop all services (stop.bat on Windows)
    3. Replace application files from staging
    4. Preserve protected directories (data/, logs/, .env, chrome_profile/)
    5. Restart services (start.bat on Windows)
    6. Health check (retry with backoff)
    7. Version verification
    8. On failure: rollback from backup
    9. Write result JSON

Steps (rollback):
    1. Stop services
    2. Restore files from backup zip
    3. Restart services
    4. Health check
    5. Write result JSON
"""
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# Log to both console and file
LOG_LINES = []

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line)
    LOG_LINES.append(line)

def write_result(result_path, result):
    """Write the update result JSON for the backend to read on restart."""
    result['log'] = LOG_LINES[-50:]  # Last 50 lines
    result['completed_at'] = datetime.now(timezone.utc).isoformat()
    Path(result_path).write_text(json.dumps(result, indent=2))
    log(f"Result written to {result_path}")


def stop_services(project_root):
    """Stop all Darts Kiosk services."""
    log("Stopping services...")
    stop_bat = Path(project_root) / 'stop.bat'
    if stop_bat.exists() and sys.platform == 'win32':
        subprocess.run(['cmd', '/c', str(stop_bat)], cwd=project_root, timeout=30)
    else:
        # Linux: try systemctl or kill
        subprocess.run(['pkill', '-f', 'uvicorn.*server:app'], timeout=10,
                       capture_output=True)
        subprocess.run(['pkill', '-f', 'node.*react-scripts'], timeout=10,
                       capture_output=True)
    time.sleep(3)
    log("Services stopped")


def start_services(project_root):
    """Start all Darts Kiosk services."""
    log("Starting services...")
    start_bat = Path(project_root) / 'start.bat'
    if start_bat.exists() and sys.platform == 'win32':
        # Launch start.bat in a new console (non-blocking)
        subprocess.Popen(
            ['cmd', '/c', str(start_bat)],
            cwd=project_root,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
    else:
        # Linux: try systemctl or manual start
        backend_env = Path(project_root) / 'backend' / '.env'
        if backend_env.exists():
            subprocess.Popen(
                [sys.executable, '-m', 'uvicorn', 'backend.server:app',
                 '--host', '0.0.0.0', '--port', '8001'],
                cwd=project_root,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    log("Services start command issued")


def health_check(url, retries=10, interval=5):
    """Check if the backend is healthy. Returns True on success."""
    log(f"Health check: {url} (max {retries} retries, {interval}s interval)")
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.urlopen(url, timeout=5)
            data = json.loads(req.read().decode())
            if data.get('status') == 'healthy':
                log(f"Health check PASSED (attempt {attempt})")
                return True
        except Exception as e:
            log(f"Health check attempt {attempt}/{retries}: {e}")
        time.sleep(interval)
    log("Health check FAILED after all retries")
    return False


def version_check(url, expected_version):
    """Verify the installed version matches the expected version."""
    try:
        req = urllib.request.urlopen(url, timeout=5)
        data = json.loads(req.read().decode())
        actual = data.get('installed_version', '')
        if actual == expected_version:
            log(f"Version check PASSED: {actual}")
            return True
        else:
            log(f"Version check FAILED: expected={expected_version}, actual={actual}")
            return False
    except Exception as e:
        log(f"Version check error: {e}")
        return False


def replace_files(staging_dir, project_root, protected_paths):
    """
    Replace application files from staging directory.
    NEVER overwrites protected paths.
    """
    staging = Path(staging_dir)
    root = Path(project_root)

    # Normalize protected paths
    protected = set()
    for p in protected_paths:
        protected.add(p.replace('/', os.sep).lower())

    def is_protected(rel_path):
        """Check if a path is protected."""
        rel_str = str(rel_path).lower()
        for pp in protected:
            if rel_str == pp or rel_str.startswith(pp + os.sep):
                return True
        return False

    # Walk staging and copy files
    files_copied = 0
    files_skipped = 0

    for src_path in staging.rglob('*'):
        if src_path.is_dir():
            continue

        rel = src_path.relative_to(staging)

        if is_protected(rel):
            files_skipped += 1
            continue

        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(src_path, dst)
        files_copied += 1

    log(f"Files replaced: {files_copied} copied, {files_skipped} protected (skipped)")
    return files_copied


def restore_from_backup(backup_path, project_root, protected_paths):
    """
    Restore application files from a backup zip.
    Same protection rules apply — data/, .env, etc. are never touched.
    """
    backup = Path(backup_path)
    root = Path(project_root)

    if not backup.exists():
        log(f"Backup not found: {backup_path}")
        return False

    protected = set()
    for p in protected_paths:
        protected.add(p.replace('/', os.sep).lower())

    def is_protected(rel_path):
        rel_str = str(rel_path).lower()
        for pp in protected:
            if rel_str == pp or rel_str.startswith(pp + os.sep):
                return True
        return False

    log(f"Restoring from backup: {backup.name}")
    files_restored = 0

    with zipfile.ZipFile(backup, 'r') as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue

            rel = Path(member.filename)
            if is_protected(rel):
                continue

            dst = root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)

            with zf.open(member) as src, open(dst, 'wb') as dst_f:
                shutil.copyfileobj(src, dst_f)
            files_restored += 1

    log(f"Restored {files_restored} files from backup")
    return True


def do_install(manifest):
    """Execute the install_update action."""
    project_root = manifest['project_root']
    staging_dir = manifest['staging_dir']
    backup_path = manifest['backup_path']
    target_version = manifest['target_version']
    protected = manifest.get('protected_paths', [])
    health_url = manifest.get('health_check_url', 'http://localhost:8001/api/health')
    version_url = manifest.get('version_check_url', 'http://localhost:8001/api/system/version')
    result_path = str(Path(manifest.get('project_root', '.')) / 'data' / 'update_result.json')

    result = {
        'action': 'install_update',
        'target_version': target_version,
        'previous_version': manifest.get('current_version', '?'),
        'started_at': datetime.now(timezone.utc).isoformat(),
        'success': False,
        'rolled_back': False,
    }

    try:
        # Step 1: Wait for backend to wind down
        log(f"=== DARTS KIOSK UPDATER v{target_version} ===")
        log("Waiting 5s for backend to wind down...")
        time.sleep(5)

        # Step 2: Stop services
        stop_services(project_root)

        # Step 3: Replace files
        log(f"Replacing application files from staging: {staging_dir}")
        count = replace_files(staging_dir, project_root, protected)
        result['files_replaced'] = count

        # Step 4: Start services
        start_services(project_root)

        # Step 5: Wait for services to come up
        log("Waiting 15s for services to start...")
        time.sleep(15)

        # Step 6: Health check
        if health_check(health_url):
            result['health_ok'] = True
        else:
            raise Exception("Health check failed after update")

        # Step 7: Version check
        if version_check(version_url, target_version):
            result['version_ok'] = True
        else:
            log(f"WARNING: Version mismatch, but health check passed")
            result['version_ok'] = False

        result['success'] = True
        log(f"=== UPDATE SUCCESSFUL: v{target_version} ===")

    except Exception as e:
        log(f"=== UPDATE FAILED: {e} ===")
        result['error'] = str(e)

        # Rollback
        log("Starting automatic rollback...")
        try:
            stop_services(project_root)
            if restore_from_backup(backup_path, project_root, protected):
                start_services(project_root)
                time.sleep(15)
                if health_check(health_url, retries=5, interval=3):
                    log("ROLLBACK SUCCESSFUL — previous version restored")
                    result['rolled_back'] = True
                else:
                    log("ROLLBACK WARNING — services may need manual restart")
                    result['rolled_back'] = True
                    result['manual_restart_needed'] = True
            else:
                log("ROLLBACK FAILED — backup could not be restored")
                result['rolled_back'] = False
        except Exception as rb_err:
            log(f"ROLLBACK ERROR: {rb_err}")
            result['rollback_error'] = str(rb_err)

    write_result(result_path, result)
    return result


def do_rollback(manifest):
    """Execute the rollback action."""
    project_root = manifest['project_root']
    backup_path = manifest['backup_path']
    protected = manifest.get('protected_paths', [])
    health_url = manifest.get('health_check_url', 'http://localhost:8001/api/health')
    result_path = str(Path(project_root) / 'data' / 'update_result.json')

    result = {
        'action': 'rollback',
        'backup_used': Path(backup_path).name,
        'started_at': datetime.now(timezone.utc).isoformat(),
        'success': False,
    }

    try:
        log("=== DARTS KIOSK ROLLBACK ===")
        log("Waiting 5s for backend to wind down...")
        time.sleep(5)

        stop_services(project_root)

        if not restore_from_backup(backup_path, project_root, protected):
            raise Exception("Backup restoration failed")

        start_services(project_root)
        log("Waiting 15s for services to start...")
        time.sleep(15)

        if health_check(health_url):
            result['health_ok'] = True
            result['success'] = True
            log("=== ROLLBACK SUCCESSFUL ===")
        else:
            raise Exception("Health check failed after rollback")

    except Exception as e:
        log(f"=== ROLLBACK FAILED: {e} ===")
        result['error'] = str(e)

    write_result(result_path, result)
    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: python updater.py <manifest_path>")
        sys.exit(1)

    manifest_path = sys.argv[1]
    log(f"Reading manifest: {manifest_path}")

    with open(manifest_path, 'r') as f:
        manifest = json.load(f)

    action = manifest.get('action', 'install_update')
    log(f"Action: {action}")

    if action == 'install_update':
        result = do_install(manifest)
    elif action == 'rollback':
        result = do_rollback(manifest)
    else:
        log(f"Unknown action: {action}")
        sys.exit(1)

    # Pause on Windows so user can see the output
    if sys.platform == 'win32':
        input("\nDruecke Enter zum Schliessen...")

    sys.exit(0 if result.get('success') else 1)


if __name__ == '__main__':
    main()
