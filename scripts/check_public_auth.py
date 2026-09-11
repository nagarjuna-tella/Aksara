"""Execute the documented account and permission helpers against an installed wheel."""

import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import asyncpg

ROOT = Path(__file__).resolve().parents[1]
SNIPPETS = {
    "accounts.py": ("docs/docs/api/authentication.md", "app/accounts.py"),
    "permissions.py": ("docs/docs/api/permissions.md", "app/permissions.py"),
}
PROBE = r'''
import asyncio, json, os, runpy, secrets
from pathlib import Path
from types import SimpleNamespace
import aksara
from aksara import Model, fields
from aksara.api import ModelViewSet
from aksara.conf import configure
from aksara.contrib.auth import (
    User, create_session_token, get_user_from_session_token, invalidate_session_token,
    require_auth,
)
from aksara.db import Database
from aksara.migrations import apply_migrations
from starlette.requests import Request
from starlette.exceptions import HTTPException

accounts = runpy.run_path('accounts.py')
permission = runpy.run_path('permissions.py')['IsActiveOwner']
checks = []
def passed(name, condition):
    assert condition, name
    checks.append(name)

def request(user):
    req = Request({'type': 'http', 'method': 'PATCH', 'path': '/', 'headers': []})
    req.state.user = user
    return req

class OwnershipProbe(Model):
    owner_id = fields.UUID(nullable=True)

class OwnershipView(ModelViewSet):
    model = OwnershipProbe
    permission_classes = [permission]

async def main():
    configure(installed_apps=['aksara.contrib.auth'])
    db = Database(os.environ['DATABASE_URL'], min_size=1, max_size=2)
    await db.connect()
    try:
        Path('migrations').mkdir()
        migration = await apply_migrations(db, Path('migrations'), verbose=False)
        passed('internal migrations apply', not migration['errors'])
        password = secrets.token_urlsafe(24)
        user = await accounts['create_account'](' AUTH-PROBE@EXAMPLE.COM ', password)
        passed('email normalized', user.email == 'auth-probe@example.com')
        stored = await User.objects.get(id=user.id)
        passed('password stored as hash', stored.hashed_password != password)
        passed('correct password verifies', accounts['password_matches'](stored, password))
        passed('wrong password rejected', not accounts['password_matches'](stored, 'wrong'))
        passed('unprivileged defaults', stored.is_active and not stored.is_staff and not stored.is_superuser)
        authenticated = await accounts['authenticate_account']('AUTH-PROBE@EXAMPLE.COM', password)
        passed('active account authenticates', authenticated is not None and authenticated.id == user.id)
        passed('incorrect credentials rejected', await accounts['authenticate_account'](user.email, 'wrong') is None)
        passed('missing account rejected', await accounts['authenticate_account']('missing@example.com', password) is None)
        session = await create_session_token(db, user)
        session_user = await get_user_from_session_token(db, session)
        passed('session resolves active account', session_user is not None and session_user.id == user.id)
        await invalidate_session_token(db, session)
        passed('revoked session rejected', await get_user_from_session_token(db, session) is None)
        await User.objects.filter(id=user.id).update(is_active=False)
        passed('inactive credentials rejected', await accounts['authenticate_account'](user.email, password) is None)
        denied = False
        try:
            await require_auth()(request(None))
        except HTTPException as exc:
            denied = exc.status_code == 401
        passed('missing attached user dependency denies 401', denied)
        active = SimpleNamespace(id=user.id, is_authenticated=True, is_active=True)
        passed('dependency reads attached identity', await require_auth()(request(active)) is active)
        view = OwnershipView()
        obj = OwnershipProbe(owner_id=user.id)
        view.check_permissions(request(active))
        view.check_object_permissions(request(active), obj)
        passed('active owner passes both permission hooks', True)
        from uuid import uuid4
        cases = [
            ('different owner denied', active, OwnershipProbe(owner_id=uuid4()), 'object'),
            ('missing owner denied', active, OwnershipProbe(owner_id=None), 'object'),
            ('anonymous denied', None, obj, 'view'),
            ('inactive owner denied', SimpleNamespace(id=user.id, is_authenticated=True, is_active=False), obj, 'view'),
        ]
        for name, caller, target, phase in cases:
            denied = False
            try:
                if phase == 'view':
                    view.check_permissions(request(caller))
                else:
                    view.check_object_permissions(request(caller), target)
            except HTTPException as exc:
                denied = exc.status_code == 403 and exc.detail == permission.message
            passed(name, denied)
    finally:
        await db.disconnect()
    print('AUTH_EVIDENCE=' + json.dumps({'checks': checks, 'package_version': aksara.__version__,
                                        'package_path': aksara.__file__}))

asyncio.run(main())
'''


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dsn = os.environ.get("AKSARA_DATABASE_URL") or os.environ["DATABASE_URL"]
    schema = "aksara_v071_auth_" + uuid4().hex[:12]
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
            with tempfile.TemporaryDirectory(prefix="aksara-auth-docs-") as directory:
                root = Path(directory)
                for filename, (page, title) in SNIPPETS.items():
                    text = (ROOT / page).read_text()
                    source = re.search(r'```python title="' + re.escape(title) + r'"\n(.*?)```', text, re.DOTALL).group(1)
                    (root / filename).write_text(source)
                run = await asyncio.to_thread(
                    subprocess.run, [str(args.python.absolute()), "-I", "-c", PROBE],
                    cwd=root, env=env, capture_output=True, text=True, timeout=60,
                )
                if run.returncode:
                    message = (run.stderr or run.stdout).replace(scoped, "[REDACTED]").replace(dsn, "[REDACTED]")
                    raise RuntimeError(message)
                evidence = json.loads(next(line.removeprefix("AUTH_EVIDENCE=") for line in run.stdout.splitlines()
                                           if line.startswith("AUTH_EVIDENCE=")))
                assert not Path(evidence.pop("package_path")).is_relative_to(ROOT)
        finally:
            await connection.execute(f'DROP SCHEMA "{schema}" CASCADE')
        assert not await connection.fetchval("SELECT 1 FROM pg_namespace WHERE nspname = $1", schema)
    finally:
        await connection.close()
    evidence.update({"schema_version": 1, "pass": True,
                     "source_checkout_framework_imports": False, "disposable_schema_removed": True,
                     "scope": "PostgreSQL account/session primitives and direct permission/dependency checks; not HTTP login, JWT/provider integration, RLS or complete application authorization",
                     "page_sha256": {page: hashlib.sha256((ROOT / page).read_bytes()).hexdigest() for page, _ in SNIPPETS.values()},
                     "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS: {len(evidence['checks'])} installed account/session/permission checks; disposable schema removed")


if __name__ == "__main__":
    asyncio.run(main())
