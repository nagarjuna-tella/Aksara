"""Inventory current pages and scoped evidence without inferring semantic acceptance."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = 'b7ac75f4b1bd4b262824e828601168336b4ecf7f'
GENERIC = {'installed-doc-imports.json', 'rendered-links.json', 'external-links.json',
           'cli-docs-syntax.json', 'public-docs-inventory.json', 'public-docs-truth.json',
           'public-page-review-inventory.json'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    changed = set(subprocess.check_output(
        ['git', 'diff', '--name-only', BASE, '--', 'docs/docs', 'README.md'],
        cwd=ROOT, text=True,
    ).splitlines())
    evidence = {}
    for artifact in sorted((ROOT / 'audit-evidence/v071').glob('*.json')):
        if artifact.name in GENERIC:
            continue
        data = json.loads(artifact.read_text())
        links = {}
        for key in ('page_sha256', 'source_sha256'):
            if isinstance(data.get(key), dict):
                links.update(data[key])
        for stage in data.get('stages', []):
            links[stage['guide']] = stage['guide_sha256']
        for page, digest in links.items():
            target = ROOT / page
            if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == digest:
                evidence.setdefault(page, []).append(artifact.name)
    pages = []
    for page in [ROOT / 'README.md', *sorted((ROOT / 'docs/docs').rglob('*.md'))]:
        name = str(page.relative_to(ROOT))
        pages.append({'path': name, 'sha256': hashlib.sha256(page.read_bytes()).hexdigest(),
                      'changed_since_release': name in changed,
                      'scoped_evidence_candidates': evidence.get(name, []),
                      'semantic_acceptance': 'requires_explicit_review',
                      'lines': len(page.read_text().splitlines())})
    data = {'schema_version': 1, 'base_sha': BASE,
            'scope': 'Current page census and discovery of fresh scoped evidence links. Change history, hashes and linked evidence do not prove all page claims or usability. Historical baseline is preserved.',
            'pages': pages,
            'counts': {'pages': len(pages),
                       'unchanged_since_release': sum(not p['changed_since_release'] for p in pages),
                       'with_scoped_evidence_candidates': sum(bool(p['scoped_evidence_candidates']) for p in pages)},
            'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    args.output.write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps(data['counts']))


if __name__ == '__main__':
    main()
