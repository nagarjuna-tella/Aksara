"""Execute the complete public local-storage/email example in an installed wheel."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    page = ROOT / "docs/docs/advanced/media-and-email.md"
    source = re.search(r'```python title="check_media.py"\n(.*?)```', page.read_text(), re.DOTALL).group(1)
    env = {k: v for k, v in os.environ.items()
           if k not in {"PYTHONPATH", "DATABASE_URL"} and not k.startswith("AKSARA_")}
    with tempfile.TemporaryDirectory(prefix="aksara-media-check-") as raw:
        root = Path(raw)
        script = root / "check_media.py"
        script.write_text(source)
        probe = subprocess.run([str(args.python.absolute()), "-I", "-c",
                                "import aksara,json; print(json.dumps({'version':aksara.__version__,'path':aksara.__file__}))"],
                               cwd=root, env=env, capture_output=True, text=True, check=True)
        package = json.loads(probe.stdout)
        assert not Path(package["path"]).is_relative_to(ROOT)
        result = subprocess.run([str(args.python.absolute()), "-I", str(script)], cwd=root,
                                env=env, capture_output=True, text=True, timeout=30, check=True)
        checks = json.loads(result.stdout)
        assert checks["pass"] is True
    evidence = {**checks, "schema_version": 1, "package_version": package["version"],
                "source_checkout_framework_imports": False,
                "scope": "Local storage and in-memory email only; no database, SMTP or S3",
                "page_sha256": hashlib.sha256(page.read_bytes()).hexdigest(),
                "snippet_sha256": hashlib.sha256(source.encode()).hexdigest(),
                "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: {len(checks['checks'])} local media/email checks")


if __name__ == "__main__":
    main()
