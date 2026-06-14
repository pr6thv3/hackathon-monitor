"""
GitHub Intelligence Module.

Searches GitHub for repositories, good first issues, bounties, and organization details
related to the hackathon and its sponsors. Uses GitHub Search API.
Handles rate limiting and optional authentication via `GITHUB_TOKEN` (recommended).
Defensively falls back to unauthenticated requests if the token is invalid (401).
"""

import logging
import os
import requests as http_requests

log = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"


def _make_request(url: str, headers: dict, params: dict = None, timeout: int = 15) -> http_requests.Response | None:
    """
    Make an HTTP GET request to GitHub API.
    If it returns 401 (Bad Credentials), falls back to an unauthenticated request.
    """
    try:
        resp = http_requests.get(url, headers=headers, params=params, timeout=timeout)
        
        # If credentials are bad, try again unauthenticated
        if resp.status_code == 401 and "Authorization" in headers:
            log.warning("GitHub API returned 401 (Bad Credentials). Retrying unauthenticated...")
            no_auth_headers = {k: v for k, v in headers.items() if k.lower() != "authorization"}
            resp = http_requests.get(url, headers=no_auth_headers, params=params, timeout=timeout)
            
        return resp
    except Exception as e:
        log.warning(f"HTTP request to {url} failed: {e}")
        return None


def get_github_intel(hackathon_name: str, sponsors: list[str] = None) -> dict:
    """
    Search GitHub REST API for:
    1. Matching repositories (related to hackathon name)
    2. Issues labeled 'good first issue' mentioning the hackathon or sponsors
    3. Issues labeled or containing 'bounty' / 'prize' for the hackathon

    Args:
        hackathon_name: The name of the hackathon to search for.
        sponsors: List of sponsors to help refine searches.

    Returns:
        A dictionary containing repos list, open issues, bounty counts, etc.
    """
    log.info(f"Retrieving GitHub intelligence for: {hackathon_name}")
    
    # Initialize default results
    intel = {
        "repos": [],
        "issues": [],
        "bounty_count": 0,
        "good_first_issues": 0,
        "total_stars": 0,
        "sponsors_intel": {}
    }

    token = os.environ.get("GITHUB_TOKEN", "").strip()
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Hackathon-Intelligence-Agent-v3"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
        log.debug("Using GitHub PAT authentication")
    else:
        log.debug("Using unauthenticated GitHub API (limit 10 req/min)")

    # Clean hackathon name for query (remove special chars/symbols)
    clean_name = "".join(c if c.isalnum() or c.isspace() else " " for c in hackathon_name).strip()
    # Replace multiple spaces with a single space
    clean_name = " ".join(clean_name.split())
    if not clean_name:
        return intel

    # 1. Search Repositories
    repo_query = f'"{clean_name}" in:name,description'
    url = f"{GITHUB_API_BASE}/search/repositories"
    params = {"q": repo_query, "sort": "updated", "order": "desc", "per_page": 5}
    
    resp = _make_request(url, headers, params)
    if resp and resp.status_code == 200:
        repo_data = resp.json()
        items = repo_data.get("items", [])
        for item in items:
            repo_info = {
                "name": item.get("full_name"),
                "url": item.get("html_url"),
                "stars": item.get("stargazers_count", 0),
                "description": item.get("description") or "",
                "language": item.get("language") or ""
            }
            intel["repos"].append(repo_info)
            intel["total_stars"] += item.get("stargazers_count", 0)
        
        # Log rate limit info if available
        limit_remaining = resp.headers.get("X-RateLimit-Remaining")
        log.debug(f"GitHub API remaining limit: {limit_remaining}")
    elif resp:
        log.warning(f"GitHub repo search returned status {resp.status_code}: {resp.text}")

    # 2. Search Good First Issues
    issue_query = f'"{clean_name}" label:"good first issue" state:open'
    url = f"{GITHUB_API_BASE}/search/issues"
    params = {"q": issue_query, "per_page": 5}
    
    resp = _make_request(url, headers, params)
    if resp and resp.status_code == 200:
        issue_data = resp.json()
        intel["good_first_issues"] = issue_data.get("total_count", 0)
        items = issue_data.get("items", [])
        for item in items:
            intel["issues"].append({
                "title": item.get("title"),
                "url": item.get("html_url"),
                "type": "good first issue"
            })

    # 3. Search Bounties
    bounty_query = f'"{clean_name}" state:open (bounty OR prize OR reward)'
    url = f"{GITHUB_API_BASE}/search/issues"
    params = {"q": bounty_query, "per_page": 5}
    
    resp = _make_request(url, headers, params)
    if resp and resp.status_code == 200:
        bounty_data = resp.json()
        intel["bounty_count"] = bounty_data.get("total_count", 0)
        items = bounty_data.get("items", [])
        for item in items:
            intel["issues"].append({
                "title": item.get("title"),
                "url": item.get("html_url"),
                "type": "bounty"
            })

    # 4. Sponsor organization information
    if sponsors:
        for sponsor in sponsors[:3]:
            clean_sponsor = "".join(c for c in sponsor if c.isalnum()).strip()
            if not clean_sponsor:
                continue
            
            url = f"{GITHUB_API_BASE}/orgs/{clean_sponsor}"
            resp = _make_request(url, headers, timeout=10)
            if resp and resp.status_code == 200:
                org_data = resp.json()
                intel["sponsors_intel"][sponsor] = {
                    "org_name": org_data.get("name"),
                    "public_repos": org_data.get("public_repos", 0),
                    "followers": org_data.get("followers", 0),
                    "github_url": org_data.get("html_url")
                }

    return intel
