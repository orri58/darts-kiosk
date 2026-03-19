"""
Darts Kiosk Agent — Task Scheduler Autostart Setup
====================================================

Registers or updates the DartsKioskAgent task in Windows Task Scheduler.
Designed to be run once during installation (manual or scripted).

Usage:
    python setup_autostart.py [--remove]

Task Properties:
    - Name: DartsKioskAgent
    - Trigger: At system startup (with 15s delay)
    - Action: Run start_agent_silent.vbs (no console window)
    - Run with highest privileges
    - Restart on failure: up to 3 times, every 60 seconds
    - Run whether user is logged on or not (SYSTEM account)
"""
import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path

IS_WINDOWS = platform.system() == "Windows"
TASK_NAME = "DartsKioskAgent"


def _run(cmd, check=True):
    """Run a subprocess command with timeout and encoding safety."""
    kwargs = {"capture_output": True, "text": True, "timeout": 15}
    if IS_WINDOWS:
        kwargs["encoding"] = "utf-8"
        kwargs["errors"] = "replace"
    result = subprocess.run(cmd, **kwargs)
    if check and result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(f"Command failed (rc={result.returncode}): {stderr}")
    return result


def task_exists() -> bool:
    """Check if the scheduled task already exists."""
    result = _run(["schtasks", "/Query", "/TN", TASK_NAME], check=False)
    return result.returncode == 0


def remove_task():
    """Remove the scheduled task if it exists."""
    if not task_exists():
        print(f"[INFO] Task '{TASK_NAME}' does not exist. Nothing to remove.")
        return
    _run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"])
    print(f"[OK] Task '{TASK_NAME}' removed.")


def create_task():
    """Create or update the scheduled task."""
    agent_dir = Path(__file__).parent.resolve()
    vbs_path = agent_dir / "start_agent_silent.vbs"

    if not vbs_path.exists():
        print(f"[ERROR] VBS launcher not found: {vbs_path}")
        sys.exit(1)

    # Remove existing task first for clean update
    if task_exists():
        print(f"[INFO] Task '{TASK_NAME}' exists — updating...")
        _run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"])

    # Build XML task definition for full control
    xml_content = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Darts Kiosk Windows Agent — Lokale OS-Steuerung und Prozessaufsicht</Description>
    <Author>DartsKiosk</Author>
  </RegistrationInfo>
  <Triggers>
    <BootTrigger>
      <Enabled>true</Enabled>
      <Delay>PT15S</Delay>
    </BootTrigger>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <Delay>PT5S</Delay>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>S-1-5-18</UserId>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>5</Priority>
    <RestartOnFailure>
      <Interval>PT60S</Interval>
      <Count>3</Count>
    </RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>wscript.exe</Command>
      <Arguments>"{vbs_path}"</Arguments>
      <WorkingDirectory>{agent_dir}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>"""

    # Write XML to temp file
    xml_path = agent_dir / "_task_definition.xml"
    xml_path.write_text(xml_content, encoding="utf-16")

    try:
        _run(["schtasks", "/Create", "/TN", TASK_NAME, "/XML", str(xml_path), "/F"])
        print(f"[OK] Task '{TASK_NAME}' registered successfully.")
        print("     Trigger: Boot (+15s delay) + Logon (+5s delay)")
        print(f"     Action:  wscript.exe \"{vbs_path}\"")
        print("     Restart: 3x on failure (every 60s)")
        print("     Run As:  SYSTEM (highest privileges)")
    finally:
        xml_path.unlink(missing_ok=True)


def main():
    if not IS_WINDOWS:
        print("[ERROR] Task Scheduler setup is Windows-only.")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Darts Kiosk Agent — Autostart Setup")
    parser.add_argument("--remove", action="store_true", help="Remove the scheduled task")
    args = parser.parse_args()

    if args.remove:
        remove_task()
    else:
        create_task()


if __name__ == "__main__":
    main()
