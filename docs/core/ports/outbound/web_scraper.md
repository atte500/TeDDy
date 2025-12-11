# Outbound Port: Web Scraper

**Motivating Slice:** [Slice 04: Implement `read` Action](../../slices/04-read-action.md)

## 1. Purpose

This port defines the contract for fetching the content of a remote URL. It abstracts the underlying HTTP client and content parsing logic, allowing the core application to request web content without knowledge of the implementation details.

## 2. Interface Definition

An adapter implementing this port **must** provide the following method:

### `get_content(url: str) -> str`

*   **Description:**
    Retrieves the primary textual content from the given URL. If the content is HTML, it should be converted to a clean, readable Markdown format.

*   **Preconditions:**
    *   `url` must be a well-formed, absolute URL string (e.g., "https://example.com").

*   **Postconditions:**
    *   On success, returns a string containing the textual content of the page.
    *   On failure (e.g., network error, HTTP status code >= 400), it **must** raise an exception (e.g., `WebContentError`) that the application service can catch and handle.

*   **Error Handling:**
    The implementing adapter is responsible for handling various failure modes, such as connection timeouts, DNS resolution errors, and non-2xx HTTP status codes. All such failures should be translated into a consistent, catchable exception for the service layer.
