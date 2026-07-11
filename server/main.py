import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from server.routers import chat, days, entries, issues

_cli_dir = str(Path(__file__).parent.parent / "cli")
if _cli_dir not in sys.path:
    sys.path.insert(0, _cli_dir)

from collect import run_collect_cycle  # noqa: E402
from config import load_config  # noqa: E402
from db import init_db  # noqa: E402


async def _polling_loop() -> None:
    while True:
        try:
            result = await asyncio.to_thread(run_collect_cycle)
            print(f"[polling] cycle finished: {result}", flush=True)
        except Exception as e:
            print(f"[polling] error: {e}", flush=True)
        await asyncio.sleep(load_config().server.poll_interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    task = asyncio.create_task(_polling_loop()) if load_config().server.collection_enabled else None
    try:
        yield
    finally:
        if task:
            task.cancel()


app = FastAPI(title="dev-journal", version="0.1.0", lifespan=lifespan)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(load_config().server.allowed_hosts))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(days.router)
app.include_router(entries.router)
app.include_router(chat.router)
app.include_router(issues.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


static_dir = Path(__file__).parent / "static"
index_html = static_dir / "index.html"

if static_dir.exists() and index_html.exists():
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        # Static assets are served exclusively by the mounted /assets app.
        # Returning arbitrary files here would allow traversal outside static_dir.
        return FileResponse(index_html)
