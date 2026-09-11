"""Keep experimental labels and corrected AI entry points visible."""

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs/docs"


def test_experimental_ai_pages_label_their_direct_entry():
    # These three pages explicitly explain the stable/experimental split.
    mixed = {"mcp.md", "safety.md", "tools.md"}
    for folder in ["ai-mode", "studio"]:
        for page in (DOCS / folder).glob("*.md"):
            if folder == "ai-mode" and page.name in mixed:
                continue
            assert '!!! warning "Experimental' in page.read_text()[:600], page


def test_corrected_ai_guide_evidence_is_current():
    evidence = json.loads((ROOT / "audit-evidence/v071/ai-docs-review.json").read_text())
    for path, digest in evidence["pages"].items():
        text = (ROOT / path).read_text()
        assert hashlib.sha256(text.encode()).hexdigest() == digest
        shell_blocks = re.findall(r'^```bash\n(.*?)^```', text, re.MULTILINE | re.DOTALL)
        assert all("aksara ai doctor" not in block for block in shell_blocks)
    hints = (DOCS / "ai-mode/hints.md").read_text()
    source = re.search(r'^```python\n(.*?)^```', hints, re.MULTILINE | re.DOTALL).group(1)
    assert evidence["hint_snippet_exit"] == 0
    assert evidence["hint_snippet_sha256"] == hashlib.sha256(source.encode()).hexdigest()
