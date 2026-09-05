from app.audit.models import init_db
from app.graph.nodes.shopping_agent import shopping_agent_node


def _product(id_, price_paise, name=None, material=None):
    return {
        "id": id_,
        "name": name or id_,
        "price_paise": price_paise,
        "attributes": {"material": material} if material else {},
    }


def _base_state(session_id: str, catalog: list[dict]):
    return {
        "session_id": session_id,
        "user_goal": "test goal",
        "catalog_snapshot": catalog,
    }


def setup_module(_module):
    init_db()


def test_proposes_three_tiers_from_five_matches():
    catalog = [
        _product("a", 999),
        _product("b", 1299),
        _product("c", 1499),
        _product("d", 1899),
        _product("e", 4999),
    ]
    result = shopping_agent_node(_base_state("shop-1", catalog))

    assert result["status"] == "awaiting_option_selection"
    options = result["proposed_options"]
    assert len(options) == 3
    tiers = [o["tier"] for o in options]
    assert tiers == ["most_affordable", "best_value", "premium_pick"]
    # cheapest and most expensive of the matched set, not arbitrary picks
    assert options[0]["unit_price_paise"] == 999
    assert options[-1]["unit_price_paise"] == 4999
    # every option is a distinct product
    assert len({o["product_id"] for o in options}) == 3


def test_three_way_tie_still_matches_demo_scenario():
    """Regression for the exact demo catalog subset: "laptop bag under
    ₹1500" matches exactly 3 bags — all 3 should surface as distinct tiers.
    """
    catalog = [
        _product("bag-compact-grey", 99900, "Compact Commuter Bag"),
        _product("bag-classic-black", 129900, "Classic Black Laptop Bag"),
        _product("bag-canvas-brown", 149900, "Canvas Messenger Bag"),
    ]
    result = shopping_agent_node(_base_state("shop-2", catalog))

    options = result["proposed_options"]
    assert [o["product_id"] for o in options] == [
        "bag-compact-grey",
        "bag-classic-black",
        "bag-canvas-brown",
    ]


def test_single_match_labeled_most_affordable_not_arbitrary_tier():
    catalog = [_product("only-one", 50000)]
    result = shopping_agent_node(_base_state("shop-3", catalog))

    options = result["proposed_options"]
    assert len(options) == 1
    assert options[0]["tier"] == "most_affordable"


def test_two_matches_skip_middle_tier():
    catalog = [_product("cheap", 10000), _product("pricey", 90000)]
    result = shopping_agent_node(_base_state("shop-4", catalog))

    options = result["proposed_options"]
    assert [o["tier"] for o in options] == ["most_affordable", "premium_pick"]


def test_no_match_proposes_nothing_and_reports_status():
    result = shopping_agent_node(_base_state("shop-5", []))

    assert result["status"] == "no_match"
    assert result["proposed_options"] == []


def test_does_not_mutate_cart_or_call_policy_agent():
    """The browse graph must not add anything to the cart on its own —
    that only happens once the user picks an option via /select-option,
    which is what keeps every cart mutation behind the Policy Agent gate.
    """
    catalog = [_product("a", 999), _product("b", 1299), _product("c", 1499)]
    state = _base_state("shop-6", catalog)
    result = shopping_agent_node(state)

    assert "cart" not in result
    assert "policy_decisions" not in result
