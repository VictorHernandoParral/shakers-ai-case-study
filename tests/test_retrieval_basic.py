import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))


from app.services.retrieval import similarity_search

def test_similarity_search_returns_candidates():
    hits = similarity_search("payments and invoices", k=8)
    assert isinstance(hits, list)
    assert len(hits) >= 1

    first = hits[0]
    # shape/keys
    assert isinstance(first, dict)
    assert "title" in first and first["title"]
    assert "url" in first
    assert "content" in first

    # url safety
    url = first.get("url", "")
    assert url.startswith("kb://") or url.startswith("http")
