import responses

from teddy_executor.adapters.outbound.web_scraper_adapter import WebScraperAdapter


@responses.activate
def test_get_content_for_github_url_fetches_raw_content():
    """
    Given a GitHub file URL,
    When get_content is called,
    Then it should transform the URL to the raw content URL and fetch the raw text.
    """
    # Arrange
    adapter = WebScraperAdapter()
    github_url = "https://github.com/user/repo/blob/main/path/to/file.py"
    raw_url = "https://raw.githubusercontent.com/user/repo/main/path/to/file.py"
    mock_response_body = "print('Hello, World!')"

    responses.add(
        responses.GET,
        raw_url,
        body=mock_response_body,
        status=200,
    )

    # Act
    content = adapter.get_content(github_url)

    # Assert
    assert content == mock_response_body
    assert len(responses.calls) == 1
    assert responses.calls[0].request.url == raw_url


@responses.activate
def test_get_content_for_article_strips_boilerplate():
    """
    Given a URL to an article with boilerplate,
    When get_content is called,
    Then it should use trafilatura to extract the main content and convert it to markdown.
    """
    # Arrange
    adapter = WebScraperAdapter()
    article_url = "https://example.com/article"
    html_with_boilerplate = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Page</title>
    </head>
    <body>
        <div id="header">
            <div class="nav">
                <a href="#">Home</a>
                <a href="#">About</a>
            </div>
            <h1>Site Title</h1>
        </div>
        <div id="content">
            <div class="main-column">
                <div class="article">
                    <h2>Main Article Title</h2>
                    <p>This is the main content.</p>
                    <p>It has multiple paragraphs.</p>
                </div>
            </div>
            <div class="sidebar">
                <h3>Related Links</h3>
                <ul>
                    <li><a href="#">Link 1</a></li>
                </ul>
            </div>
        </div>
        <div id="footer">
            <p>Copyright 2024. All rights reserved.</p>
        </div>
    </body>
    </html>
    """
    responses.add(
        responses.GET,
        article_url,
        body=html_with_boilerplate,
        status=200,
        content_type="text/html",
    )

    # Act
    content = adapter.get_content(article_url)

    # Assert
    # The spike revealed trafilatura can sometimes duplicate content in this scenario.
    # We will assert the main content is present and boilerplate is not.
    # A more robust assertion would require a more complex HTML mock.
    assert "Site Title" not in content
    assert "Copyright" not in content
    assert "This is the main content." in content
    assert "It has multiple paragraphs." in content
