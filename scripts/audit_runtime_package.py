#!/usr/bin/env python3
"""Advisory audit for runtime-package shaping.

Safe by default:
- reads an extracted directory or .zip/.tar.gz artifact
- compares contents against release/runtime_package_allowlist.json
- reports mismatches without changing the current release flow

Exit codes:
- 0: audit completed, no disallowed entries found
- 1: audit completed, disallowed entries found (only with --strict)
- 2: usage or manifest error
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Iterable, List


TEXT_ARCHIVE_SUFFIXES = (".zip", ".tar.gz", ".tgz", ".tar")


def load_manifest(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive path
        raise SystemExit(f"Manifest could not be read: {path} ({exc})") from exc


def normalize(rel_path: str) -> str:
    rel_path = rel_path.replace('\\', '/').lstrip('./')
    return rel_path.rstrip('/') + ('/' if rel_path and rel_path.endswith('/') else '')


def list_entries(target: Path) -> List[str]:
    if target.is_dir():
        items = []
        for path in sorted(target.rglob('*')):
            rel = path.relative_to(target).as_posix()
            if path.is_dir():
                rel += '/'
            items.append(rel)
        return items

    name = target.name.lower()
    if name.endswith('.zip'):
        with zipfile.ZipFile(target) as zf:
            items = []
            for info in zf.infolist():
                rel = info.filename
                if info.is_dir() and not rel.endswith('/'):
                    rel += '/'
                items.append(rel)
            return sorted(items)

    if name.endswith(('.tar.gz', '.tgz', '.tar')):
        with tarfile.open(target) as tf:
            items = []
            for member in tf.getmembers():
                rel = member.name
                if member.isdir() and not rel.endswith('/'):
                    rel += '/'
                items.append(rel)
            return sorted(items)

    raise SystemExit(f'Unsupported target: {target}')


def strip_single_top_level(entries: Iterable[str]) -> List[str]:
    entries = list(entries)
    roots = {entry.split('/', 1)[0] for entry in entries if entry}
    if len(roots) != 1:
        return entries
    root = next(iter(roots))
    prefix = root + '/'
    stripped = []
    for entry in entries:
        if entry == root or entry == root + '/':
            continue
        stripped.append(entry[len(prefix):] if entry.startswith(prefix) else entry)
    return stripped


def matches_any(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def path_is_allowed(path: str, manifest: dict) -> bool:
    allowed_roots = manifest.get('allowed_roots', [])
    if allowed_roots and not any(path == root.rstrip('/') or path.startswith(root) for root in allowed_roots):
        return False

    exclude_globs = manifest.get('exclude_globs', [])
    if matches_any(path, exclude_globs):
        return False

    allow = manifest.get('allow', [])
    if not allow:
        return True
    return matches_any(path, allow)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('target', help='Extracted package directory or built archive to audit')
    parser.add_argument('--manifest', default='release/runtime_package_allowlist.json')
    parser.add_argument('--strict', action='store_true', help='Return exit code 1 when disallowed entries are found')
    args = parser.parse_args()

    workspace = Path.cwd()
    target = (workspace / args.target).resolve() if not Path(args.target).is_absolute() else Path(args.target)
    manifest_path = (workspace / args.manifest).resolve() if not Path(args.manifest).is_absolute() else Path(args.manifest)

    if not target.exists():
        print(f'Target not found: {target}', file=sys.stderr)
        return 2
    if not manifest_path.exists():
        print(f'Manifest not found: {manifest_path}', file=sys.stderr)
        return 2

    manifest = load_manifest(manifest_path)
    entries = strip_single_top_level(list_entries(target))
    normalized = [normalize(entry) for entry in entries if entry]

    disallowed = [path for path in normalized if not path_is_allowed(path, manifest)]
    missing_required = []
    for req in manifest.get('required_paths', []):
        req = normalize(req)
        if not any(path == req.rstrip('/') or path.startswith(req) for path in normalized):
            missing_required.append(req)

    print(f'Audit target: {target}')
    print(f'Manifest: {manifest_path}')
    print(f'Entries scanned: {len(normalized)}')
    print(f'Disallowed entries: {len(disallowed)}')
    print(f'Missing required paths: {len(missing_required)}')

    if disallowed:
        print('\nDisallowed sample:')
        for path in disallowed[:40]:
            print(f'  - {path}')
        if len(disallowed) > 40:
            print(f'  ... +{len(disallowed) - 40} more')

    if missing_required:
        print('\nMissing required paths:')
        for path in missing_required:
            print(f'  - {path}')

    if disallowed and args.strict:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
