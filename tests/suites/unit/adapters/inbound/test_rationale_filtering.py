from unittest.mock import MagicMock
from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import on_mount_logic


def test_on_mount_logic_filters_and_merges_rationale_sections():
    # Setup
    app = MagicMock()
    app.plan.title = "Test Plan"
    app.plan.metadata = {"Status": "Green 🟢"}
    app.plan.actions = []
    app.project_context = None

    # Rationale with:
    # 1. Leading junk (should be ignored)
    # 2. Standard "Synthesis"
    # 3. Non-standard "Extra Details" (should merge into Synthesis)
    # 4. Standard "Justification"
    app.plan.rationale = """
0. Lead-in text that should be ignored because no preceding node.
1. Synthesis
Core logic here.
3. Extra Details
This is non-standard and should be appended to Synthesis.
2. Justification
Valid reason.
"""

    # Mock Tree behavior
    tree = MagicMock()
    app.query_one.return_value = tree

    # Track nodes added to rationale root
    rat_root = MagicMock()
    nodes = []

    def add_leaf_mock(label, data):
        node = MagicMock()
        node.label = label
        node.data = data
        nodes.append(node)
        return node

    rat_root.add_leaf.side_effect = add_leaf_mock
    tree.root.add.side_effect = lambda label, data, expand: (
        rat_root if data == "RATIONALE_ROOT" else MagicMock()
    )

    # Driver
    on_mount_logic(app)

    # Observer
    # We expect 2 nodes: "Synthesis" and "Justification"
    # "Extra Details" should be merged into "Synthesis"
    titles = [n.data["title"] for n in nodes]
    assert "Synthesis" in titles
    assert "Justification" in titles
    assert "Extra Details" not in titles

    synthesis_node = next(n for n in nodes if n.data["title"] == "Synthesis")
    assert "Core logic here." in synthesis_node.data["content"]
    assert "3. Extra Details" in synthesis_node.data["content"]
    assert "This is non-standard" in synthesis_node.data["content"]

    justification_node = next(n for n in nodes if n.data["title"] == "Justification")
    assert justification_node.data["content"] == "Valid reason."
