from teddy_executor.core.ports.inbound.plan_parser import InvalidPlanError


def test_invalid_plan_error_supports_multiple_offending_nodes():
    """
    Ensure InvalidPlanError can store a list of offending AST nodes.
    """
    mock_nodes = [{"type": "Paragraph"}, {"type": "Heading"}]
    message = "Something went wrong"

    error = InvalidPlanError(message, offending_nodes=mock_nodes)

    assert str(error) == message
    assert error.offending_nodes == mock_nodes


def test_invalid_plan_error_defaults_to_empty_list():
    """
    Ensure offending_nodes is an empty list by default.
    """
    error = InvalidPlanError("Simple error")
    assert error.offending_nodes == []


def test_invalid_plan_error_backward_compatibility():
    """
    Ensure InvalidPlanError still supports a single offending_node (deprecated).
    """
    mock_node = {"type": "Paragraph"}
    error = InvalidPlanError("test", offending_node=mock_node)
    assert error.offending_nodes == [mock_node]
