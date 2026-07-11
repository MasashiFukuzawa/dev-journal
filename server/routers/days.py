import sqlite3

from fastapi import APIRouter, Depends

from server.deps import get_db
from server.schemas import DayMeta
from server.services.journal_service import get_days

router = APIRouter(prefix="/api/days", tags=["days"])


@router.get("", response_model=list[DayMeta])
def list_days(conn: sqlite3.Connection = Depends(get_db)):
    return get_days(conn)
