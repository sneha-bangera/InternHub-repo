import json
import os
import time
from pathlib import Path

from tectonic_compile_service import compile_tex


COMPILE_ROOT = Path(os.environ.get("RESUME_COMPILE_DIR", "/var/lib/internhub/compile"))
ARTIFACT_ROOT = Path(
    os.environ.get("RESUME_ARTIFACT_DIR", "/var/lib/internhub/artifacts")
)
INBOX = COMPILE_ROOT / "inbox"
RESPONSES = COMPILE_ROOT / "responses"


def _write_response(job_id: str, response: dict[str, str]) -> None:
    response_path = RESPONSES / f"{job_id}.json"
    temporary_path = RESPONSES / f".{job_id}.{os.getpid()}.tmp"
    temporary_path.write_text(json.dumps(response), encoding="utf-8")
    os.replace(temporary_path, response_path)


def _process_request(request_path: Path) -> None:
    claimed_path = request_path.with_suffix(".processing")
    try:
        os.replace(request_path, claimed_path)
    except FileNotFoundError:
        return

    job_id = claimed_path.stem
    try:
        request = json.loads(claimed_path.read_text(encoding="utf-8"))
        if request.get("job_id") != job_id:
            raise ValueError("Compile request ID does not match its filename")
        response = compile_tex(
            job_id=job_id,
            tex=request["tex"],
            compile_root=COMPILE_ROOT,
            artifact_root=ARTIFACT_ROOT,
            deadline=float(request["deadline"]),
        )
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as exc:
        response = {"status": "failed", "error": str(exc)[:4000]}
    except Exception as exc:
        response = {"status": "failed", "error": str(exc)[:4000]}
    finally:
        claimed_path.unlink(missing_ok=True)
    _write_response(job_id, response)


def main() -> None:
    INBOX.mkdir(parents=True, exist_ok=True)
    RESPONSES.mkdir(parents=True, exist_ok=True)
    (COMPILE_ROOT / "tmp").mkdir(parents=True, exist_ok=True)
    while True:
        requests = sorted(INBOX.glob("*.json"))
        if requests:
            _process_request(requests[0])
        else:
            time.sleep(0.1)


if __name__ == "__main__":
    main()
