"""Observe HTTP permission metadata enforcement without database or external effects."""

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = r'''
import asyncio, json, httpx, aksara
from fastapi import FastAPI
from aksara import Model, ModelViewSet, fields, include_viewset
from aksara.api import action
from aksara.permissions import IsAuthenticated

class Probe(Model):
    name = fields.String(max_length=20)

class ProbeView(ModelViewSet):
    model = Probe
    prefix = '/probe'
    permission_classes = [IsAuthenticated]
    stream_enabled = False
    @action(detail=False, methods=['GET'], permission_classes=[IsAuthenticated])
    async def marker(self):
        return {'marker': 'disposable-test'}

async def main():
    app = FastAPI()
    @app.middleware('http')
    async def anonymous(request, call_next):
        request.state.user = None
        return await call_next(request)
    include_viewset(app, ProbeView)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        standard = await client.get('/probe/')
        custom = await client.get('/probe/marker')
    assert standard.status_code == 403
    print(json.dumps({'package_version': aksara.__version__, 'package_path': aksara.__file__,
                      'generated_list_status': standard.status_code,
                      'custom_action_status': custom.status_code,
                      'runtime_boundary_pass': custom.status_code == 403}))
asyncio.run(main())
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    env = {k: v for k, v in os.environ.items()
           if k not in {"PYTHONPATH", "DATABASE_URL"} and not k.startswith("AKSARA_")}
    with tempfile.TemporaryDirectory(prefix="aksara-action-boundary-") as directory:
        run = subprocess.run([str(args.python.absolute()), "-I", "-c", PROBE],
                             cwd=directory, env=env, capture_output=True, text=True,
                             timeout=30, check=True)
    evidence = json.loads(run.stdout)
    assert not Path(evidence.pop("package_path")).is_relative_to(ROOT)
    evidence.update({"schema_version": 1, "defect": "ACTION-001", "severity": "P1",
                     "source_checkout_framework_imports": False,
                     "scope": "Anonymous in-process HTTP request to inert custom action; no database, network provider, or data mutation"})
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence))
    raise SystemExit(not evidence["runtime_boundary_pass"])


if __name__ == "__main__":
    main()
