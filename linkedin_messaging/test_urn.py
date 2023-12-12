from .api_objects import URN


def test_urn_equivalence():
    assert URN("urn:123") == URN("123")
    assert URN("urn:(123,456)") == URN("urn:test:(123,456)")


def test_urn_equivalence_in_tuple():
    assert (URN("urn:123"), URN("urn:(123,456)")) == (
        URN("123"),
        URN("urn:test:(123,456)"),
    )
