"""Execute documented query diagnostics against a read-only PostgreSQL connection and installed wheel."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
PAGE = 'docs/docs/debugging/query-profiling.md'
PROBE = r'''
import asyncio, json, os, types
from pathlib import Path
import aksara
from aksara.conf import Settings, configure
from aksara.db import (Database, capture_queries, start_trace_session, stop_trace_session,
    get_trace_by_request_id, get_recent_traces, clear_traces)
from aksara.exceptions import DatabaseError
from httpx import AsyncClient, ASGITransport
modules={}
for filename in ('query_examples', 'request_queries'):
    module=types.ModuleType(filename)
    exec(compile(Path(filename+'.py').read_text(),filename+'.py','exec'),module.__dict__)
    modules[filename]=module
checks=[]
def passed(name,condition):
    assert condition,name
    checks.append(name)
async def main():
    configure(Settings(db_trace_enabled=True))
    db=Database(os.environ['DATABASE_URL'],min_size=1,max_size=2)
    await db.connect()
    try:
        passed('connection is read only',await db.fetchval('SHOW default_transaction_read_only')=='on')
        log,batch=await modules['query_examples'].inspect_queries(db)
        passed('exact two-query example executes',log.count==batch.total_queries==2)
        passed('capture records parameters without timing',log.queries[0].params==(7,) and log.queries[0].duration_ms is None)
        passed('tracing records timing and unredacted parameters',batch.queries[1].params==('example',) and all(q.duration_ms>=0 for q in batch.queries))
        passed('database path does not populate row counts',all(q.rows_affected is None for q in batch.queries))
        passed('identified session retained in same process',get_trace_by_request_id('local-example') is batch)
        passed('stopped session is reset',stop_trace_session() is None)
        clear_traces()
        start_trace_session()
        await db.fetchval('SELECT 1')
        anonymous=stop_trace_session()
        passed('anonymous batch returned but not retained',anonymous.total_queries==1 and not get_recent_traces())
        configure(Settings(db_trace_enabled=False))
        start_trace_session(request_id='disabled')
        async with capture_queries() as disabled_log:
            await db.fetchval('SELECT 1')
        passed('capture works while trace disabled',disabled_log.count==1 and stop_trace_session() is None)
        configure(Settings(db_trace_enabled=True,db_trace_max_queries=2,db_trace_slow_threshold_ms=0))
        start_trace_session(request_id='capped')
        configure(Settings(db_trace_enabled=True,db_trace_max_queries=50,db_trace_slow_threshold_ms=999999))
        for _ in range(3):await db.fetchval('SELECT 1')
        capped=stop_trace_session()
        passed('session snapshots count cap and slow threshold',capped.total_queries==2 and capped.slow_queries==2)
        start_trace_session(request_id='bypass')
        async with capture_queries() as bypass_log:
            async with db.acquire() as connection:
                value=await connection.fetchval('SELECT 42')
        bypass=stop_trace_session()
        passed('direct driver calls bypass both collectors',value==42 and bypass_log.count==bypass.total_queries==0)
        start_trace_session(request_id='failed')
        try:
            async with capture_queries() as failed_log:
                await db.fetchval('SELECT 1 / 0')
        except DatabaseError:
            failed=stop_trace_session()
            passed('failed database call recorded',failed_log.count==failed.total_queries==1)
        else:raise AssertionError('expected real PostgreSQL division failure')
        async with capture_queries() as outer:
            await db.fetchval('SELECT 1')
            async with capture_queries() as inner:
                await db.fetchval('SELECT 2')
            await db.fetchval('SELECT 3')
        passed('nested capture excludes inner calls from outer',outer.count==2 and inner.count==1)
        async with capture_queries() as shared:
            await asyncio.create_task(db.fetchval('SELECT 4'))
        passed('capture includes calls from another task',shared.count==1)
        configure(Settings(db_trace_enabled=True))
        clear_traces()
        app=modules['request_queries'].create_query_example(db)
        async with AsyncClient(transport=ASGITransport(app=app),base_url='http://example.test') as client:
            response=await client.get('/query-example',headers={'X-Request-ID':'docs-request'})
            first=get_trace_by_request_id('docs-request')
            passed('exact middleware example correlates request',response.status_code==200 and response.json()=={'value':7} and response.headers['X-Request-ID']=='docs-request' and first.total_queries==1 and first.path=='/query-example' and first.method=='GET' and first.status_code==200)
            await client.get('/query-example',headers={'X-Request-ID':'docs-request'})
            passed('reused client request ID replaces stored batch',get_trace_by_request_id('docs-request') is not first and len(get_recent_traces())==1)
            generated=await client.get('/query-example')
            passed('missing request ID generated',get_trace_by_request_id(generated.headers['X-Request-ID']).total_queries==1)
        plan=await db.fetch('EXPLAIN (FORMAT JSON) SELECT 1')
        passed('explicit PostgreSQL plan query executes',bool(plan) and 'Plan' in json.loads(plan[0][0])[0])
        clear_traces()
        passed('clear removes process-local history',not get_recent_traces())
    finally:
        stop_trace_session()
        clear_traces()
        await db.disconnect()
    print('QUERY_DOC_EVIDENCE='+json.dumps({'checks':checks,'package_version':aksara.__version__,'package_path':aksara.__file__}))
asyncio.run(main())
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    dsn = os.environ.get('AKSARA_DATABASE_URL') or os.environ['DATABASE_URL']
    url = urlsplit(dsn)
    query = dict(parse_qsl(url.query))
    query['default_transaction_read_only'] = 'on'
    readonly_dsn = urlunsplit(url._replace(query=urlencode(query)))
    env = {k: v for k, v in os.environ.items()
           if k not in {'PYTHONPATH', 'DATABASE_URL'} and not k.startswith('AKSARA_')}
    env['DATABASE_URL'] = readonly_dsn
    with tempfile.TemporaryDirectory(prefix='aksara-query-docs-') as directory:
        root = Path(directory)
        for filename in ('query_examples.py', 'request_queries.py'):
            source = re.search(r'```python title="' + re.escape(filename) + r'"\n(.*?)```',
                               (ROOT / PAGE).read_text(), re.DOTALL)
            assert source, filename
            (root / filename).write_text(source[1])
        run = subprocess.run([str(args.python.absolute()), '-I', '-c', PROBE],
                             cwd=root, env=env, capture_output=True, text=True, timeout=60, check=False)
        if run.returncode:
            raise RuntimeError((run.stderr or run.stdout).replace(readonly_dsn, '[REDACTED]').replace(dsn, '[REDACTED]'))
        standalone = subprocess.run([str(args.python.absolute()), '-I', 'query_examples.py'],
                                    cwd=root, env=env, capture_output=True, text=True, timeout=60, check=False)
        if standalone.returncode:
            raise RuntimeError((standalone.stderr or standalone.stdout).replace(readonly_dsn, '[REDACTED]').replace(dsn, '[REDACTED]'))
        assert 'Captured calls: 2' in standalone.stdout
        assert 'Recorded duration:' in standalone.stdout
        evidence = json.loads(next(line.removeprefix('QUERY_DOC_EVIDENCE=') for line in run.stdout.splitlines()
                                   if line.startswith('QUERY_DOC_EVIDENCE=')))
        assert not Path(evidence.pop('package_path')).is_relative_to(ROOT)
    evidence.update({
        'schema_version': 1, 'pass': True, 'source_checkout_framework_imports': False,
        'read_only_database': True, 'database_objects_created': False,
        'standalone_documented_script_pass': True,
        'scope': 'Exact manual and HTTP examples, read-only PostgreSQL calls, capture/tracing limits and retention; no ORM N+1 benchmark, streaming/cancellation guarantee, Studio, authorization or production observability certification',
        'page_sha256': {PAGE: hashlib.sha256((ROOT / PAGE).read_bytes()).hexdigest()},
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    })
    args.output.write_text(json.dumps(evidence, indent=2) + '\n')
    print(f"PASS: {len(evidence['checks'])} installed query-profiling checks; read-only PostgreSQL")


if __name__ == '__main__':
    main()
