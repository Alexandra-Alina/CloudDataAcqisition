"""Routes for listing and downloading Parquet export files."""

import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from auth import verify_api_key
from models import ExportFileInfo

router = APIRouter(prefix="/exports", tags=["exports"])


def _get_exports_dir() -> Path:
    exports_dir = Path(os.environ.get("EXPORTS_DIR", "/app/exports"))
    exports_dir.mkdir(parents=True, exist_ok=True)
    return exports_dir


def _safe_filename(filename: str) -> str:
    """Reject any filename with path separators or parent traversal."""
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not filename.endswith(".parquet"):
        raise HTTPException(status_code=400, detail="Only .parquet files are served")
    return filename


@router.get("", response_model=list[ExportFileInfo])
async def list_exports(_: str = Depends(verify_api_key)):
    """List all available Parquet files with metadata."""
    exports_dir = _get_exports_dir()
    files = []
    for path in sorted(exports_dir.glob("*.parquet"), key=lambda p: p.stat().st_mtime, reverse=True):
        stat = path.stat()
        files.append(ExportFileInfo(
            name=path.name,
            size_bytes=stat.st_size,
            size_mb=round(stat.st_size / 1024 ** 2, 3),
            modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            download_url=f"/exports/{path.name}",
        ))
    return files


@router.get("/{filename}")
async def download_export(filename: str, _: str = Depends(verify_api_key)):
    """Download a specific Parquet file."""
    safe_name = _safe_filename(filename)
    file_path = _get_exports_dir() / safe_name

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File '{safe_name}' not found")

    return FileResponse(
        path=str(file_path),
        filename=safe_name,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )
