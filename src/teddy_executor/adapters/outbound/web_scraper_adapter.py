from teddy_executor.core.ports.outbound.web_scraper import WebScraper
from teddy_executor.core.ports.outbound.config_service import IConfigService


MIN_GITHUB_CONTENT_LENGTH = 10


class WebScraperAdapter(WebScraper):
    """
    An adapter that implements the WebScraper port using requests and trafilatura.
    """

    def __init__(self, config_service: IConfigService = None):  # type: ignore
        self._config_service = config_service

    def _get_trafilatura(self):
        """Lazy-load trafilatura to keep CLI startup fast."""
        import trafilatura

        return trafilatura

    def _get_bs4(self):
        """Lazy-load BeautifulSoup to keep CLI startup fast."""
        from bs4 import BeautifulSoup

        return BeautifulSoup

    def _extract_github_conversation(self, html: str) -> str:
        """
        Extracts issue or pull request content and comments from GitHub HTML.
        Uses a hybrid strategy: JSON-embedded data (primary) and CSS selectors (fallback).
        """
        import json

        soup = self._get_bs4()(html, "html.parser")

        # 1. Primary: Try high-fidelity extraction from embedded JSON data
        scripts = soup.find_all("script", type="application/json")
        for script in scripts:
            if not script.string:
                continue
            try:
                data = json.loads(script.string)
                result = self._parse_github_json(data)
                if result:
                    return result
            except (json.JSONDecodeError, TypeError, AttributeError):
                continue

        # 2. Fallback: CSS-based scraping
        return self._scrape_github_html(soup)

    def _find_key_recursive(self, obj, target_key):
        """Recursively search for a key in a nested dictionary/list."""
        if isinstance(obj, dict):
            if target_key in obj:
                return obj[target_key]
            for v in obj.values():
                res = self._find_key_recursive(v, target_key)
                if res:
                    return res
        elif isinstance(obj, list):
            for item in obj:
                res = self._find_key_recursive(item, target_key)
                if res:
                    return res
        return None

    def _gather_edges_recursive(self, obj, edges_out: list):
        """Recursively gather all 'edges' lists into the output list."""
        if isinstance(obj, dict):
            if "edges" in obj and isinstance(obj["edges"], list):
                edges_out.extend(obj["edges"])
            for v in obj.values():
                self._gather_edges_recursive(v, edges_out)
        elif isinstance(obj, list):
            for i in obj:
                self._gather_edges_recursive(i, edges_out)

    def _parse_github_json(self, data: dict) -> str | None:
        """Helper to recursively find and parse issue/PR data from JSON."""
        container = self._find_key_recursive(data, "issue") or self._find_key_recursive(
            data, "pullRequest"
        )
        if not container or not isinstance(container, dict):
            return None

        title = (
            container.get("title")
            or container.get("titleHtml")
            or container.get("titleText")
            or "Unknown Title"
        )
        body = container.get("body") or container.get("bodyHTML", "")

        all_edges: list[dict] = []
        self._gather_edges_recursive(data, all_edges)

        comments = []
        seen_ids = set()
        for edge in all_edges:
            node = edge.get("node", {}) if isinstance(edge, dict) else {}
            node_id = node.get("id")
            if node_id and node_id not in seen_ids:
                if node.get("__typename") in [
                    "IssueComment",
                    "PullRequestReview",
                    "PullRequestReviewComment",
                ]:
                    seen_ids.add(node_id)
                    author = node.get("author", {}).get("login", "unknown")
                    c_body = node.get("body") or node.get("bodyHTML") or ""
                    comments.append(
                        f"### {node.get('__typename')} by {author}\n{c_body}\n\n"
                    )

        return f"# {title}\n\n## Description\n{body}\n\n" + "".join(comments)

    def _scrape_github_html(self, soup) -> str:
        """Helper for CSS-based fallback scraping."""
        title_elem = soup.select_one(".markdown-title") or soup.select_one(
            ".gh-header-title"
        )
        title = title_elem.get_text(strip=True) if title_elem else "GitHub Content"

        bodies = soup.select(".markdown-body")
        content_blocks = []
        for i, block in enumerate(bodies):
            text = block.get_text(separator="\n", strip=True)
            if len(text) > MIN_GITHUB_CONTENT_LENGTH:
                label = "Description" if i == 0 else f"Comment {i}"
                content_blocks.append(f"## {label}\n{text}\n\n")

        return f"# {title}\n\n" + "".join(content_blocks)

    def get_content(self, url: str, **_kwargs) -> str:
        """
        Fetches and extracts the content from the given URL.

        Args:
            url: The URL to fetch content from.
            **_kwargs: Optional extraction hints.

        Returns:
            The extracted text content.
        """
        import requests

        # Stealthy identity mimicking Chrome on macOS to avoid automated blocking
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        headers = {"User-Agent": user_agent}

        if url.startswith("https://github.com/") and "/blob/" in url:
            raw_url = url.replace("github.com", "raw.githubusercontent.com").replace(
                "/blob/", "/"
            )
            response = requests.get(raw_url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.text

        # 1. Manual Fetch: Always use our own identity rather than delegating
        # network state to third-party libraries.
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        html_content = response.text

        if not html_content:
            return ""

        # Routing: Use specialized extractor for GitHub Issues and Pull Requests
        is_github_domain = (
            "github.com" in url or "localhost" in url or "127.0.0.1" in url
        )
        if is_github_domain and ("/issues/" in url or "/pull/" in url):
            github_content = self._extract_github_conversation(html_content)
            if github_content:
                return github_content

        trafilatura = self._get_trafilatura()
        markdown_content = trafilatura.extract(
            html_content,
            output_format="markdown",
            include_links=True,
            include_formatting=True,
            favor_recall=True,
            include_comments=True,
            include_tables=True,
        )

        return markdown_content if markdown_content else ""
