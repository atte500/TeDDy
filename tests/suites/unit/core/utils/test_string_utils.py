from teddy_executor.core.utils.string import slugify


def test_slugify_basic():
    """It should lowercase and replace spaces with hyphens. Hello is removed due to being conversational filler."""
    assert slugify("Hello World") == "world"


def test_slugify_special_characters():
    """It should remove non-alphanumeric characters and collapse hyphens."""
    assert slugify("Refactor: Auth Service (v2)!!!") == "refactor-auth-service-v2"


def test_slugify_truncation():
    """It should truncate to a default of 40 characters at word boundaries."""
    long_title = "This is a very long title that should definitely be truncated because it exceeds forty characters"
    # Filtered (Exhaustive): ["long", "title", "definitely", "truncated", "because", "exceeds", "forty", "characters"]
    # "long-title-definitely-truncated-exceeds" is 39 chars
    # adding "-forty" (5 chars) would make it 45 chars (>40)
    # So it should stop at "exceeds"
    expected = "long-title-definitely-truncated-exceeds"
    assert slugify(long_title) == expected
    assert len(slugify(long_title)) <= 40


def test_slugify_avoids_trailing_hyphen_after_truncation():
    """It should not end with a hyphen and should respect word boundaries."""
    input_str = "aaaaa bbbbb ccccc ddddd eeeee fffff ggggg hhhhh"
    # 40 chars: "aaaaa-bbbbb-ccccc-ddddd-eeeee-fffff-ggggg" (41 chars) -> too long
    # Should be: "aaaaa-bbbbb-ccccc-ddddd-eeeee-fffff" (35 chars)
    result = slugify(input_str)
    assert result == "aaaaa-bbbbb-ccccc-ddddd-eeeee-fffff"
    assert not result.endswith("-")


def test_slugify_removes_stopwords():
    """It should remove exhaustive filler words like 'using', 'from', 'should'."""
    input_str = (
        "I want to refactor the auth service using a better approach from the docs"
    )
    # Filtered: ["refactor", "auth", "service", "better", "approach", "docs"]
    # "refactor-auth-service-better-approach" is 37 chars.
    # adding "-docs" (5 chars) would make it 42 chars (>40).
    # So it should stop at "approach".
    assert slugify(input_str) == "refactor-auth-service-better-approach"
