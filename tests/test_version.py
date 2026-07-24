import re

from relister.__version__ import __version__


def test_version_is_a_nonempty_string():
    assert isinstance(__version__, str)
    assert __version__
    # dotted numeric form with an optional pre-release suffix, e.g. "0.1.0" or
    # "0.1.1a".
    assert re.fullmatch(r"\d+(\.\d+)*[a-z]?\d*", __version__), __version__
