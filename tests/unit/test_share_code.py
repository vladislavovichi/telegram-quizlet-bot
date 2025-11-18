
import pytest

from app.services.share_code import (_b64d, _b64e, make_share_code,
                                     parse_share_code)


def test_b64_roundtrip():
    raw = b"hello\x00world"
    enc = _b64e(raw)
    assert "=" not in enc
    dec = _b64d(enc)
    assert dec == raw


def test_make_and_parse_share_code_valid():
    secret = "secret"
    code = make_share_code(collection_id=10, owner_id=20, secret=secret)
    cid, oid = parse_share_code(code, secret)
    assert cid == 10
    assert oid == 20


def test_parse_share_code_wrong_secret():
    secret = "secret"
    other = "wrong"
    code = make_share_code(1, 2, secret=secret)
    assert parse_share_code(code, other) is None


@pytest.mark.parametrize("code", ["", "!!!", "not_base64"])
def test_parse_share_code_garbage(code):
    assert parse_share_code(code, "secret") is None
