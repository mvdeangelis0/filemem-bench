from pathlib import Path

from amb.continuous.console import HELP_TEXT, Session, dispatch_line
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
    assert dispatch_line(session, "/inject --now Focus on humidity") is True
    assert "humidity" in (run / "INBOX.md").read_text(encoding="utf-8")


def test_curriculum_queues_for_next_run(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AMBC_SETTINGS", raising=False)
    session = Session(out_dir=tmp_path)
    assert dispatch_line(session, "/curriculum") is True
    assert "temperature sweep" in session.next_inbox.lower()
    assert dispatch_line(session, "/inject Do a humidity sweep at T=37") is True
    assert session.next_inbox.startswith("Do a humidity")


def test_quit(tmp_path: Path):
    session = Session(out_dir=tmp_path)
    assert dispatch_line(session, "/quit") is False


def test_ambc_help_oneshot(capsys):
    from amb.continuous.ambc import main

    main(["help"])
    assert "/help" in capsys.readouterr().out


def test_pull_command_invokes_git(tmp_path: Path, monkeypatch, capsys):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    calls: list[list[str]] = []

    def fake_run(argv, cwd=None, check=False):  # noqa: ANN001
        calls.append(list(argv))

        class _P:
            returncode = 0

        return _P()

    monkeypatch.setattr("amb.continuous.console.subprocess.run", fake_run)
    session = Session(out_dir=tmp_path)
    assert dispatch_line(session, "/pull") is True
    assert calls and calls[0][:2] == ["git", "pull"]
    out = capsys.readouterr().out
    assert "pulled ok" in out
    assert "/pull" in HELP_TEXT and "/reinstall" in HELP_TEXT


def test_menu_dispatches_status(tmp_path: Path, monkeypatch, capsys):
    run = init_run_dir(tmp_path, run_id="m1", world="crystal", seed=0)
    session = Session(out_dir=tmp_path, run_dir=run)
    monkeypatch.setattr("amb.continuous.console.pick_command", lambda: "status")
    monkeypatch.setattr("amb.continuous.console.prompt_args", lambda _c: "")
    assert dispatch_line(session, "/menu") is True
    out = capsys.readouterr().out
    assert "Status" in out or "Explore instruments" in out


def test_menu_quit_raises_exit_repl(tmp_path: Path, monkeypatch):
    from amb.continuous.console import _ExitRepl, cmd_menu

    session = Session(out_dir=tmp_path)
    monkeypatch.setattr("amb.continuous.console.pick_command", lambda: "quit")
    monkeypatch.setattr("amb.continuous.console.prompt_args", lambda _c: "")
    try:
        cmd_menu(session, [])
        raised = False
    except _ExitRepl:
        raised = True
    assert raised


def test_build_slash_line():
    from amb.continuous.menu import build_slash_line

    assert build_slash_line("status", "") == "/status"
    assert build_slash_line("inject", "Focus humidity") == "/inject Focus humidity"


def test_settings_persist_across_load(tmp_path: Path, monkeypatch):
    from amb.continuous.console import load_session, save_session, settings_path

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AMBC_SETTINGS", raising=False)
    s = Session(out_dir=tmp_path / "continuous_runs")
    assert s.llm == "ollama"
    assert "qwen2.5" in s.model
    assert dispatch_line(s, "/set max_steps 42") is True
    assert settings_path().is_file()
    s2 = load_session(Session())
    assert s2.max_steps == 42
    assert s2.model == s.model
    # explicit path
    other = tmp_path / "alt.json"
    s.model = "llama3.1:8b-instruct-q4_K_M"
    save_session(s, path=other)
    s3 = load_session(Session(), path=other)
    assert s3.model == "llama3.1:8b-instruct-q4_K_M"
