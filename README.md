# github-work-summary

Fetches all pull requests you authored in a GitHub org **or your personal repositories** and generates a Markdown file with:

1. **Resume bullets** — AI-generated (via Claude), grouped by technical theme, ready to copy onto a resume or LinkedIn
2. **PR list by repository** — every PR with state, date, and labels
3. **Full timeline** — all PRs sorted newest-first

## Prerequisites

- Python 3.11+
- A GitHub Personal Access Token
- An Anthropic API key (for resume bullet generation)

## Setup

### 1. Clone the repo

```bash
git clone <your-repo-url>
cd github-work-summary
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create your `.env` file

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

| Variable | Required | Description |
|---|---|---|
| `GITHUB_TOKEN` | Yes | GitHub Personal Access Token (scopes: `repo`, `read:org`) |
| `REPO_TYPE` | No | `org` (default) to search an org, or `user` for personal repos |
| `GITHUB_ORG` | When `REPO_TYPE=org` | Your org's slug, e.g. `acme-corp` |
| `GITHUB_USERNAME` | Yes | Your GitHub username |
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key for resume bullet generation |
| `SINCE_DATE` | No | Only include PRs created on or after this date (`YYYY-MM-DD`) |
| `UNTIL_DATE` | No | Only include PRs created on or before this date (`YYYY-MM-DD`) |

#### Getting a GitHub token

1. Go to <https://github.com/settings/tokens/new>
2. Give it a name (e.g. `work-summary`)
3. Set an expiration
4. Check **`repo`** scope (and **`read:org`** if using `REPO_TYPE=org`)
5. Click **Generate token** and copy the value into `GITHUB_TOKEN`

#### Getting an Anthropic API key

1. Go to <https://console.anthropic.com/settings/keys>
2. Click **Create Key**
3. Copy the value into `ANTHROPIC_API_KEY`

### 4. Run it

```bash
python main.py
```

The output file is saved in the current directory as:

```
work-summary-<org>-<YYYYMMDD>.md          # REPO_TYPE=org (default)
work-summary-<username>-personal-<YYYYMMDD>.md  # REPO_TYPE=user
```

## Personal vs organization repos

By default the tool searches within a GitHub organization. To summarize PRs
across your own personal repositories instead, set `REPO_TYPE=user` in your
`.env` (and omit `GITHUB_ORG`):

```env
REPO_TYPE=user
GITHUB_USERNAME=your-username
```

Or inline:

```bash
REPO_TYPE=user python main.py
```

## Filtering by date

To limit the date range, set `SINCE_DATE` and/or `UNTIL_DATE` in your `.env`:

```env
SINCE_DATE=2024-01-01
UNTIL_DATE=2024-12-31
```

Or export them inline:

```bash
SINCE_DATE=2024-01-01 UNTIL_DATE=2024-12-31 python main.py
```

## Output structure

```
# Work Summary — @username @ org

## Resume Bullets          ← AI-generated, themed, copy-paste ready
### Backend Development
- Implemented ...
- Designed ...

### Infrastructure & DevOps
- Automated ...

## Overview               ← stats table

## By Repository          ← PR list per repo

## Full Timeline          ← all PRs, newest first
```

## Notes

- If `ANTHROPIC_API_KEY` is missing, the tool still runs but skips the resume section.
- PRs are fetched via the GitHub GraphQL API; pagination is handled automatically.
- PR descriptions are truncated to 400 characters before being sent to Claude to keep costs low.
