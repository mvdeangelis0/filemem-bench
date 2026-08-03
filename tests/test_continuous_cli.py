from pathlib import Path

from amb.cli import main
from amb.continuous.layout import init_run_dir


def test_cli_inject(tmp_path: Path):
    run = init_run_dir(tmp_path, run_id="c1", world="crystal", seed=0)
    main(["continuous", "inject", "--run", str(run), "Try humidity next"])
    assert "humidity" in (run / "INBOX.md").read_text(encoding="utf-8")


def test_cli_mock_run(tmp_path: Path):
    # Empty MockLLM will protocol-fail then stop; still creates a run dir.
    main(
        [
            "continuous",
            "run",
            "--world",
            "crystal",
            "--llm",
            "mock",
            "--max-steps",
            "3",
            "--out",
            str(tmp_path / "continuous_runs"),
            "--run-id",
            "cli_mock",
        ]
    )
    run = tmp_path / "continuous_runs" / "cli_mock"
    assert (run / "REPORT.md").is_file()
    assert (run / "STATUS.md").is_file()
