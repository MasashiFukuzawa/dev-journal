import json
import re
import sqlite3
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

_cli_dir = str(Path(__file__).parent.parent.parent / "cli")

if _cli_dir not in sys.path:
    sys.path.insert(0, _cli_dir)

from config import load_config  # noqa: E402
from db import default_db_path  # noqa: E402

router = APIRouter(prefix="/api/chat", tags=["chat"])

SYSTEM_PROMPT = """あなたは開発日誌アシスタントです。日本語で回答してください。
選択された GitHub Issue と保存済みの開発文脈に基づいて質問に答えます。
回答は簡潔かつ具体的に。
表形式（markdownテーブル）は使用しない。情報を整理する際は箇条書きや番号リストを使う。"""

_REPO_PATTERN = re.compile(r"^[\w.\-]+/[\w.\-]+$")


def _open_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(default_db_path()), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _build_system_context(conn: sqlite3.Connection, issue_refs: list[dict[str, Any]]) -> str:
    if not issue_refs:
        return ""
    parts: list[str] = []
    for ref in issue_refs:
        row = conn.execute(
            "SELECT title, body, deep_dive_json FROM issues WHERE repo = ? AND issue_number = ?",
            (ref.get("repo"), ref.get("issue_number")),
        ).fetchone()
        if not row:
            continue
        parts.append(f"## Issue #{ref['issue_number']} ({ref['repo']})")
        parts.append(f"**タイトル**: {row['title']}")
        if row["body"]:
            parts.append(f"**本文**:\n{row['body']}")
        if row["deep_dive_json"]:
            parts.append(f"**解析結果**:\n{row['deep_dive_json']}")

        comments = conn.execute(
            "SELECT author, body FROM comments WHERE issue_pk = "
            "(SELECT id FROM issues WHERE repo = ? AND issue_number = ?)",
            (ref.get("repo"), ref.get("issue_number")),
        ).fetchall()
        if comments:
            parts.append("**コメント**:")
            for c in comments:
                parts.append(f"- {c['author']}: {c['body']}")
        parts.append("")
    return "\n".join(parts)


def _build_prompt(
    user_content: str,
    past_messages: list[dict[str, Any]],
    system_context: str,
) -> str:
    parts: list[str] = [SYSTEM_PROMPT]
    if system_context:
        parts.append("\n---\n[Issue コンテキスト]\n" + system_context)
    if past_messages:
        history = "\n".join(
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
            for m in past_messages
        )
        parts.append("\n---\n[過去の会話]\n" + history)
    parts.append("\n---\n[最新の質問]\n" + user_content)
    return "\n".join(parts)


def _normalize_issue_refs(issue_refs: list[dict[str, Any]]) -> str:
    normalized = sorted(
        ({"repo": r.get("repo", ""), "issue_number": r.get("issue_number", 0)} for r in issue_refs),
        key=lambda r: (r["repo"], r["issue_number"]),
    )
    return json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))


def _run_claude(prompt: str) -> str:
    cfg = load_config().analysis
    cmd = [
        cfg.command,
        "-p",
        prompt,
        "--tools",
        "",
        "--strict-mcp-config",
        "--mcp-config",
        '{"mcpServers":{}}',
        "--model",
        cfg.model,
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=cfg.timeout_seconds,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or "claude failed")
    return result.stdout.strip()


def _process_message(message_id: int, prompt: str) -> None:
    try:
        response = _run_claude(prompt)
        status = "done"
        content = response
    except Exception as e:
        status = "error"
        content = str(e)

    conn = _open_conn()
    try:
        conn.execute(
            "UPDATE chat_messages SET content = ?, status = ? WHERE id = ?",
            (content, status, message_id),
        )
        conn.commit()
    finally:
        conn.close()


class CreateThreadRequest(BaseModel):
    issue_refs: list[dict[str, Any]] = []


class SendMessageRequest(BaseModel):
    content: str


@router.post("/threads")
def create_thread(req: CreateThreadRequest):
    normalized = _normalize_issue_refs(req.issue_refs)
    thread_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn = _open_conn()
    try:
        # INSERT OR IGNORE lets the UNIQUE constraint on issue_refs_json silently
        # discard the row if a concurrent request already created the thread.
        conn.execute(
            "INSERT OR IGNORE INTO chat_threads (id, created_at, issue_refs_json) VALUES (?, ?, ?)",
            (thread_id, now, normalized),
        )
        conn.commit()

        # 同一issueのスレッドが複数ある場合はメッセージ有り・古い順を優先する
        row = conn.execute(
            "SELECT ct.id, ct.created_at, ct.title, ct.issue_refs_json "
            "FROM chat_threads ct "
            "LEFT JOIN chat_messages cm ON cm.thread_id = ct.id "
            "WHERE ct.issue_refs_json = ? "
            "GROUP BY ct.id "
            "ORDER BY (COUNT(cm.id) > 0) DESC, ct.created_at ASC "
            "LIMIT 1",
            (normalized,),
        ).fetchone()

        conn.execute(
            "UPDATE chat_messages SET status = 'error', content = '(中断されました)' "
            "WHERE thread_id = ? AND status = 'pending'",
            (row["id"],),
        )
        conn.commit()

        messages = conn.execute(
            "SELECT id, thread_id, role, content, status, created_at "
            "FROM chat_messages WHERE thread_id = ? ORDER BY id",
            (row["id"],),
        ).fetchall()
        latest_assistant = max(
            (m["id"] for m in messages if m["role"] == "assistant" and m["status"] == "done"),
            default=None,
        )
        if latest_assistant is not None:
            conn.execute(
                """
                UPDATE chat_threads
                SET last_read_assistant_message_id = ?, last_read_at = ?
                WHERE id = ?
                """,
                (latest_assistant, datetime.now(timezone.utc).isoformat(), row["id"]),
            )
            conn.commit()
        return {
            "id": row["id"],
            "created_at": row["created_at"],
            "title": row["title"],
            "issue_refs": json.loads(row["issue_refs_json"]),
            "messages": [dict(m) for m in messages],
        }
    finally:
        conn.close()


@router.get("/threads")
def list_threads():
    conn = _open_conn()
    try:
        rows = conn.execute(
            "SELECT ct.id, ct.created_at, ct.title, ct.issue_refs_json, "
            "ct.last_read_assistant_message_id, "
            "COUNT(cm.id) AS message_count, "
            "SUM(CASE WHEN cm.status = 'pending' THEN 1 ELSE 0 END) AS pending_count, "
            "SUM(CASE WHEN cm.role = 'assistant' AND cm.status = 'done' "
            "          AND cm.id > COALESCE(ct.last_read_assistant_message_id, 0) "
            "    THEN 1 ELSE 0 END) AS unread_count, "
            "MAX(cm.created_at) AS last_message_at "
            "FROM chat_threads ct "
            "LEFT JOIN chat_messages cm ON cm.thread_id = ct.id "
            "GROUP BY ct.id "
            "ORDER BY ct.created_at DESC"
        ).fetchall()
        return [
            {
                "id": r["id"],
                "created_at": r["created_at"],
                "title": r["title"],
                "issue_refs": json.loads(r["issue_refs_json"]),
                "message_count": r["message_count"],
                "has_pending": bool(r["pending_count"]),
                "unread_count": r["unread_count"] or 0,
                "has_unread": bool(r["unread_count"]),
                "last_message_at": r["last_message_at"],
            }
            for r in rows
        ]
    finally:
        conn.close()


@router.get("/threads/{thread_id}")
def get_thread(thread_id: str):
    conn = _open_conn()
    try:
        row = conn.execute(
            "SELECT id, created_at, title, issue_refs_json FROM chat_threads WHERE id = ?",
            (thread_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Thread not found")
        messages = conn.execute(
            "SELECT id, thread_id, role, content, status, created_at FROM chat_messages "
            "WHERE thread_id = ? ORDER BY id",
            (thread_id,),
        ).fetchall()
        return {
            "id": row["id"],
            "created_at": row["created_at"],
            "title": row["title"],
            "issue_refs": json.loads(row["issue_refs_json"]),
            "messages": [dict(m) for m in messages],
        }
    finally:
        conn.close()


@router.post("/threads/{thread_id}/read")
def mark_thread_read(thread_id: str):
    conn = _open_conn()
    try:
        row = conn.execute(
            "SELECT id FROM chat_threads WHERE id = ?",
            (thread_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Thread not found")

        latest = conn.execute(
            "SELECT MAX(id) AS id FROM chat_messages "
            "WHERE thread_id = ? AND role = 'assistant' AND status = 'done'",
            (thread_id,),
        ).fetchone()
        latest_id = latest["id"] if latest else None
        conn.execute(
            """
            UPDATE chat_threads
            SET last_read_assistant_message_id = ?, last_read_at = ?
            WHERE id = ?
            """,
            (latest_id, datetime.now(timezone.utc).isoformat(), thread_id),
        )
        conn.commit()
        return {"id": thread_id, "last_read_assistant_message_id": latest_id}
    finally:
        conn.close()


@router.delete("/threads/{thread_id}", status_code=204)
def delete_thread(thread_id: str):
    conn = _open_conn()
    try:
        conn.execute("DELETE FROM chat_threads WHERE id = ?", (thread_id,))
        conn.commit()
    finally:
        conn.close()


@router.post("/threads/{thread_id}/messages")
def send_message(thread_id: str, req: SendMessageRequest):
    conn = _open_conn()
    try:
        thread_row = conn.execute(
            "SELECT issue_refs_json FROM chat_threads WHERE id = ?", (thread_id,)
        ).fetchone()
        if not thread_row:
            raise HTTPException(status_code=404, detail="Thread not found")

        issue_refs = json.loads(thread_row["issue_refs_json"])
        system_context = _build_system_context(conn, issue_refs)

        past_messages = conn.execute(
            "SELECT role, content FROM chat_messages "
            "WHERE thread_id = ? AND status = 'done' ORDER BY id",
            (thread_id,),
        ).fetchall()
        prompt = _build_prompt(req.content, [dict(m) for m in past_messages], system_context)

        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO chat_messages (thread_id, role, content, status, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (thread_id, "user", req.content, "done", now),
        )
        cur = conn.execute(
            "INSERT INTO chat_messages (thread_id, role, content, status, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (thread_id, "assistant", "", "pending", now),
        )
        assert cur.lastrowid is not None
        message_id: int = cur.lastrowid
        conn.commit()
    finally:
        conn.close()

    threading.Thread(
        target=_process_message,
        args=(message_id, prompt),
        daemon=True,
    ).start()

    return {"status": "pending", "message_id": message_id}


@router.get("/threads/{thread_id}/messages/{message_id}/status")
def get_message_status(thread_id: str, message_id: int):
    conn = _open_conn()
    try:
        row = conn.execute(
            "SELECT status, content FROM chat_messages WHERE id = ? AND thread_id = ?",
            (message_id, thread_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Message not found")
        return {"status": row["status"], "content": row["content"]}
    finally:
        conn.close()
