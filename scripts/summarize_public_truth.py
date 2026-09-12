"""Index scoped public-truth evidence without treating it as release approval."""

import argparse
import hashlib
import json
import re
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'audit-evidence/v071'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--objective', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    objective = args.objective.read_text()
    phases = []
    for number, line in enumerate(objective.splitlines(),1):
        match = re.match(r'^#{1,3} Phase ([A-E]\d+)\s+[—–-]\s+(.+)$',line)
        if match:
            phases.append({'id':match[1], 'title':match[2], 'objective_line':number,
                           'final_requirement_audit':'not yet performed'})
    assert len(phases)==63, 'Objective phase structure changed; review explicitly'
    entries = []
    stale = []
    for path in sorted(EVIDENCE.glob('*.json')):
        if path.resolve()==args.output.resolve():
            continue
        data=json.loads(path.read_text())
        linked={}
        for field in ('page_sha256','source_sha256'):
            if isinstance(data.get(field),dict):
                linked.update(data[field])
        if isinstance(data.get('page_sha256'),str) and data.get('page'):
            linked[data['page']]=data['page_sha256']
        for stage in data.get('stages',[]):
            linked[stage['guide']]=stage['guide_sha256']
        mismatches=[name for name, value in linked.items()
                    if not (ROOT/name).is_file() or digest(ROOT/name)!=value]
        stale.extend({'artifact':path.name,'input':name} for name in mismatches)
        entries.append({'artifact':str(path.relative_to(ROOT)),'sha256':digest(path),
                        'recorded_result':data.get('pass',data.get('status','not a boolean gate')),
                        'scope':data.get('scope','Read the artifact and audit report for scope; no inferred pass'),
                        'checked_linked_page_hashes':len(linked),'stale_linked_pages':mismatches,
                        'historical_head':data.get('head',data.get('source_head'))})
    metadata=tomllib.loads((ROOT/'pyproject.toml').read_text())
    result={
        'schema_version':1,'assessment':'NOT READY: final requirement audit and release gates remain open',
        'candidate_ready':False,'input_integrity_pass':not stale,
        'reviewed_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'package_version':metadata['project']['version'],
        'objective_sha256':digest(args.objective),'objective_phase_index':phases,
        'phase_index_scope':'Preserves phase identities for the final audit; does not mark any full phase complete or replace requirements elsewhere in the objective',
        'requirement_review': {
            'artifact': 'audit-evidence/v071/requirement-review.md',
            'sha256': digest(EVIDENCE / 'requirement-review.md'),
            'scope': 'Checkpoint covering all phase identities, non-phase boundaries and named deliverables; scoped evidence and open work, not final subitem acceptance or release approval',
        },
        'evidence':entries,'stale_linked_inputs':stale,
        'known_defects':[
            {'id':'RELATION001','evidence':'query-execution.json','boundary':'first does not populate requested eager relation'},
            {'id':'ADMINWIDGET001','evidence':'installed-doc-imports.json','boundary':'Array widget padding mutates caller list'},
            {'id':'INSPECTOR001','evidence':'installed-doc-imports.json','boundary':'Offline synthetic ANALYZE result lacks provenance warning'},
            {'id':'FIXTURE001','evidence':'fixture-execution.json','boundary':'Exported primary keys cannot restore absent rows'},
            {'id':'FIXTURE002','evidence':'fixture-execution.json','boundary':'Single-model YAML UUID tags rejected by safe loader'},
            {'id':'FIXTURE003','evidence':'fixture-execution.json','boundary':'Default database export iterates registry names as models'},
            {'id':'SOFTDELETE001','evidence':'soft-delete-execution.json','boundary':'Module-level visibility helpers discard existing queryset filters'},
            {'id':'EX-001','evidence':'example-defects.json','boundary':'Example middleware exemption matching'},
            {'id':'CFG-001','evidence':'configuration-findings.json','boundary':'POSIX environment list parsing'},
            {'id':'SDK-001','evidence':'typescript-sdk-probe.json','boundary':'Generated TypeScript strict compilation'},
            {'id':'STORAGE-001','evidence':'storage-boundary.json','boundary':'Direct filesystem path containment'},
            {'id':'ACTION-001','evidence':'custom-action-boundary.json','boundary':'Custom HTTP action authorization metadata'},
            {'id':'MIGRATION-001','evidence':'domain-template-execution.json','boundary':'CLI model-name collision omits application User table'},
            {'id':'PAGINATION-001','evidence':'pagination-doc-execution.json','boundary':'Generated HTTP response discards page/cursor metadata'},
            {'id':'BULK-001','evidence':'bulk-execution.json','boundary':'Boolean/timestamp bulk_update CASE type inference'},
            {'id':'TESTING-001','evidence':'testing-helper-findings.json','boundary':'Installed helper cleanup leaves Database.execute writes committed and pool usable on normal/exceptional exit; not a sustained leak measurement'},
            {'id':'SCAFFOLD-001','evidence':'scaffold-editable-defect.json','boundary':'Generated application editable packaging'},
            {'id':'TASK-001','evidence':'task-stale-recovery.json','boundary':'Ordinary stale-lock recovery can duplicate active work and permits an older completion to overwrite the newer result'},
            {'id':'AIPROVIDER001','evidence':'ai-provider-contract.json','boundary':'Experimental compatibility detection reports default Ollama without reachability and rejects keyless custom endpoints'},
        ],
        'remaining_before_candidate':[
            'Finish semantic public-page/reference audit and reconcile stale capability-matrix descriptions with the scoped evidence.',
            'Perform the final usability and requirement-by-requirement review, including every named deliverable and hard scope constraint.',
            'Record deliberate disposition of known functional defects; do not silently fix them in this documentation release.',
            'Only when documentation readiness is established, bump once to 0.7.1rc1 and write the candidate changelog.',
            'Build and validate candidate wheel/sdist and run the established final regression, security, Doctor, migration, MCP, durable, task, RLS and reference-application gates.',
            'Repeat installed examples/scaffold/journeys against the actual candidate; current development/public-wheel successes are not candidate evidence.',
            'Create RELEASE_EVIDENCE_v0.7.1-rc1.md, open the one final PR, inspect hosted checks, and leave it unmerged/unpublished.',
        ],
        'release_evidence_exists':(ROOT/'RELEASE_EVIDENCE_v0.7.1-rc1.md').exists(),
        'scope':'Evidence index and linked-page freshness only. Boolean results retain their individual scopes; historical checks are not fresh-head certification. No automatic release approval.',
    }
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(f'{len(entries)} artifacts indexed; {len(phases)} objective phases; {len(stale)} stale linked inputs; candidate not ready')
    raise SystemExit(bool(stale))


if __name__=='__main__':
    main()
