#!/usr/bin/env python3
"""Data collection CLI for dev-journal.

Subcommands:
  fetch-pending        Fetch Done issues from GitHub that need processing, print JSON
  save --file <path>   Accept fully-processed issues JSON file and upsert to DB
"""

import argparse
import fcntl
import json
import re
import subprocess
import sys
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))
from config import ensure_private_dir, ensure_private_file, load_config, state_dir
from db import get_connection, init_db

GH_BIN = "gh"


def _timezone() -> ZoneInfo:
    return ZoneInfo(load_config().timezone)


def _lock_file() -> Path:
    return ensure_private_dir(state_dir()) / "collect.lock"


def _claude_raw_log() -> Path:
    return ensure_private_dir(state_dir()) / "analysis-raw.log"


DEEP_DIVE_PROMPT = """\
以下は GitHub Issue の JSON データです。
この Issue の `deep_dive_json` だけを含む JSON オブジェクトを返してください。

ルール:
- JSON オブジェクトのみを返す。前置き・後書き・コードフェンス・説明文は一切不要。
- `deep_dive_json`: 以下の構造を持つ JSON オブジェクト:
  {
    "background": "この Issue に取り組んだ背景・文脈（2〜3文）",
    "decisions": [
      {
        "kind": "adopted"|"rejected"|"implemented"|"out_of_scope",
        "title": "決定内容",
        "reason": "理由"
      }
    ],
    "constraints": ["制約や前提条件"],
    "future": ["今後の課題や改善点"]
  }

入力データ:
"""

CATEGORY_PROMPT = """\
以下は同じ日にDoneになったGitHub Issueの一覧です。
各Issueに `category_name` と `category_order` を付与した JSON 配列だけを返してください。

ルール:
- JSON 配列のみを返す。前置き・後書き・コードフェンス・説明文は一切不要。
- `category_name`: 意味的にグルーピングした日本語カテゴリ名。
  例: "インフラ整備", "セキュリティ強化"。Issue が 1 件のみなら null。
- `category_order`: 同日内のカテゴリ表示順。0 始まりの整数。
  同じカテゴリ名には同じ order を付ける。
- 各要素は以下の形式。
  `{"issue_number": <int>, "category_name": <str|null>, "category_order": <int>}`

入力データ:
"""


def _now_jst() -> datetime:
    return datetime.now(_timezone())


def _to_closed_date_jst(closed_at_utc: str) -> str:
    dt = datetime.fromisoformat(closed_at_utc.replace("Z", "+00:00"))
    return dt.astimezone(_timezone()).strftime("%Y-%m-%d")


def _parse_repo_from_url(url: str) -> str | None:
    m = re.match(r"https://github\.com/([^/]+/[^/]+)/issues/\d+", url)
    return m.group(1) if m else None


def _run_gh(*args: str) -> dict | list:
    result = subprocess.run(
        [GH_BIN, *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


PROJECT_QUERY = """
query($login: String!, $number: Int!, $cursor: String) {
  OWNER(login: $login) {
    projectV2(number: $number) {
      items(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          content { ... on Issue { number url closedAt repository { nameWithOwner } } }
          fieldValues(first: 50) {
            nodes {
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
                field { ... on ProjectV2SingleSelectField { name } }
              }
            }
          }
        }
      }
    }
  }
}
"""


def _project_page(owner: str, number: int, cursor: str | None) -> dict:
    """Fetch one ProjectV2 page, supporting organization and user owners."""
    last_error: subprocess.CalledProcessError | None = None
    for owner_type in ("organization", "user"):
        query = PROJECT_QUERY.replace("OWNER", owner_type)
        args = [
            "api",
            "graphql",
            "-f",
            f"query={query}",
            "-F",
            f"login={owner}",
            "-F",
            f"number={number}",
        ]
        if cursor:
            args.extend(("-F", f"cursor={cursor}"))
        try:
            result = _run_gh(*args)
        except subprocess.CalledProcessError as exc:
            last_error = exc
            continue
        owner_data = result.get("data", {}).get(owner_type) if isinstance(result, dict) else None
        if owner_data and owner_data.get("projectV2"):
            return owner_data["projectV2"]["items"]
    if last_error:
        raise last_error
    raise RuntimeError(f"GitHub Project {owner}/{number} was not found")


def _get_scoped_project_items() -> list[dict]:
    cfg = load_config().github
    assert cfg.project_owner is not None and cfg.project_number is not None
    repositories = set(cfg.repositories)
    cutoff = datetime.now(timezone.utc) - timedelta(days=cfg.lookback_days)
    items: list[dict] = []
    cursor: str | None = None
    while True:
        page = _project_page(cfg.project_owner, cfg.project_number, cursor)
        for node in page.get("nodes", []):
            content = node.get("content") or {}
            repo = (content.get("repository") or {}).get("nameWithOwner")
            closed_at = content.get("closedAt")
            if (
                not repo
                or (repositories and repo not in repositories)
                or not closed_at
            ):
                continue
            try:
                closed_at_dt = datetime.fromisoformat(closed_at.replace("Z", "+00:00"))
            except (TypeError, ValueError):
                continue
            if closed_at_dt < cutoff:
                continue
            status = ""
            for value in (node.get("fieldValues") or {}).get("nodes", []):
                if (value.get("field") or {}).get("name") == "Status":
                    status = value.get("name", "")
                    break
            if status.casefold() == cfg.done_status.casefold():
                items.append(
                    {
                        "content": {
                            "type": "Issue",
                            "number": content["number"],
                            "url": content["url"],
                        },
                        "status": status,
                    }
                )
        page_info = page.get("pageInfo", {})
        if not page_info.get("hasNextPage"):
            return items
        cursor = page_info.get("endCursor")


def _get_done_items() -> list[dict]:
    cfg = load_config()
    if cfg.github.project_owner is not None:
        return _get_scoped_project_items()
    warnings.warn(
        "github.project_owner/project_number are unset; using legacy status matching across "
        "all projects. Configure a Project scope to avoid collecting an unrelated Done item.",
        UserWarning,
        stacklevel=2,
    )
    cutoff_utc = (datetime.now(timezone.utc) - timedelta(days=cfg.github.lookback_days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    done = []
    for repo in cfg.github.repositories:
        try:
            pages = _run_gh(
                "api",
                "--paginate",
                "--slurp",
                f"repos/{repo}/issues?state=closed&per_page=100&since={cutoff_utc}",
            )
            issues = [issue for page in pages for issue in page if "pull_request" not in issue]
        except subprocess.CalledProcessError as e:
            print(f"Warning: failed to list issues for {repo}: {e}", file=sys.stderr)
            continue

        for issue in issues:
            closed_at = issue.get("closedAt", issue.get("closed_at", ""))
            if closed_at < cutoff_utc:
                continue
            try:
                detail = _run_gh(
                    "issue",
                    "view",
                    str(issue["number"]),
                    "--repo",
                    repo,
                    "--json",
                    "projectItems",
                )
            except subprocess.CalledProcessError as e:
                print(
                    f"Warning: failed to fetch projectItems for {repo}#{issue['number']}: {e}",
                    file=sys.stderr,
                )
                continue

            for pi in detail.get("projectItems", []):
                status = pi.get("status", "")
                if isinstance(status, dict):
                    status = status.get("name", "")
                if str(status).casefold() == cfg.github.done_status.casefold():
                    done.append(
                        {
                            "content": {
                                "type": "Issue",
                                "number": issue["number"],
                                "url": issue.get("html_url") or issue.get("url"),
                            },
                            "status": "Done",
                        }
                    )
                    break
    return done


def _extract_issue_ref(item: dict) -> tuple[int, str] | None:
    content = item.get("content", {})
    url = content.get("url", "")
    repo = _parse_repo_from_url(url)
    if not repo:
        return None
    number = content.get("number")
    if not number:
        m = re.search(r"/issues/(\d+)$", url)
        if m:
            number = int(m.group(1))
    return (int(number), repo) if number else None


def _fetch_issue_detail(number: int, repo: str) -> dict:
    return _run_gh(
        "issue",
        "view",
        str(number),
        "--repo",
        repo,
        "--json",
        "number,title,body,createdAt,closedAt,stateReason,labels,url,comments",
    )


def _get_db_registered(conn) -> set[tuple[int, str]]:
    rows = conn.execute(
        "SELECT issue_number, repo FROM issues WHERE deep_dive_json IS NOT NULL"
    ).fetchall()
    return {(r["issue_number"], r["repo"]) for r in rows}


# ---------------------------------------------------------------------------
# Public API (used by server polling + CLI subcommands)
# ---------------------------------------------------------------------------


def fetch_pending_issues() -> dict[str, list[dict]]:
    """Fetch Done issues not yet processed. Returns {date: [issue_dict, ...]}."""
    init_db()
    conn = get_connection()

    cutoff_jst = (_now_jst() - timedelta(days=load_config().github.lookback_days)).date()
    registered = _get_db_registered(conn)
    conn.close()

    done_items = _get_done_items()

    pending_refs: list[tuple[int, str]] = []
    for item in done_items:
        ref = _extract_issue_ref(item)
        if not ref or ref in registered:
            continue
        pending_refs.append(ref)

    if not pending_refs:
        return {}

    by_date: dict[str, list[dict]] = {}
    for number, repo in pending_refs:
        try:
            detail = _fetch_issue_detail(number, repo)
        except subprocess.CalledProcessError as e:
            print(f"Warning: failed to fetch issue {repo}#{number}: {e}", file=sys.stderr)
            continue

        if detail.get("stateReason") == "NOT_PLANNED":
            continue

        closed_at = detail.get("closedAt", "")
        if not closed_at:
            continue
        closed_date_jst = _to_closed_date_jst(closed_at)
        if closed_date_jst < str(cutoff_jst):
            continue

        comments = [
            {
                "author": c.get("author", {}).get("login", "unknown"),
                "body": c.get("body", ""),
                "created_at": c.get("createdAt", ""),
            }
            for c in detail.get("comments", [])
        ]
        labels = [lb.get("name", "") for lb in detail.get("labels", [])]

        by_date.setdefault(closed_date_jst, []).append(
            {
                "issue_number": number,
                "repo": repo,
                "title": detail.get("title", ""),
                "body": detail.get("body", ""),
                "labels": labels,
                "url": detail.get("url", ""),
                "closed_at": closed_at,
                "closed_date_jst": closed_date_jst,
                "comments": comments,
            }
        )

    return by_date


def _upsert_category(conn, name: str) -> int:
    """Insert category if not exists, return its id."""
    conn.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,))
    row = conn.execute("SELECT id FROM categories WHERE name = ?", (name,)).fetchone()
    return row["id"]


def save_processed_issues(issues: list[dict]) -> int:
    """Upsert processed issues (with deep_dive_json) to SQLite. Returns count saved."""
    init_db()
    conn = get_connection()
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with conn:
        for issue in issues:
            deep_dive = issue.get("deep_dive_json")
            if isinstance(deep_dive, dict):
                deep_dive = json.dumps(deep_dive, ensure_ascii=False)

            # category_name → category_id の解決（後方互換: 古いsave --file 呼び出し用）
            category_id = issue.get("category_id")
            if category_id is None:
                category_name = issue.get("category_name")
                if category_name:
                    category_id = _upsert_category(conn, category_name)

            conn.execute(
                """
                INSERT INTO issues
                    (issue_number, repo, title, body, labels_json, url,
                     closed_at, closed_date_jst, category_id, category_order,
                     deep_dive_json, generated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(repo, issue_number) DO UPDATE SET
                    title=excluded.title,
                    body=excluded.body,
                    labels_json=excluded.labels_json,
                    url=excluded.url,
                    closed_at=excluded.closed_at,
                    closed_date_jst=excluded.closed_date_jst,
                    category_id=excluded.category_id,
                    category_order=excluded.category_order,
                    deep_dive_json=excluded.deep_dive_json,
                    generated_at=excluded.generated_at
                """,
                (
                    issue["issue_number"],
                    issue["repo"],
                    issue.get("title", ""),
                    issue.get("body"),
                    json.dumps(issue.get("labels", []), ensure_ascii=False),
                    issue.get("url", ""),
                    issue["closed_at"],
                    issue["closed_date_jst"],
                    category_id,
                    issue.get("category_order", 0),
                    deep_dive,
                    now_iso,
                ),
            )

            row = conn.execute(
                "SELECT id FROM issues WHERE repo=? AND issue_number=?",
                (issue["repo"], issue["issue_number"]),
            ).fetchone()
            if row:
                pk = row["id"]
                conn.execute("DELETE FROM comments WHERE issue_pk=?", (pk,))
                for c in issue.get("comments", []):
                    conn.execute(
                        """
                        INSERT INTO comments (issue_pk, author, body, created_at)
                        VALUES (?,?,?,?)
                        """,
                        (pk, c.get("author", ""), c.get("body", ""), c.get("created_at", "")),
                    )

    return len(issues)


def assign_categories_for_date(conn, date: str) -> None:
    """Pass 2: fetch all issues for a date from DB, ask Claude to assign categories, update DB.

    Always operates on the full day's issue set so category_order is globally consistent
    within the day, regardless of how many cycles have touched the day.
    """
    rows = conn.execute(
        "SELECT issue_number, repo, title FROM issues WHERE closed_date_jst=? ORDER BY closed_at",
        (date,),
    ).fetchall()

    if not rows:
        return

    if len(rows) == 1:
        with conn:
            conn.execute(
                """
                UPDATE issues
                SET category_id=NULL, category_order=0
                WHERE closed_date_jst=? AND issue_number=? AND repo=?
                """,
                (date, rows[0]["issue_number"], rows[0]["repo"]),
            )
        return

    issue_map = {r["issue_number"]: dict(r) for r in rows}
    input_data = [{"issue_number": r["issue_number"], "title": r["title"]} for r in rows]
    prompt = CATEGORY_PROMPT + json.dumps(input_data, ensure_ascii=False, indent=2)

    try:
        analysis = load_config().analysis
        result = subprocess.run(
            [
                analysis.command,
                "-p",
                "--tools",
                "",
                "--strict-mcp-config",
                "--mcp-config",
                '{"mcpServers":{}}',
                "--output-format",
                "json",
                "--model",
                analysis.model,
            ],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=load_config().analysis.timeout_seconds,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"[collect] category pass failed for {date}: {e}", file=sys.stderr)
        return

    if result.returncode != 0:
        print(f"[collect] category pass error for {date}: {result.stderr[:300]}", file=sys.stderr)
        return

    try:
        outer = json.loads(result.stdout)
        raw = outer.get("result", "")
        if isinstance(raw, str):
            raw = re.sub(r"```(?:json)?\s*", "", raw).strip()
        assignments = raw if isinstance(raw, list) else json.loads(raw)
        if not isinstance(assignments, list):
            raise ValueError(f"expected list, got {type(assignments)}")
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        print(f"[collect] category parse failed for {date}: {e}", file=sys.stderr)
        return

    with conn:
        for a in assignments:
            num = a.get("issue_number")
            cat_name = a.get("category_name")
            cat_order = a.get("category_order", 0)
            issue = issue_map.get(num)
            if not issue:
                continue

            category_id = None
            if cat_name:
                conn.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (cat_name,))
                row = conn.execute(
                    "SELECT id FROM categories WHERE name = ?",
                    (cat_name,),
                ).fetchone()
                category_id = row["id"] if row else None

            conn.execute(
                """
                UPDATE issues
                SET category_id=?, category_order=?
                WHERE closed_date_jst=? AND issue_number=? AND repo=?
                """,
                (category_id, cat_order, date, num, issue["repo"]),
            )
        normalize_category_orders_for_date(conn, date)


def normalize_category_orders_for_date(conn, date: str) -> None:
    rows = conn.execute(
        """
        SELECT DISTINCT category_id, COALESCE(category_order, 0) AS category_order
        FROM issues
        WHERE closed_date_jst = ?
        ORDER BY COALESCE(category_order, 0), COALESCE(category_id, -1)
        """,
        (date,),
    ).fetchall()
    with conn:
        for order, row in enumerate(rows):
            conn.execute(
                """
                UPDATE issues
                SET category_order = ?
                WHERE closed_date_jst = ?
                  AND (
                    (category_id IS NULL AND ? IS NULL)
                    OR category_id = ?
                  )
                """,
                (order, date, row["category_id"], row["category_id"]),
            )


def generate_deep_dive_via_claude_cli(issue: dict) -> dict | None:
    """Call `claude -p` to generate deep_dive_json for a single issue.

    Returns enriched issue dict, or None on failure.
    """
    prompt = DEEP_DIVE_PROMPT + json.dumps(issue, ensure_ascii=False, indent=2)

    try:
        cfg = load_config().analysis
        result = subprocess.run(
            [
                cfg.command,
                "-p",
                "--tools",
                "",
                "--strict-mcp-config",
                "--mcp-config",
                '{"mcpServers":{}}',
                "--output-format",
                "json",
                "--model",
                cfg.model,
            ],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=cfg.timeout_seconds,
        )
    except FileNotFoundError:
        print("[collect] claude CLI not found. Skipping deep_dive generation.", file=sys.stderr)
        return None
    except subprocess.TimeoutExpired:
        print(
            f"[collect] claude CLI timed out after {load_config().analysis.timeout_seconds}s. "
            f"issue={issue.get('issue_number')}",
            file=sys.stderr,
        )
        return None

    if result.returncode != 0:
        print(
            f"[collect] claude CLI exited {result.returncode}: {result.stderr[:500]}",
            file=sys.stderr,
        )
        return None

    try:
        outer = json.loads(result.stdout)
        raw = outer.get("result", "")
        if isinstance(raw, str):
            raw = re.sub(r"```(?:json)?\s*", "", raw).strip()
        parsed = raw if isinstance(raw, dict) else json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError(f"expected dict, got {type(parsed)}")
        return {**issue, "deep_dive_json": parsed.get("deep_dive_json", parsed)}
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        print(f"[collect] failed to parse claude output: {e}", file=sys.stderr)
        if not load_config().analysis.save_raw_output:
            return None
        try:
            log_path = _claude_raw_log()
            log_path.write_text(result.stdout, encoding="utf-8")
            ensure_private_file(log_path)
        except OSError:
            pass
        return None


def prune_old_issues() -> int:
    """Delete issues older than the configured retention period. Returns count deleted."""
    init_db()
    cutoff = (_now_jst().date() - timedelta(days=load_config().retention_days)).isoformat()
    conn = get_connection()
    with conn:
        result = conn.execute("DELETE FROM issues WHERE closed_date_jst < ?", (cutoff,))
    conn.close()
    return result.rowcount


def run_collect_cycle() -> dict:
    """Full collect cycle: fetch → AI generate → save → categorize → prune.

    Pass 1 (per issue): generate deep_dive_json, save with category_id=NULL.
    Pass 2 (per day):   assign categories to all issues for the day in one Claude call.

    Uses a file lock to prevent concurrent runs.
    """
    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    lock_file = _lock_file()
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = open(lock_file, "w")
    ensure_private_file(lock_file)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_fd.close()
        print("[collect] another cycle is already running. Skipping.", file=sys.stderr)
        return {
            "fetched": 0,
            "saved": 0,
            "skipped": True,
            "started_at": started_at,
            "finished_at": started_at,
        }

    try:
        print("[collect] cycle start", file=sys.stderr)

        issues_by_date = fetch_pending_issues()
        total_fetched = sum(len(v) for v in issues_by_date.values())
        print(f"[collect] fetched {total_fetched} pending issue(s)", file=sys.stderr)

        if total_fetched == 0:
            finished_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            return {"fetched": 0, "saved": 0, "started_at": started_at, "finished_at": finished_at}

        saved = 0
        for date, date_issues in sorted(issues_by_date.items()):
            # Pass 1: deep_dive を1件ずつ生成・保存
            enriched_for_date: list[dict] = []
            for issue in date_issues:
                enriched = generate_deep_dive_via_claude_cli(issue)
                if enriched:
                    save_processed_issues([enriched])
                    saved += 1
                    enriched_for_date.append(enriched)

            # Pass 2: その日の全 Issue（既存分含む）をDBから取得してカテゴリ付与
            if enriched_for_date:
                conn = get_connection()
                try:
                    assign_categories_for_date(conn, date)
                finally:
                    conn.close()

            print(f"[collect] {date}: done ({len(enriched_for_date)} issues)", file=sys.stderr)

        print(f"[collect] saved={saved}", file=sys.stderr)

        pruned = prune_old_issues()
        print(f"[collect] pruned={pruned}", file=sys.stderr)

        finished_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {
            "fetched": total_fetched,
            "saved": saved,
            "started_at": started_at,
            "finished_at": finished_at,
        }

    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


# ---------------------------------------------------------------------------
# CLI subcommands (thin wrappers; used by SKILL.md manual flow + launchd fallback)
# ---------------------------------------------------------------------------


def cmd_fetch_pending(args: argparse.Namespace) -> None:
    init_db()
    by_date = fetch_pending_issues()
    print(json.dumps({"dates": by_date}, ensure_ascii=False, indent=2))


def cmd_save(args: argparse.Namespace) -> None:
    path = args.file
    with open(path) as f:
        data = json.load(f)
    issues: list[dict] = data if isinstance(data, list) else data.get("issues", [])
    saved = save_processed_issues(issues)
    print(f"Saved {saved} issue(s).", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="dev-journal data collection CLI")
    parser.add_argument(
        "--config",
        help="Config path (overrides DEV_JOURNAL_CONFIG and the XDG default)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("fetch-pending", help="Fetch unprocessed Done issues, print JSON")

    save_p = sub.add_parser("save", help="Upsert processed issues JSON to DB")
    save_p.add_argument("--file", required=True, help="Path to JSON file of processed issues")

    args = parser.parse_args()
    if args.config:
        import os

        os.environ["DEV_JOURNAL_CONFIG"] = args.config
        load_config(args.config, required=True)
    if args.command == "fetch-pending":
        cmd_fetch_pending(args)
    elif args.command == "save":
        cmd_save(args)


if __name__ == "__main__":
    main()
