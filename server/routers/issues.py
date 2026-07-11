import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from server.deps import get_db
from server.schemas import IssueItemFull
from server.services.journal_service import get_issue

router = APIRouter(prefix="/api/issues", tags=["issues"])


class IssueStateRequest(BaseModel):
    is_confirmed: bool


@router.get("/{org}/{repo_name}/{issue_number}", response_model=IssueItemFull)
def get_issue_endpoint(
    org: str,
    repo_name: str,
    issue_number: int,
    conn: sqlite3.Connection = Depends(get_db),
):
    repo = f"{org}/{repo_name}"
    issue = get_issue(conn, repo, issue_number)
    if issue is None:
        raise HTTPException(status_code=404, detail=f"Issue {repo}#{issue_number} not found")
    return issue


@router.patch("/{org}/{repo_name}/{issue_number}/state")
def update_issue_state(
    org: str,
    repo_name: str,
    issue_number: int,
    req: IssueStateRequest,
    conn: sqlite3.Connection = Depends(get_db),
):
    repo = f"{org}/{repo_name}"
    exists = conn.execute(
        "SELECT 1 FROM issues WHERE repo = ? AND issue_number = ?",
        (repo, issue_number),
    ).fetchone()
    if exists is None:
        raise HTTPException(status_code=404, detail=f"Issue {repo}#{issue_number} not found")

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO issue_states (repo, issue_number, is_confirmed, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(repo, issue_number) DO UPDATE SET
            is_confirmed = excluded.is_confirmed,
            updated_at = excluded.updated_at
        """,
        (repo, issue_number, int(req.is_confirmed), now),
    )
    conn.commit()
    return {"repo": repo, "issue_number": issue_number, "is_confirmed": req.is_confirmed}
