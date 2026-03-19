from http import HTTPStatus
from unittest.mock import patch
import responses
from tests.harness.setup.test_environment import TestEnvironment
from teddy_executor.core.ports.outbound import IWebScraper


@responses.activate
def test_get_content_for_github_url_fetches_raw_content(monkeypatch):
    """
    Given a GitHub file URL,
    When get_content is called,
    Then it should transform the URL to the raw content URL and fetch the raw text.
    """
    # Arrange
    env = TestEnvironment(monkeypatch).setup().with_real_web_scraper()
    scraper = env.get_service(IWebScraper)

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
    content = scraper.get_content(github_url)

    # Assert
    assert content == mock_response_body
    assert len(responses.calls) == 1
    assert responses.calls[0].request.url == raw_url


@responses.activate
@patch("trafilatura.fetch_url")
@patch("trafilatura.extract")
def test_get_content_falls_back_on_403_error(mock_extract, mock_fetch_url, monkeypatch):
    """
    Given a URL that returns a 403 Forbidden error,
    When get_content is called,
    Then it should fall back to using trafilatura.fetch_url.
    """
    # Arrange
    env = TestEnvironment(monkeypatch).setup().with_real_web_scraper()
    scraper = env.get_service(IWebScraper)

    protected_url = "https://protected.example.com/article"
    mock_html_content = "<html><body><p>Fallback Content</p></body></html>"
    mock_markdown_content = "Fallback Content"

    # Mock the initial failed request
    responses.add(
        responses.GET,
        protected_url,
        status=403,
    )

    # Mock the successful fallback
    mock_fetch_url.return_value = mock_html_content
    mock_extract.return_value = mock_markdown_content

    # Act
    content = scraper.get_content(protected_url)

    # Assert
    assert len(responses.calls) == 1
    assert responses.calls[0].request.url == protected_url
    assert responses.calls[0].response.status_code == HTTPStatus.FORBIDDEN

    mock_fetch_url.assert_called_once_with(protected_url)
    assert mock_extract.call_args[0][0] == mock_html_content
    assert content == mock_markdown_content


@responses.activate
def test_get_content_for_article_strips_boilerplate(monkeypatch):
    """
    Given a URL to an article with boilerplate,
    When get_content is called,
    Then it should use trafilatura to extract the main content.
    """
    # Arrange
    env = TestEnvironment(monkeypatch).setup().with_real_web_scraper()
    scraper = env.get_service(IWebScraper)

    article_url = "https://example.com/article"
    html_with_boilerplate = """
    <!DOCTYPE html>
    <html>
    <body>
        <div id="content">
            <div class="article">
                <h2>Main Article Title</h2>
                <p>This is the main content.</p>
            </div>
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
    content = scraper.get_content(article_url)

    # Assert
    assert "Main Article Title" in content
    assert "This is the main content." in content
