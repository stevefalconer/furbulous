#!/usr/bin/env python3
"""Fail if tracked files look like they contain private hosts or secrets.

Intended for local pre-tag checks and CI. Does not print matched secret values
beyond a short masked excerpt.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Patterns that must not appear in the public repo.
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("private_ipv4", re.compile(r"\b192\.168\.\d{1,3}\.\d{1,3}\b")),
    ("private_ipv4_10", re.compile(r"\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")),
    ("private_ipv4_172", re.compile(r"\b172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}\b")),
    ("loopback_ha_url", re.compile(r"https?://127\.0\.0\.1:\d+")),
    ("bearer_header", re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}")),
    ("jwt_like", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.")),
    # Obvious password assignments in docs/yaml (not CONF_PASSWORD keys).
    ("password_literal", re.compile(r"""password\s*[:=]\s*['\"][^'\"]{8,}['\"]""", re.I)),
]

SKIP_SUFFIXES = {
    ".pyc",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".woff",
    ".woff2",
}
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules"}


def tracked_files() -> list[Path]:
    out = subprocess.check_output(
        ["git", "-C", str(ROOT), "ls-files", "-z"], text=False
    )
    paths: list[Path] = []
    for raw in out.split(b"\0"):
        if not raw:
            continue
        rel = raw.decode("utf-8", errors="replace")
        path = ROOT / rel
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        if not path.is_file():
            continue
        paths.append(path)
    return paths


def mask(s: str, limit: int = 40) -> str:
    s = s.strip().replace("\n", " ")
    if len(s) > limit:
        s = s[:limit] + "…"
    return s


def main() -> int:
    findings: list[str] = []
    for path in tracked_files():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = path.relative_to(ROOT).as_posix()
        # Allow this scanner and SECURITY docs to mention pattern names.
        if rel in {
            "scripts/secrets_scan.py",
            "docs/SECURITY_REVIEW.md",
        } or rel.startswith("docs/reviews/"):
            # Still ban real private IPs even in review docs.
            for name, pat in PATTERNS:
                if name.startswith("private_ipv4") or name == "loopback_ha_url":
                    for m in pat.finditer(text):
                        findings.append(f"{rel}: {name}: {mask(m.group(0))}")
            continue
        for name, pat in PATTERNS:
            for m in pat.finditer(text):
                # Unit tests / stubs use obvious fake passwords only.
                if name == "password_literal":
                    low = m.group(0).lower()
                    if any(
                        fake in low
                        for fake in ('"secret"', "'secret'", '"wrong"', "'wrong'", '"password"', "'password'", '"y"', "'y'")
                    ):
                        continue
                findings.append(f"{rel}: {name}: {mask(m.group(0))}")

    if findings:
        print("secrets_scan: FAILED — potential secrets / private hosts:", file=sys.stderr)
        for line in findings:
            print(f"  {line}", file=sys.stderr)
        return 1
    print("secrets_scan: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
