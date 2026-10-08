"""The Seller assistant (AGENTS.md): its tools, chat actions, and the plumbing they use."""

from app.agents.common import with_attachments
from tests.conftest import fake_vector, sign_up
from tests.test_agents import add_listing, user_doc


def test_actions_keep_only_sell_form_links():
    def tool():
        return {"a": {"action": {"kind": "sell", "url": "/sell?item=1&price=12"}},
                "b": {"action": {"kind": "sell", "url": "https://example.com/phish"}},
                "c": {"action": {"kind": "pay", "url": "/sell?item=2"}},
                "d": [{"action": {"kind": "sell", "url": "/sell?item=1&price=12"}}]}   # duplicate
    attachments, actions = [], []
    with_attachments({"tool": tool}, attachments, actions)["tool"]()
    assert actions == [{"kind": "sell", "url": "/sell?item=1&price=12"}]


def test_listing_search_can_leave_out_one_seller(client):
    sign_up(client)
    me = user_doc(client)["_id"]
    mine = add_listing(client, source_id="sellers", seller_id=me, price_tnd=10.0)
    other = add_listing(client, price_tnd=40.0)
    index, db = client.app.state.listing_index, client.app.state.db
    ids = [h["id"] for h in index.search(db, fake_vector(1), k=5, category="top")]
    assert set(ids) == {mine, other}
    ids = [h["id"] for h in index.search(db, fake_vector(1), k=5, category="top", exclude_seller=me)]
    assert ids == [other]
