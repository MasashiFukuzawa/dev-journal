import json
import sqlite3

from server.schemas import (
    DayDetail,
    DayMeta,
    Decision,
    DeepDive,
    IssueComment,
    IssueItem,
    IssueItemFull,
    PhaseGroup,
)


def get_days(conn: sqlite3.Connection) -> list[DayMeta]:
    rows = conn.execute(
        """
        SELECT
            closed_date_jst                              AS date,
            COUNT(*)                                     AS issue_count,
            COUNT(DISTINCT COALESCE(i.category_id, -1)) AS phase_count
        FROM issues i
        GROUP BY closed_date_jst
        ORDER BY closed_date_jst DESC
        """
    ).fetchall()
    return [
        DayMeta(date=r["date"], issue_count=r["issue_count"], phase_count=r["phase_count"])
        for r in rows
    ]


def get_day_detail(conn: sqlite3.Connection, date: str) -> DayDetail | None:
    rows = conn.execute(
        """
        SELECT i.issue_number, i.repo, i.title, i.url, i.closed_at, i.labels_json,
               c.name AS category_name, i.category_order, i.deep_dive_json,
               COALESCE(s.is_confirmed, 0) AS is_confirmed
        FROM issues i
        LEFT JOIN categories c ON c.id = i.category_id
        LEFT JOIN issue_states s
          ON s.repo = i.repo AND s.issue_number = i.issue_number
        WHERE i.closed_date_jst = ?
        ORDER BY i.category_order ASC, i.closed_at ASC
        """,
        (date,),
    ).fetchall()

    if not rows:
        return None

    phases_map: dict[tuple, list[IssueItem]] = {}
    for r in rows:
        labels = json.loads(r["labels_json"] or "[]")
        deep_dive: DeepDive | None = None
        if r["deep_dive_json"]:
            try:
                dd = json.loads(r["deep_dive_json"])
                decisions = [Decision(**d) for d in dd.get("decisions", [])]
                deep_dive = DeepDive(
                    background=dd.get("background", ""),
                    decisions=decisions,
                    constraints=dd.get("constraints", []),
                    future=dd.get("future", []),
                )
            except Exception:
                pass

        issue = IssueItem(
            issue_number=r["issue_number"],
            repo=r["repo"],
            title=r["title"],
            url=r["url"],
            closed_at=r["closed_at"],
            labels=labels,
            deep_dive=deep_dive,
            is_confirmed=bool(r["is_confirmed"]),
        )
        key = (r["category_order"] or 0, r["category_name"])
        phases_map.setdefault(key, []).append(issue)

    sorted_phases = sorted(phases_map.items(), key=lambda x: (x[0][0], x[0][1] or ""))
    phases = [
        PhaseGroup(name=name, order=index, issues=issues)
        for index, ((_, name), issues) in enumerate(sorted_phases)
    ]
    return DayDetail(date=date, phases=phases)


def _parse_deep_dive(deep_dive_json: str | None) -> DeepDive | None:
    if not deep_dive_json:
        return None
    try:
        dd = json.loads(deep_dive_json)
        decisions = [Decision(**d) for d in dd.get("decisions", [])]
        return DeepDive(
            background=dd.get("background", ""),
            decisions=decisions,
            constraints=dd.get("constraints", []),
            future=dd.get("future", []),
        )
    except Exception:
        return None


def get_issue(conn: sqlite3.Connection, repo: str, issue_number: int) -> IssueItemFull | None:
    row = conn.execute(
        """
        SELECT id, issue_number, repo, title, body, labels_json, url, closed_at, deep_dive_json
        FROM issues
        WHERE repo = ? AND issue_number = ?
        """,
        (repo, issue_number),
    ).fetchone()
    if row is None:
        return None

    comment_rows = conn.execute(
        "SELECT author, body, created_at FROM comments WHERE issue_pk = ? ORDER BY created_at ASC",
        (row["id"],),
    ).fetchall()

    labels = json.loads(row["labels_json"] or "[]")
    comments = [
        IssueComment(author=c["author"], body=c["body"], created_at=c["created_at"])
        for c in comment_rows
    ]

    return IssueItemFull(
        issue_number=row["issue_number"],
        repo=row["repo"],
        title=row["title"],
        body=row["body"],
        url=row["url"],
        closed_at=row["closed_at"],
        labels=labels,
        deep_dive=_parse_deep_dive(row["deep_dive_json"]),
        comments=comments,
    )
