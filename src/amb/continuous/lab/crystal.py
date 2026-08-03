from __future__ import annotations

import json
import random
from pathlib import Path

# Hidden — do not expose via sense()
_IDEAL_TEMP = 37.0
_HUM_LO, _HUM_HI = 40.0, 60.0


class CrystalLab:
    def __init__(self, lab_dir: Path, *, seed: int) -> None:
        self.lab_dir = Path(lab_dir)
        self.lab_dir.mkdir(parents=True, exist_ok=True)
        self.rng = random.Random(seed)
        self.state_path = self.lab_dir / "state.json"
        if not self.state_path.exists():
            self._save({"temperature": 25.0, "humidity": 30.0, "growth": 0.0, "trials": 0})

    def _load(self) -> dict:
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def _save(self, state: dict) -> None:
        self.state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    def _true_growth(self, temp: float, humidity: float) -> float:
        temp_term = max(0.0, 1.0 - abs(temp - _IDEAL_TEMP) / 20.0)
        hum_term = 1.0 if _HUM_LO <= humidity <= _HUM_HI else 0.2
        return max(0.0, temp_term * (0.5 + 0.5 * hum_term))

    def act(self, args: dict) -> dict:
        st = self._load()
        if "temperature" in args:
            st["temperature"] = float(args["temperature"])
        if "humidity" in args:
            st["humidity"] = float(args["humidity"])
        true = self._true_growth(st["temperature"], st["humidity"])
        noise = self.rng.gauss(0, 0.05)
        st["growth"] = max(0.0, min(1.5, true + noise))
        st["trials"] = int(st.get("trials", 0)) + 1
        self._save(st)
        return {"ok": True, "informative": True, "state": self.sense()}

    def sense(self) -> dict:
        st = self._load()
        return {
            "temperature": st["temperature"],
            "humidity": st["humidity"],
            "growth": st["growth"],
            "trials": st["trials"],
        }
