import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from server.deps import get_db
from server.schemas import DayDetail
from server.services.journal_service import get_day_detail

router = APIRouter(prefix="/api/days", tags=["entries"])


@router.get("/{date}", response_model=DayDetail)
def get_entry(date: str, conn: sqlite3.Connection = Depends(get_db)):
    detail = get_day_detail(conn, date)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"No data for {date}")
    return detail
