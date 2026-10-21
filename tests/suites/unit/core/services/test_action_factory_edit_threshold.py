def test_action_factory_injects_configured_edit_threshold(
    factory, mock_fs, mock_config
):
    """The EDIT action resolves its threshold from edit.similarity_threshold.

    The side effect returns a sentinel only for the canonical key, so the
    assertion proves the factory reads the canonical group rather than a
    legacy key or a call-site fallback.
    """
    mock_config.get_setting.side_effect = lambda key, default=None: (
        0.42 if key == "edit.similarity_threshold" else default
    )

    action = factory.create_action(
        "EDIT",
        params={"path": "test.py", "edits": [{"find": "a", "replace": "b"}]},
    )

    action.execute(path="test.py", edits=[{"find": "a", "replace": "b"}])

    assert mock_fs.edit_file.call_args.kwargs.get("similarity_threshold") == 0.42
