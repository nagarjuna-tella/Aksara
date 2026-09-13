"""Verify the v0.7.2rc1 evidence manifest and credential boundary."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "audit-evidence/v072"
PROTECTED = (
    "audit-evidence/current-state/",
    "audit-evidence/v055/",
    "benchmarks/results/",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=EVIDENCE / "artifact-manifest.sha256",
    )
    args = parser.parse_args()

    entries: list[tuple[str, str]] = []
    for line in args.manifest.read_text().splitlines():
        digest, path = line.split("  ", 1)
        if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise SystemExit(f"invalid digest: {path}")
        if path in {item[1] for item in entries}:
            raise SystemExit(f"duplicate path: {path}")
        if path.startswith(PROTECTED):
            raise SystemExit(f"protected path included: {path}")
        entries.append((digest, path))

    if not entries:
        raise SystemExit("manifest is empty")

    for digest, path in entries:
        target = ROOT / path
        if not target.is_file():
            raise SystemExit(f"missing artifact: {path}")
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != digest:
            raise SystemExit(f"digest mismatch: {path}")

    credential_pattern = re.compile(
        rb"postgres(?:ql)?://[^\s/@:]+:[^\s/@]+@",
        re.IGNORECASE,
    )
    for path in EVIDENCE.iterdir():
        if path.is_file() and credential_pattern.search(path.read_bytes()) is not None:
            raise SystemExit(f"credential-like database URL in {path.relative_to(ROOT)}")

    print(f"PASS: verified {len(entries)} manifest entries and credential boundary")


if __name__ == "__main__":
    main()
