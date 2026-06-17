import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


def parse_github_url(url: str) -> Tuple[str, str, str | None]:
    """
    Parses a GitHub URL to extract the owner, repository name, and subpath if any.
    Matches formats like:
      - https://github.com/owner/repo
      - https://github.com/owner/repo/tree/branch/path/to/subfolder
    """
    pattern = r"https?://github\.com/([^/]+)/([^/]+)(?:/tree/[^/]+/(.+))?"
    match = re.match(pattern, url.strip())
    if not match:
        raise ValueError(f"Invalid GitHub URL: {url}")

    owner = match.group(1)
    repo = match.group(2)
    path = match.group(3)

    # Strip any trailing slashes or .git extensions
    if repo.endswith(".git"):
        repo = repo[:-4]

    return owner, repo, path


def fetch_commits_page(
    owner: str,
    repo: str,
    path: str | None,
    since: str,
    author: str,
    token: str | None,
    page: int,
) -> List[Dict[str, Any]]:
    """
    Fetches a single page of commits for a repository path/author since a specific date.
    """
    base_url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    params = [f"since={since}", f"author={author}", "per_page=100", f"page={page}"]
    if path:
        # URL encode the path in case of spaces/special chars
        encoded_path = urllib.parse.quote(path)
        params.append(f"path={encoded_path}")

    url = f"{base_url}?{'&'.join(params)}"

    req = urllib.request.Request(url)
    req.add_header("User-Agent", "GitHub-Contributions-Generator")
    req.add_header("Accept", "application/vnd.github.v3+json")
    if token:
        req.add_header("Authorization", f"token {token}")

    try:
        with urllib.request.urlopen(req) as response:
            data = response.read().decode("utf-8")
            commits: List[Dict[str, Any]] = json.loads(data)
            return commits
    except urllib.error.HTTPError as err:
        print(
            f"Error fetching commits for {owner}/{repo} (path: {path}) page {page}: {err.code} {err.reason}"
        )
        if err.code == 404:
            print(f"Repository or path not found: {owner}/{repo} (path: {path})")
            return []
        raise err


def fetch_all_commits(
    owner: str, repo: str, path: str | None, since: str, author: str, token: str | None
) -> List[Dict[str, Any]]:
    """
    Fetches all commits since a date using pagination.
    """
    all_commits: List[Dict[str, Any]] = []
    page = 1
    while True:
        commits = fetch_commits_page(owner, repo, path, since, author, token, page)
        if not commits:
            break
        all_commits.extend(commits)
        if len(commits) < 100:
            break
        page += 1
    return all_commits


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parents[1]
    experiments_file = repo_root / "experiments.json"
    output_file = repo_root / "contributions.json"

    if not experiments_file.exists():
        raise FileNotFoundError(f"experiments.json not found at {experiments_file}")

    with open(experiments_file, "r", encoding="utf-8") as f:
        experiments: List[Dict[str, Any]] = json.load(f)

    token = os.environ.get("GITHUB_TOKEN")

    # Calculate since date (1 year ago, or let's say 365 days ago)
    since_date = datetime.now(timezone.utc) - timedelta(days=365)
    since_str = since_date.strftime("%Y-%m-%dT00:00:00Z")

    # Track contributions: dict of YYYY-MM-DD -> count
    contributions: Dict[str, int] = {}

    # Query commits for each experiment's repository
    seen_targets: Set[Tuple[str, str, str | None]] = set()

    for exp in experiments:
        github_url = exp.get("github")
        if not github_url:
            continue

        try:
            owner, repo, path = parse_github_url(github_url)
        except ValueError as e:
            print(f"Skipping invalid URL: {e}")
            continue

        # De-duplicate queries
        target = (owner, repo, path)
        if target in seen_targets:
            continue
        seen_targets.add(target)

        print(
            f"Fetching commits for {owner}/{repo}"
            + (f" (path: {path})" if path else "")
            + "..."
        )

        try:
            commits = fetch_all_commits(owner, repo, path, since_str, owner, token)
        except Exception as e:
            print(f"Failed to fetch commits for {owner}/{repo}: {e}")
            continue

        print(f"Found {len(commits)} commits.")

        for commit in commits:
            commit_info = commit.get("commit", {})
            committer = commit_info.get("committer", {})
            date_str = committer.get("date")  # Format: "2026-06-17T06:06:40Z"
            if date_str:
                date = date_str.split("T")[0]
                contributions[date] = contributions.get(date, 0) + 1

    output_data = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "contributions": contributions,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    print(f"Successfully generated contributions data at {output_file}")


if __name__ == "__main__":
    main()
