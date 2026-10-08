import shutil
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import pytest

from backend.services.tectonic_compile_service import compile_tex


def test_compile_uses_untrusted_mode_and_cleans_temporary_directory(
    monkeypatch, tmp_path: Path
):
    job_id = str(uuid4())
    observed = {}

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed["kwargs"] = kwargs
        output_directory = Path(command[command.index("--outdir") + 1])
        (output_directory / "resume.pdf").write_bytes(b"%PDF-test")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = compile_tex(
        job_id,
        r"\documentclass{article}",
        tmp_path / "compile",
        tmp_path / "artifacts",
        time.time() + 20,
    )

    assert result["status"] == "succeeded"
    assert observed["command"][1] == "--untrusted"
    assert observed["kwargs"]["timeout"] <= 20
    assert list((tmp_path / "compile" / "tmp").iterdir()) == []
    assert (tmp_path / "artifacts" / f"{job_id}.tex").exists()
    assert (tmp_path / "artifacts" / f"{job_id}.pdf").read_bytes() == b"%PDF-test"


def test_compile_failure_keeps_tex_and_does_not_leave_pdf_or_temp_files(
    monkeypatch, tmp_path: Path
):
    job_id = str(uuid4())

    def fake_run(command, **kwargs):
        output_directory = Path(command[command.index("--outdir") + 1])
        (output_directory / "resume.pdf").write_bytes(b"incomplete")
        return subprocess.CompletedProcess(
            command, 1, stdout="", stderr="invalid document"
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = compile_tex(
        job_id,
        "invalid",
        tmp_path / "compile",
        tmp_path / "artifacts",
        time.time() + 20,
    )

    assert result == {"status": "failed", "error": "invalid document"}
    assert (tmp_path / "artifacts" / f"{job_id}.tex").read_text() == "invalid"
    assert not (tmp_path / "artifacts" / f"{job_id}.pdf").exists()
    assert list((tmp_path / "compile" / "tmp").iterdir()) == []


@pytest.mark.skipif(shutil.which("tectonic") is None, reason="Tectonic engine is not installed")
def test_tectonic_compiles_a_minimal_tex_document_when_engine_is_available(
    tmp_path: Path,
):
    job_id = str(uuid4())
    result = compile_tex(
        job_id,
        r"\documentclass{article}\begin{document}Hello\end{document}",
        tmp_path / "compile",
        tmp_path / "artifacts",
        time.time() + 20,
    )

    assert result["status"] == "succeeded"
    assert (tmp_path / "artifacts" / f"{job_id}.pdf").read_bytes().startswith(b"%PDF")
