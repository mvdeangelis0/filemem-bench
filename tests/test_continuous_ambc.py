from pathlib import Path

from amb.continuous.console import Session, dispatch_line
from amb.continuous.layout import init_run_dir


def test_help_and_status(tmp_path: Path, capsys):
    run = init_run_dir(tmp_path, run_id="c1", world="crystal", seed=0)
    session = Session(out_dir=tmp_path, run_dir=run)
    assert dispatch_line(session, "/help") is True
    out = capsys.readouterr().out
    assert "/status" in out
    assert "/inject" in out
    assert dispatch_line(session, "/status") is True
    out = capsys.readouterr().out
    assert "Explore instruments" in out or "Status" in out


def test_inject_via_slash(tmp_path: Path):
    run = init_run_dir(tmp_path, run_id="c2", world="crystal", seed=0)
    session = Session(out_dir=tmp_path, run_dir=run)
    assert dispatch_line(session, "/inject Focus on humidity") is True
    assert "humidity" in (run / "INBOX.md").read_text(encoding="utf-8")


def test_quit(tmp_path: Path):
    session = Session(out_dir=tmp_path)
    assert dispatch_line(session, "/quit") is False


def test_ambc_help_oneshot(capsys):
    from amb.continuous.ambc import main

    main(["help"])
    assert "/help" in capsys.readouterr().out
