#!/usr/bin/env python3
"""Railway entrypoint for API and cron services.

The default mode starts the FastAPI web server. A second Railway service can set
RAILWAY_RUN_MODE=worker-cron to process queued evaluation jobs and exit.
"""

import asyncio
import json
import os
import sys


def run_api() -> None:
    port = os.getenv("PORT", "8000")
    os.execvp(
        "uvicorn",
        ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", port],
    )


async def run_worker_cron() -> None:
    from api import EvaluationJobsProcessRequest, process_evaluation_jobs

    limit = int(os.getenv("EVALUATION_JOBS_CRON_LIMIT", "3"))
    worker_id = os.getenv("EVALUATION_JOBS_WORKER_ID", "railway-cron")
    result = await process_evaluation_jobs(
        EvaluationJobsProcessRequest(
            limit=limit,
            worker_id=worker_id,
            source="railway-cron",
        )
    )
    print(json.dumps(result, ensure_ascii=False, default=str))


def main() -> None:
    mode = os.getenv("RAILWAY_RUN_MODE", "api").strip().lower()
    if mode == "worker-cron":
        asyncio.run(run_worker_cron())
        return

    if mode != "api":
        print(f"Unknown RAILWAY_RUN_MODE={mode!r}. Expected 'api' or 'worker-cron'.", file=sys.stderr)
        sys.exit(1)

    run_api()


if __name__ == "__main__":
    main()
