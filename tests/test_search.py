"""Search API against a tiny Syriac fixture index. No network required."""

from fastapi.testclient import TestClient

import backend

RISH = "\u072a\u071d\u072b"
BRESHIT = "\u0712\u072a\u071d\u072b\u071d\u072c"
ALAHA = "\u0710\u0720\u0717\u0710"
KLILA = "\u071f\u0720\u071d\u0720\u0710"


def _client():
    return TestClient(backend.app)


def test_health_and_books():
    health = _client().get("/api/health").json()
    assert health["status"] == "ok"
    assert health["verses"] == 5
    books = _client().get("/api/books").json()
    codes = [b["code"] for b in books]
    assert codes[0] == "GEN"
    assert "MAT" in codes
    assert len(books) == 3


def test_root_match_expands_sedra_root_family():
    """Root family: head form finds beginning form and vice versa."""
    client = _client()
    rosh = client.get("/api/search", params={"q": RISH, "mode": "lemma"}).json()
    ids = [row["verse_id"] for row in rosh["results"]]
    assert "GEN.2.10" in ids
    assert "GEN.1.1" in ids
    assert BRESHIT in rosh["forms"]
    assert any(lem["strongs"] == "L3017" for lem in rosh["lemmas"])

    reshit = client.get(
        "/api/search", params={"q": BRESHIT, "mode": "lemma"}
    ).json()
    assert "GEN.1.1" in [row["verse_id"] for row in reshit["results"]]
    assert "GEN.2.10" in [row["verse_id"] for row in reshit["results"]]


def test_exact_does_not_expand_root():
    body = _client().get(
        "/api/search", params={"q": RISH, "mode": "exact"}
    ).json()
    assert [row["verse_id"] for row in body["results"]] == ["GEN.2.10"]
    assert body["results"][0]["matches"] == [RISH]


def test_vocalized_query_strips_to_consonants():
    # ܐܰܠܳܗܳܐ = aleph + pthaha + lamadh + zqapha + he + zqapha + aleph
    vocal = "\u0710\u0730\u0720\u0733\u0717\u0733\u0710"
    body = _client().get(
        "/api/search", params={"q": vocal, "mode": "lemma"}
    ).json()
    assert body["normalized"] == ALAHA
    assert body["total"] == 2
    assert [row["verse_id"] for row in body["results"]] == ["GEN.1.1", "GEN.1.3"]


def test_legacy_fuzziness_maps_to_root():
    root = _client().get("/api/search", params={"q": ALAHA, "fuzziness": 1}).json()
    assert root["mode"] == "lemma"
    assert root["total"] == 2


def test_exact_crown_form():
    body = _client().get(
        "/api/search", params={"q": KLILA, "mode": "exact"}
    ).json()
    assert body["total"] == 1
    assert body["results"][0]["verse_id"] == "EXO.39.30"


def test_book_filter():
    body = _client().get(
        "/api/search",
        params={"q": ALAHA, "mode": "lemma", "book": "GEN"},
    ).json()
    assert body["total"] == 2
    body = _client().get(
        "/api/search",
        params={"q": ALAHA, "mode": "lemma", "book": "MAT"},
    ).json()
    assert body["total"] == 0


def test_lemma_key_filter():
    body = _client().get(
        "/api/search",
        params={"q": RISH, "mode": "lemma", "strongs": "L3017"},
    ).json()
    ids = [row["verse_id"] for row in body["results"]]
    assert "GEN.2.10" in ids
    assert "GEN.1.1" in ids
