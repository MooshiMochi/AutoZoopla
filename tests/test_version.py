from relister.__version__ import __version__


def test_version_is_a_nonempty_string():
    assert isinstance(__version__, str)
    assert __version__
    # dotted numeric form, e.g. "0.1.0"
    assert all(part.isdigit() for part in __version__.split("."))
