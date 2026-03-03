import teddy_executor.__main__


def test_container_fixture_patches_main(container):
    """
    Verifies that the container fixture is available and
    that it correctly patches teddy_executor.__main__.container.
    """
    assert container is not None
    assert teddy_executor.__main__.container is container
