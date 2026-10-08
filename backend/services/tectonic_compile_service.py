import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from uuid import UUID


JOB_ID_PATTERN = re.compile(r"^[0-9a-fA-F-]{36}$")
MAX_ERROR_LENGTH = 4000


def compile_tex(
    job_id: str,
    tex: str,
    compile_root: Path,
    artifact_root: Path,
    deadline: float,
    tectonic_binary: str = "tectonic",
) -> dict[str, str]:
    if not JOB_ID_PATTERN.fullmatch(job_id):
        raise ValueError("Invalid compile job ID")
    UUID(job_id)

    compile_root.mkdir(parents=True, exist_ok=True)
    temp_root = compile_root / "tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    artifact_root.mkdir(parents=True, exist_ok=True)

    tex_path = artifact_root / f"{job_id}.tex"
    pdf_path = artifact_root / f"{job_id}.pdf"
    _write_atomically(tex_path, tex.encode("utf-8"))
    pdf_path.unlink(missing_ok=True)

    try:
        remaining = deadline - time.time()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(tectonic_binary, 0)

        with tempfile.TemporaryDirectory(
            prefix=f"{job_id}-", dir=temp_root
        ) as working_directory:
            source_path = Path(working_directory) / "resume.tex"
            source_path.write_text(tex, encoding="utf-8")
            try:
                result = subprocess.run(
                    [
                        tectonic_binary,
                        "--untrusted",
                        "--outdir",
                        working_directory,
                        str(source_path),
                    ],
                    cwd=working_directory,
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    errors="replace",
                    timeout=remaining,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise TimeoutError("Tectonic compilation exceeded 20 seconds") from exc

            if result.returncode != 0:
                detail = (result.stderr or result.stdout).strip()
                raise RuntimeError(
                    detail[-MAX_ERROR_LENGTH:] or "Tectonic compilation failed"
                )

            compiled_pdf = Path(working_directory) / "resume.pdf"
            if not compiled_pdf.is_file():
                raise RuntimeError("Tectonic completed without producing a PDF")
            _write_atomically(pdf_path, compiled_pdf.read_bytes())
    except (RuntimeError, TimeoutError, OSError, subprocess.TimeoutExpired) as exc:
        pdf_path.unlink(missing_ok=True)
        message = str(exc)[:MAX_ERROR_LENGTH] or "Tectonic compilation failed"
        return {"status": "failed", "error": message}

    return {"status": "succeeded", "error": ""}


def _write_atomically(path: Path, content: bytes) -> None:
    temporary_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary_path.open("wb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
