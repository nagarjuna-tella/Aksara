"""One-shot process worker for v0.7.2 ordinary-task ownership tests."""

from __future__ import annotations

import argparse
import asyncio
import json
import os

from aksara.db import Database
from aksara.tasks import TaskWorker, clear_task_registry, task


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--lease-seconds", type=float, default=0.4)
    args = parser.parse_args()

    database = Database(os.environ["DATABASE_URL"], min_size=1, max_size=4)
    await database.connect()
    try:

        @task(name="tests.v072.process_task", max_attempts=5)
        async def process_task(case_id: str) -> dict[str, str]:
            await database.execute(
                """
                INSERT INTO task_process_effects (case_id, worker_id)
                VALUES ($1, $2)
                """,
                case_id,
                args.worker_id,
            )
            await database.execute(
                """
                UPDATE task_process_control
                SET started_at = clock_timestamp()
                WHERE case_id = $1 AND worker_id = $2
                """,
                case_id,
                args.worker_id,
            )
            while not await database.fetchval(
                """
                SELECT released FROM task_process_control
                WHERE case_id = $1 AND worker_id = $2
                """,
                case_id,
                args.worker_id,
            ):
                await asyncio.sleep(0.025)
            outcome = await database.fetchval(
                """
                SELECT outcome FROM task_process_control
                WHERE case_id = $1 AND worker_id = $2
                """,
                case_id,
                args.worker_id,
            )
            if outcome == "fail":
                raise RuntimeError(f"worker {args.worker_id} failed")
            return {"worker_id": args.worker_id}

        worker = TaskWorker(
            database,
            worker_id=args.worker_id,
            stale_lock_timeout_seconds=args.lease_seconds,
            retry_delay_seconds=0.0,
        )
        record = await worker.poll_once()
        print(
            "TASK_PROCESS_RESULT="
            + json.dumps(
                {
                    "worker_id": args.worker_id,
                    "claimed": record is not None,
                    "status": record.status if record is not None else None,
                    "result": record.result if record is not None else None,
                },
                sort_keys=True,
            ),
            flush=True,
        )
    finally:
        clear_task_registry()
        await database.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
