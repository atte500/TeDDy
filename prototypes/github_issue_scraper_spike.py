import sys
import requests
from bs4 import BeautifulSoup

def scrape_github_conversation(url: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
    }

    print(f"Fetching: {url}")
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()

    with open("github_debug.html", "w", encoding="utf-8") as f:
        f.write(response.text)

    import json
    soup = BeautifulSoup(response.text, 'html.parser')

    # 1. Try to find the embedded JSON payload
    script_tag = soup.find('script', attrs={'data-target': 'react-app.embeddedData'})
    if not script_tag:
        # Fallback for some PR views
        script_tag = soup.find('script', attrs={'id': 'client-env'})

    def find_key_recursive(obj, target_key):
        """Recursively search for a key in a nested dictionary/list."""
        if isinstance(obj, dict):
            if target_key in obj:
                return obj[target_key]
            for v in obj.values():
                res = find_key_recursive(v, target_key)
                if res: return res
        elif isinstance(obj, list):
            for item in obj:
                res = find_key_recursive(item, target_key)
                if res: return res
        return None

    # Find all script tags that might contain the data
    scripts = soup.find_all('script', type='application/json')
    for script in scripts:
        if not script.string: continue
        try:
            data = json.loads(script.string)
        except: continue

        # Try finding issue or pullRequest data
        issue_data = find_key_recursive(data, 'issue') or find_key_recursive(data, 'pullRequest')

        if issue_data and isinstance(issue_data, dict):
            print(f"Analyzing data container in script: {script.get('data-target', script.get('id', 'unknown'))}")

            title = issue_data.get('title') or issue_data.get('titleHtml')
            body = issue_data.get('body') or issue_data.get('bodyHTML')

            # Gather comments from JSON
            all_edges = []
            def gather_edges(obj):
                if isinstance(obj, dict):
                    if 'edges' in obj and isinstance(obj['edges'], list): all_edges.extend(obj['edges'])
                    for v in obj.values(): gather_edges(v)
                elif isinstance(obj, list):
                    for i in obj: gather_edges(i)
            gather_edges(data)

            json_comments = []
            seen_ids = set()
            for edge in all_edges:
                node = edge.get('node', {}) if isinstance(edge, dict) else {}
                if node.get('id') and node.get('id') not in seen_ids:
                    if node.get('__typename') in ['IssueComment', 'PullRequestReview', 'PullRequestReviewComment']:
                        seen_ids.add(node['id'])
                        author = node.get('author', {}).get('login', 'unknown')
                        c_body = node.get('body') or node.get('bodyHTML') or ""
                        json_comments.append(f"### {node.get('__typename')} by {author}\n{c_body}\n\n")

            if title and (body or json_comments):
                print(f"SUCCESS: Extracted Title + {len(json_comments)} comments via JSON.")
                return f"# {title}\n\n## Description\n{body}\n\n" + "".join(json_comments)

    print("Partial or Failed JSON extraction. Merging with HTML scraping...")
    title_elem = soup.select_one('.markdown-title') or soup.select_one('.gh-header-title')
    title = title_elem.get_text(strip=True) if title_elem else "Unknown Title"

    # Extract body and comments via CSS
    bodies = soup.select('.markdown-body')
    content_blocks = []
    for i, block in enumerate(bodies):
        # Skip very short blocks or nav items
        text = block.get_text(separator='\n', strip=True)
        if len(text) > 10:
            label = "Description" if i == 0 else f"Comment {i}"
            content_blocks.append(f"## {label}\n{text}\n\n")

    return f"# {title}\n\n" + "".join(content_blocks)

    print("Falling back to CSS selectors...")
    # Original fallback logic
    title_elem = soup.select_one('.markdown-title') or soup.select_one('.gh-header-title')
    title = title_elem.get_text(strip=True) if title_elem else "No Title Found"
    comments = soup.select('.markdown-body')

    output = [f"# {title}\n"]
    for i, comment in enumerate(comments):
        text = comment.get_text(separator='\n', strip=True)
        output.append(f"## Content Block {i+1}\n{text}\n---\n")

    return "".join(output)

if __name__ == "__main__":
    test_url = "https://github.com/octocat/Spoon-Knife/issues/1"
    if len(sys.argv) > 1:
        test_url = sys.argv[1]

    try:
        result = scrape_github_conversation(test_url)
        print(result[:1000] + "...") # Print first 1000 chars
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
