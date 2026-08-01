from amb import __version__


def test_version_semver_prefix():
    assert __version__.startswith("0.")
