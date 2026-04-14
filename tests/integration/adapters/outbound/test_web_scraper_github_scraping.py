import pytest
from teddy_executor.adapters.outbound.web_scraper_adapter import WebScraperAdapter


@pytest.fixture
def scraper():
    return WebScraperAdapter()


def test_github_issue_scraping_extracts_description_and_comments(httpserver, scraper):
    """
    Integration test ensuring that when a GitHub Issue URL is provided,
    the scraper extracts the title, description, and comments.
    """
    # GIVEN: A mocked GitHub issue page with embedded JSON data
    # (Simplified version of what the prototype expects)
    mock_html = """
    <html>
    <head><title>Issue Title</title></head>
    <body>
        <h1 class="markdown-title">Real Issue Title</h1>
        <script type="application/json" data-target="react-app.embeddedData">
        {
          "payload": {
            "issue": {
              "title": "Real Issue Title",
              "body": "This is the main issue description.",
              "edges": [
                {
                  "node": {
                    "id": "comment-1",
                    "__typename": "IssueComment",
                    "author": { "login": "octocat" },
                    "body": "This is a comment from octocat."
                  }
                }
              ]
            }
          }
        }
        </script>
    </body>
    </html>
    """
    httpserver.expect_request("/octocat/Spoon-Knife/issues/1").respond_with_data(
        mock_html
    )
    url = httpserver.url_for("/octocat/Spoon-Knife/issues/1")

    # WHEN: The scraper is invoked
    content = scraper.get_content(url)

    # THEN: The output should contain the title, description, and comments
    assert "Real Issue Title" in content
    assert "This is the main issue description." in content
    assert "octocat" in content
    assert "comment from octocat" in content


def test_github_pr_scraping_fallback_to_html(httpserver, scraper):
    """
    Integration test ensuring that if JSON extraction fails,
    the scraper falls back to HTML-based extraction for GitHub.
    """
    # GIVEN: A mocked GitHub PR page WITHOUT embedded JSON but with standard CSS classes
    mock_html = """
    <html>
    <body>
        <div class="gh-header-title">PR Title</div>
        <div class="markdown-body">PR Description block</div>
        <div class="markdown-body">Comment 1 block</div>
    </body>
    </html>
    """
    httpserver.expect_request("/octocat/Spoon-Knife/pull/1").respond_with_data(
        mock_html
    )
    url = httpserver.url_for("/octocat/Spoon-Knife/pull/1")

    # WHEN: The scraper is invoked
    content = scraper.get_content(url)

    # THEN: The output should contain extracted blocks
    assert "PR Title" in content
    assert "PR Description block" in content
    assert "Comment 1 block" in content
