from teddy_executor.core.ports.inbound.plan_parser import InvalidPlanError


def test_invalid_plan_error_supports_offending_node():
    """
    Ensure InvalidPlanError can store a reference to the offending AST node.
    """
    mock_node = {"type": "Paragraph", "content": "bad node"}
    message = "Something went wrong"

    error = InvalidPlanError(message, offending_node=mock_node)

    assert str(error) == message
    assert error.offending_node == mock_node


def test_invalid_plan_error_offending_node_defaults_to_none():
    """
    Ensure offending_node is None by default.
    """
    error = InvalidPlanError("Simple error")
    assert error.offending_node is None
