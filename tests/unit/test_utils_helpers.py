from src.utils.helpers import (
    generate_incident_id,
    safe_get,
    normalize_whitespace,
    chunk_list,
    flatten_dict,
)


def test_generate_incident_id():
    id1 = generate_incident_id()
    id2 = generate_incident_id()
    assert isinstance(id1, str) and isinstance(id2, str)
    assert id1 != id2
    assert "-" in id1


def test_safe_get():
    assert safe_get(None, "x", 5) == 5
    assert safe_get({"a": 1}, "a", 0) == 1
    assert safe_get({"a": 1}, "b", 2) == 2


def test_normalize_whitespace():
    assert normalize_whitespace(None) is None
    assert normalize_whitespace("  a   b  c ") == "a b c"


def test_chunk_list():
    assert chunk_list([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]


def test_flatten_dict():
    d = {"a": 1, "b": {"c": 2, "d": {"e": 3}}}
    f = flatten_dict(d)
    assert f["b_c"] == 2
    assert f["b_d_e"] == 3
