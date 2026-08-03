from amb.continuous.lab.crystal import CrystalLab


def load_world(world: str, lab_dir, *, seed: int):
    if world == "crystal":
        return CrystalLab(lab_dir, seed=seed)
    raise ValueError(f"unknown world: {world}")
