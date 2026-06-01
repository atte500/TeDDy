from teddy_executor.core.ports.outbound.web_scraper import WebScraper
from teddy_executor.core.ports.outbound.config_service import IConfigService


MIN_GITHUB_CONTENT_LENGTH = 10
HTTP_FORBIDDEN = 403


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

    def _fetch_with_rotation(self, url: str) -> str | None:
        """Attempts to fetch HTML content using a rotating pool of User-Agents."""
        import requests

        user_agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
        ]

        last_error: Exception | None = None

        for ua in user_agents:
            headers = {
                "User-Agent": ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
            }
            try:
                response = requests.get(url, headers=headers, timeout=20)
                response.raise_for_status()
                return response.text
            except requests.exceptions.HTTPError as e:
                last_error = e
                # Retry on 403 (Forbidden) and 406 (Not Acceptable)
                status_code = getattr(e.response, "status_code", None)
                if status_code in [HTTP_FORBIDDEN, 406]:
                    continue
                raise
            except Exception as e:
                last_error = e
                continue

        # Final Resort: Trafilatura's internal fetcher
        html_content = self._get_trafilatura().fetch_url(url)
        if not html_content and last_error:
            raise last_error

        return html_content

    def _handle_github_raw(self, url: str) -> str | None:
        """Handles specialized fetching for GitHub raw content."""
        import requests

        is_raw_github = url.startswith("https://raw.githubusercontent.com/")
        is_github_blob = url.startswith("https://github.com/") and "/blob/" in url

        if not (is_raw_github or is_github_blob):
            return None

        target_url = (
            url.replace("github.com", "raw.githubusercontent.com").replace(
                "/blob/", "/"
            )
            if is_github_blob
            else url
        )
        response = requests.get(
            target_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, Gecko) Chrome/124.0.0.0 Safari/537.36"
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.text

    def get_content(self, url: str, **_kwargs) -> str:
        """
        Fetches and extracts the content from the given URL.
        Employs a multi-stage stealth rotation to bypass automated blocking.

        Args:
            url: The URL to fetch content from.
            **_kwargs: Optional extraction hints.

        Returns:
            The extracted text content.
        """
        # 1. Specialized handling for GitHub raw content
        raw_github_content = self._handle_github_raw(url)
        if raw_github_content is not None:
            return raw_github_content

        # 2. Multi-stage Stealth Rotation for general URLs
        html_content = self._fetch_with_rotation(url)
        if not html_content:
            return ""

        # 3. Routing: Use specialized extractor for GitHub Issues and Pull Requests
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
