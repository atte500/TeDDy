import responses

from teddy.adapters.outbound.web_scraper_adapter import WebScraperAdapter


@responses.activate
def test_get_content_success():
    """
    Given a mocked successful HTTP response for a URL,
    When get_content is called,
    Then it should return the string content of the mocked response.
    """
    # Arrange
    adapter = WebScraperAdapter()
    url = "https://example.com/test_page"
    mock_response_body = (
        '{"Host": "example.com", "url": "https://example.com/test_page"}'
    )
    expected_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
    }
    responses.add(
        responses.GET,
        url,
        body=mock_response_body,
        status=200,
        match=[responses.matchers.header_matcher(expected_headers)],
    )

    # Act
    content = adapter.get_content(url)

    # Assert
    assert isinstance(content, str)
    assert '"Host": "example.com"' in content
    # Markdownify escapes underscores, so we need to account for that in the assertion
    assert '"url": "https://example.com/test\\_page"' in content
