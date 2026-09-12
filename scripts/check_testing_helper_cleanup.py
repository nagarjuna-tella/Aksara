"""Reproduce testing-helper cleanup limitations in an isolated installed package."""

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import asyncpg

ROOT = Path(__file__).resolve().parents[1]
PROBE = r'''
import asyncio, json, os
import aksara
from aksara.db import Database
from aksara.testing import test_database

class DeliberateFailure(Exception):
    pass

async def main():
    dsn=os.environ['DATABASE_URL']
    observer=Database(dsn,min_size=1,max_size=2)
    await observer.connect()
    checks=[]
    try:
        await observer.execute('CREATE TABLE helper_probe (name text PRIMARY KEY)')
        for failing in (False, True):
            helper=None
            label='exception' if failing else 'normal'
            try:
                try:
                    async with test_database(dsn,cleanup=True) as helper:
                        await helper.execute('INSERT INTO helper_probe(name) VALUES($1)',label)
                        if failing:
                            raise DeliberateFailure()
                except DeliberateFailure:
                    assert failing
                assert await observer.fetchval('SELECT count(*) FROM helper_probe WHERE name=$1',label)==1
                checks.append(label+' exit leaves write committed')
                assert await helper.fetchval('SELECT 1')==1
                checks.append(label+' exit leaves helper pool usable')
            finally:
                if helper is not None:
                    await helper.disconnect()
        async with test_database(dsn,cleanup=False) as helper:
            await helper.execute("INSERT INTO helper_probe(name) VALUES('no_cleanup')")
        try:
            helper.pool
        except RuntimeError as error:
            assert 'not connected' in str(error)
        else:
            raise AssertionError('cleanup=False did not disconnect')
        checks.append('cleanup=False disconnects normally')
        assert await observer.fetchval('SELECT count(*) FROM helper_probe')==3
    finally:
        await observer.disconnect()
    print('TESTING_HELPER_EVIDENCE='+json.dumps({
        'checks':checks,'package_version':aksara.__version__,'package_path':aksara.__file__,
        'runtime_rollback_isolation_pass':False,'runtime_cleanup_disconnect_pass':False,
        'probe_owned_connections_closed':True}))
asyncio.run(main())
'''


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dsn = os.environ.get("AKSARA_DATABASE_URL") or os.environ["DATABASE_URL"]
    schema = "aksara_v071_testing_helper_" + uuid4().hex[:12]
    connection = await asyncpg.connect(dsn)
    try:
        await connection.execute(f'CREATE SCHEMA "{schema}"')
        try:
            url = urlsplit(dsn)
            query = dict(parse_qsl(url.query))
            query["search_path"] = schema
            scoped = urlunsplit(url._replace(query=urlencode(query)))
            env = {k: v for k, v in os.environ.items()
                   if k not in {"PYTHONPATH", "DATABASE_URL"} and not k.startswith("AKSARA_")}
            env["DATABASE_URL"] = scoped
            with tempfile.TemporaryDirectory(prefix="aksara-testing-helper-") as directory:
                root = Path(directory)
                run = await asyncio.to_thread(
                    subprocess.run, [str(args.python.absolute()), "-I", "-c", PROBE],
                    cwd=root, env=env, capture_output=True, text=True, timeout=60, check=False,
                )
                if run.returncode:
                    message = (run.stderr or run.stdout).replace(scoped, "[REDACTED]").replace(dsn, "[REDACTED]")
                    raise RuntimeError(message)
                evidence = json.loads(next(line.removeprefix("TESTING_HELPER_EVIDENCE=") for line in run.stdout.splitlines()
                                           if line.startswith("TESTING_HELPER_EVIDENCE=")))
                assert not Path(evidence.pop("package_path")).is_relative_to(ROOT)
        finally:
            await connection.execute(f'DROP SCHEMA "{schema}" CASCADE')
        assert not await connection.fetchval("SELECT 1 FROM pg_namespace WHERE nspname = $1", schema)
    finally:
        await connection.close()
    evidence.update({"schema_version": 1, "pass": True,
                     "source_checkout_framework_imports": False, "disposable_schema_removed": True,
                     "scope": "Negative cleanup=True probe on normal and exceptional exit: direct Database.execute writes persist and the helper pool remains usable. cleanup=False disconnection is a control. Admin role, owned schema; not HTTP, ORM model writes, RLS or a sustained resource-leak measurement",
                     "source_sha256": {"aksara/testing.py": hashlib.sha256((ROOT / "aksara/testing.py").read_bytes()).hexdigest()},
                     "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: {len(evidence['checks'])} installed testing-helper negative/control checks; disposable schema removed")


if __name__ == "__main__":
    asyncio.run(main())
