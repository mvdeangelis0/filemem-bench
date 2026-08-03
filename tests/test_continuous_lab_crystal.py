from pathlib import Path

from amb.continuous.lab.crystal import CrystalLab


def test_crystal_deterministic(tmp_path: Path):
    a = CrystalLab(tmp_path / "a", seed=7)
    b = CrystalLab(tmp_path / "b", seed=7)
    a.act({"temperature": 37, "humidity": 50})
    b.act({"temperature": 37, "humidity": 50})
    assert a.sense()["growth"] == b.sense()["growth"]


def test_near_ideal_beats_bad(tmp_path: Path):
    good = CrystalLab(tmp_path / "g", seed=1)
    bad = CrystalLab(tmp_path / "x", seed=1)
    good.act({"temperature": 37, "humidity": 50})
    bad.act({"temperature": 10, "humidity": 10})
    assert good.sense()["growth"] > bad.sense()["growth"]


def test_hidden_laws_not_in_public_state(tmp_path: Path):
    lab = CrystalLab(tmp_path / "l", seed=0)
    sense = lab.sense()
    assert "law" not in sense
    assert "ideal" not in str(sense).lower()
