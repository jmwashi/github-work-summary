#!/usr/bin/env python3
"""
github-work-summary
Fetches all PRs you authored in a GitHub org and generates a resume-quality
Markdown summary using Claude to synthesize accomplishments by theme.
"""

import os
import sys
from datetime import datetime
from pathlib import Path

import anthropic
import requests
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_ORG = os.getenv("GITHUB_ORG", "")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "")
SINCE_DATE = os.getenv("SINCE_DATE", "")   # optional: YYYY-MM-DD
UNTIL_DATE = os.getenv("UNTIL_DATE", "")   # optional: YYYY-MM-DD
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

GRAPHQL_URL = "https://api.github.com/graphql"

STATE_ICON = {"MERGED": "✅", "OPEN": "🟢", "CLOSED": "❌"}

PR_QUERY = """
query($searchQuery: String!, $cursor: String) {
  search(query: $searchQuery, type: ISSUE, first: 100, after: $cursor) {
    pageInfo {
      hasNextPage
      endCursor
    }
    nodes {
      ... on PullRequest {
        title
        url
        number
        state
        body
        createdAt
        mergedAt
        repository {
          name
          nameWithOwner
        }
        labels(first: 10) {
          nodes { name }
        }
      }
    }
  }
}
"""


def run_query(query: str, variables: dict) -> dict:
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Content-Type": "application/json",
    }
    response = requests.post(
        GRAPHQL_URL,
        json={"query": query, "variables": variables},
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    if "errors" in data:
        raise RuntimeError(f"GitHub API error: {data['errors']}")
    return data["data"]


def build_search_query() -> str:
    q = f"org:{GITHUB_ORG} author:{GITHUB_USERNAME} type:pr"
    if SINCE_DATE:
        q += f" created:>={SINCE_DATE}"
    if UNTIL_DATE:
        q += f" created:<={UNTIL_DATE}"
    return q


def fetch_all_prs() -> list[dict]:
    search_query = build_search_query()
    prs: list[dict] = []
    cursor = None
    page = 1

    while True:
        print(f"  Fetching page {page}...", end="\r", flush=True)
        data = run_query(PR_QUERY, {"searchQuery": search_query, "cursor": cursor})
        result = data["search"]

        for node in result["nodes"]:
            if node:
                prs.append(node)

        if not result["pageInfo"]["hasNextPage"]:
            break

        cursor = result["pageInfo"]["endCursor"]
        page += 1

    print()
    return prs


def fmt_date(iso: str | None) -> str:
    if not iso:
        return "N/A"
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return dt.strftime("%b %d, %Y")


def generate_resume_bullets(prs: list[dict]) -> str:
    """Call Claude to synthesize PR data into themed resume bullet points."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    pr_lines = []
    for pr in prs:
        repo = pr["repository"]["nameWithOwner"]
        title = pr["title"]
        # Truncate long bodies to keep the prompt manageable
        body = (pr.get("body") or "").strip()
        body = body[:400] if len(body) > 400 else body
        state = pr["state"]
        labels = [lb["name"] for lb in pr.get("labels", {}).get("nodes", [])]

        line = f"- [{state}] {repo}: {title}"
        if labels:
            line += f" (labels: {', '.join(labels)})"
        if body:
            line += f"\n  Description: {body}"
        pr_lines.append(line)

    pr_text = "\n".join(pr_lines)

    prompt = f"""You are helping a software developer craft resume bullet points from their GitHub pull request history.

Analyze these {len(prs)} pull requests and produce resume-quality accomplishment bullet points.

Rules:
- Identify 3–6 thematic headings that reflect the actual work (e.g. "Backend Development", "Infrastructure & DevOps", "Frontend", "Testing & Quality", "Developer Experience", "Data & Analytics") — only include themes that are genuinely represented
- Write 2–5 bullets per theme
- Every bullet starts with a strong past-tense action verb (Implemented, Designed, Migrated, Optimized, Refactored, Automated, Reduced, Improved, Built, Introduced, etc.)
- Focus on impact and scope, not just what was changed
- Quantify wherever the data supports it (number of services, repos, endpoints, percentage improvement, etc.)
- Write at a senior engineer level — suitable for copying directly onto a resume or LinkedIn
- Do NOT simply restate PR titles; synthesize and elevate the language

Pull requests:
{pr_text}

Output only the Markdown (### headings and bullet points). No intro sentence, no outro.
"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text


def generate_markdown(prs: list[dict], resume_bullets: str) -> str:
    now = datetime.now().strftime("%Y-%m-%d")

    merged = [p for p in prs if p["state"] == "MERGED"]
    open_prs = [p for p in prs if p["state"] == "OPEN"]
    closed = [p for p in prs if p["state"] == "CLOSED"]

    all_dates = sorted(p["createdAt"] for p in prs if p.get("createdAt"))
    date_range = f"{fmt_date(all_dates[0])} → {fmt_date(all_dates[-1])}" if all_dates else "N/A"

    by_repo: dict[str, list[dict]] = {}
    for pr in prs:
        key = pr["repository"]["nameWithOwner"]
        by_repo.setdefault(key, []).append(pr)

    sorted_repos = sorted(by_repo.items(), key=lambda x: len(x[1]), reverse=True)

    lines: list[str] = [
        f"# Work Summary — @{GITHUB_USERNAME} @ {GITHUB_ORG}",
        "",
        f"_Generated: {now}_",
        "",
        "---",
        "",
    ]

    # --- Resume section (AI-generated) ---
    if resume_bullets:
        lines += [
            "## Resume Bullets",
            "",
            "_Copy-paste ready. Grouped by theme, synthesized from your PR history._",
            "",
            resume_bullets.strip(),
            "",
            "---",
            "",
        ]

    # --- Stats overview ---
    lines += [
        "## Overview",
        "",
        "| | |",
        "|---|---|",
        f"| Total PRs | {len(prs)} |",
        f"| Merged | {len(merged)} |",
        f"| Open | {len(open_prs)} |",
        f"| Closed (unmerged) | {len(closed)} |",
        f"| Repositories | {len(by_repo)} |",
        f"| Date range | {date_range} |",
        "",
        "---",
        "",
        "## By Repository",
        "",
    ]

    for repo_name, repo_prs in sorted_repos:
        merged_count = sum(1 for p in repo_prs if p["state"] == "MERGED")
        repo_prs_sorted = sorted(repo_prs, key=lambda p: p["createdAt"], reverse=True)

        lines.append(f"### {repo_name}")
        lines.append(f"_{len(repo_prs)} PRs — {merged_count} merged_")
        lines.append("")

        for pr in repo_prs_sorted:
            icon = STATE_ICON.get(pr["state"], "")
            date = fmt_date(pr.get("mergedAt") or pr.get("createdAt"))
            labels = [lb["name"] for lb in pr.get("labels", {}).get("nodes", [])]
            label_str = "  `" + "`  `".join(labels) + "`" if labels else ""
            lines.append(f"- {icon} [{pr['title']}]({pr['url']}) — {date}{label_str}")

        lines.append("")

    lines += [
        "---",
        "",
        "## Full Timeline",
        "",
        "_All PRs, newest first_",
        "",
    ]

    for pr in sorted(prs, key=lambda p: p["createdAt"], reverse=True):
        icon = STATE_ICON.get(pr["state"], "")
        date = fmt_date(pr.get("mergedAt") or pr.get("createdAt"))
        repo = pr["repository"]["name"]
        lines.append(f"- {icon} **{repo}** — [{pr['title']}]({pr['url']}) — {date}")

    return "\n".join(lines) + "\n"


def main() -> None:
    missing = [v for v in ("GITHUB_TOKEN", "GITHUB_ORG", "GITHUB_USERNAME") if not os.getenv(v)]
    if missing:
        print(f"Error: missing required environment variables: {', '.join(missing)}")
        print("Copy .env.example to .env and fill in your values.")
        sys.exit(1)

    date_filter = ""
    if SINCE_DATE:
        date_filter += f" since {SINCE_DATE}"
    if UNTIL_DATE:
        date_filter += f" until {UNTIL_DATE}"

    print(f"Fetching PRs for @{GITHUB_USERNAME} in '{GITHUB_ORG}'{date_filter}...")

    prs = fetch_all_prs()
    repo_count = len({p["repository"]["nameWithOwner"] for p in prs})
    print(f"Found {len(prs)} PRs across {repo_count} repositories.")

    resume_bullets = ""
    if ANTHROPIC_API_KEY:
        print("Generating resume bullets with Claude...")
        resume_bullets = generate_resume_bullets(prs)
    else:
        print("Warning: ANTHROPIC_API_KEY not set — skipping resume bullet generation.")
        print("         Add it to your .env to enable AI-generated resume content.")

    print("Generating summary...")
    markdown = generate_markdown(prs, resume_bullets)

    filename = f"work-summary-{GITHUB_ORG}-{datetime.now().strftime('%Y%m%d')}.md"
    Path(filename).write_text(markdown, encoding="utf-8")
    print(f"Saved: {filename}")


if __name__ == "__main__":
    main()
