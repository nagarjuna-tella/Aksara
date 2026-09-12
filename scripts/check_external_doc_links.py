"""Check important external documentation references without fetching page bodies."""

import argparse
import concurrent.futures
import hashlib
import json
import re
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urldefrag, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PAGES = (
    'README.md', 'docs/docs/index.md',
    'docs/docs/getting-started/installation.md',
    'docs/docs/getting-started/database-setup.md',
    'docs/docs/tutorials/deployment.md', 'docs/docs/roadmap.md',
    'docs/docs/reference/runtime-compatibility.md',
    'AKSARA_POST_V07_MARKET_AND_ROADMAP_REVIEW.md',
)
POST_MERGE_LOCAL_TARGETS = {
    'https://github.com/nagarjuna-tella/Aksara/blob/main/AKSARA_POST_V07_MARKET_AND_ROADMAP_REVIEW.md':
        'AKSARA_POST_V07_MARKET_AND_ROADMAP_REVIEW.md',
}


def check(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'Aksara-docs-link-check/0.7.1'})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return {'url': url, 'status': response.status, 'final_url': response.url,
                    'classification': 'reachable'}
    except urllib.error.HTTPError as error:
        return {'url': url, 'status': error.code, 'final_url': error.url,
                'classification': 'broken' if error.code in (404, 410) else 'unverified'}
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return {'url': url, 'status': None, 'classification': 'unverified',
                'error_type': type(error).__name__}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sources = {}
    excluded = {}
    for page in PAGES:
        content = re.sub(r'```.*?```', '', (ROOT / page).read_text(), flags=re.DOTALL)
        # Inline Markdown targets and HTML href/src attributes in these selected pages.
        urls = re.findall(r'\]\((https?://[^\s)]+)\)', content)
        urls += re.findall(r'(?:href|src)="(https?://[^"]+)"', content)
        for raw in urls:
            url = urldefrag(raw)[0]
            parsed = urlsplit(url)
            assert not parsed.username and not parsed.password, 'Credential-bearing link is not allowed'
            if parsed.hostname == 'nagarjuna-tella.github.io':
                excluded[url] = 'Candidate documentation URLs are checked against the rendered site, not the older published site'
            elif url in POST_MERGE_LOCAL_TARGETS:
                target = ROOT / POST_MERGE_LOCAL_TARGETS[url]
                assert target.is_file(), f'Post-merge link target is missing locally: {target}'
                excluded[url] = (
                    'Target exists in this candidate and becomes reachable on main only after merge'
                )
            else:
                sources.setdefault(url, []).append(page)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(check, sorted(sources)))
    for result in results:
        result['source_pages'] = sorted(set(sources[result['url']]))
    counts = {key: sum(row['classification'] == key for row in results)
              for key in ('reachable', 'broken', 'unverified')}
    evidence = {
        'schema_version': 1, 'checked_at': datetime.now(UTC).isoformat(),
        'pass': not counts['broken'] and not counts['unverified'], 'counts': counts,
        'scope': 'HTTP GET reachability of selected important inline Markdown/HTML external targets; no response-body, fragment, semantic-accuracy or all-docs coverage claim',
        'page_sha256': {page: hashlib.sha256((ROOT / page).read_bytes()).hexdigest() for page in PAGES},
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'excluded': excluded, 'results': results,
    }
    args.output.write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps(counts))
    for result in results:
        if result['classification'] != 'reachable':
            print(result['classification'], result['status'], result['url'])
    raise SystemExit(1 if counts['broken'] or counts['unverified'] else 0)


if __name__ == '__main__':
    main()
