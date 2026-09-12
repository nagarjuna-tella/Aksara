"""Keep the important external-reference check tied to the reviewed pages."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_external_link_evidence_is_current():
    evidence = json.loads((ROOT / 'audit-evidence/v071/external-links.json').read_text())
    assert evidence['pass']
    assert evidence['counts']['broken'] == evidence['counts']['unverified'] == 0
    assert evidence['counts']['reachable'] == len(evidence['results']) > 0
    assert {'README.md', 'AKSARA_POST_V07_MARKET_AND_ROADMAP_REVIEW.md'} <= set(evidence['page_sha256'])
    for path, digest in evidence['page_sha256'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    assert evidence['runner_sha256'] == hashlib.sha256((ROOT / 'scripts/check_external_doc_links.py').read_bytes()).hexdigest()
    assert len({item['url'] for item in evidence['results']}) == len(evidence['results'])
    post_merge_url = (
        'https://github.com/nagarjuna-tella/Aksara/blob/main/'
        'AKSARA_POST_V07_MARKET_AND_ROADMAP_REVIEW.md'
    )
    assert evidence['excluded'][post_merge_url] == (
        'Target exists in this candidate and becomes reachable on main only after merge'
    )
    assert (ROOT / 'AKSARA_POST_V07_MARKET_AND_ROADMAP_REVIEW.md').is_file()
    for item in evidence['results']:
        assert 200 <= item['status'] < 300
        assert item['classification'] == 'reachable'
        assert item['source_pages']
