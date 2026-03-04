import httpx

from app.exceptions import GitHubFetchError

API_BASE = "https://api.github.com"
RAW_BASE = "https://raw.githubusercontent.com"


async def fetch_repo_tree(
    client: httpx.AsyncClient, owner: str, repo: str,
) -> tuple[str, list[dict]]:
    """Fetch the recursive file tree. Returns (default_branch, tree_entries)."""
    # Get default branch
    r = await client.get(f"{API_BASE}/repos/{owner}/{repo}")
    if r.status_code == 404:
        raise GitHubFetchError("Repository not found or is private", 404)
    if r.status_code == 403:
        raise GitHubFetchError("GitHub API rate limit exceeded", 429)
    if r.status_code != 200:
        raise GitHubFetchError(f"GitHub API error: {r.status_code}")

    default_branch = r.json()["default_branch"]

    # Get recursive tree
    r = await client.get(
        f"{API_BASE}/repos/{owner}/{repo}/git/trees/{default_branch}",
        params={"recursive": "1"},
    )
    if r.status_code != 200:
        raise GitHubFetchError(f"Failed to fetch repository tree: {r.status_code}")

    tree = r.json().get("tree", [])
    blobs = [e for e in tree if e["type"] == "blob"]
    return default_branch, blobs


async def fetch_file_content(
    client: httpx.AsyncClient, owner: str, repo: str, branch: str, path: str,
) -> str | None:
    """Fetch raw file content. Returns None on failure."""
    url = f"{RAW_BASE}/{owner}/{repo}/{branch}/{path}"
    try:
        r = await client.get(url)
        if r.status_code != 200:
            return None
        return r.text
    except httpx.HTTPError:
        return None
