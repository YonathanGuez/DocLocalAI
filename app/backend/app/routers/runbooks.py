from fastapi import APIRouter, UploadFile, File, HTTPException, status
from pathlib import Path
import os
import subprocess

router = APIRouter(prefix="/api/runbooks", tags=["runbooks"])

# Read-only: sample runbooks
RUNBOOKS_DIR = Path(os.getenv("RUNBOOK_DIR", "/runbooks"))
# Read-write: user uploads (uses PVC in OpenShift)
RUNBOOKS_UPLOAD_DIR = Path(os.getenv("RUNBOOK_UPLOAD_DIR", "/runbooks-uploads"))


@router.get("/{filename}/content")
def get_runbook_content(filename: str):
    """Get the content of a specific runbook file"""
    # Validate filename
    if "/" in filename or "\\" in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename"
        )

    if not filename.endswith(('.md', '.txt')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type"
        )

    try:
        # Check uploaded files first
        file_path = RUNBOOKS_UPLOAD_DIR / filename
        source = "uploaded"

        # If not found in uploads, check samples
        if not file_path.exists():
            file_path = RUNBOOKS_DIR / filename
            source = "sample"

        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Runbook '{filename}' not found"
            )

        # Read file content
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        return {
            "filename": filename,
            "content": content,
            "source": source,
            "size": len(content)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read runbook: {str(e)}"
        )


@router.get("")
def list_runbooks():
    """List all runbook files from both sample and uploaded directories"""
    try:
        runbooks = []

        # List sample runbooks (read-only)
        if RUNBOOKS_DIR.exists():
            for file_path in RUNBOOKS_DIR.glob("*.md"):
                if file_path.name != "README.md":
                    stat = file_path.stat()
                    runbooks.append({
                        "filename": file_path.name,
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                        "source": "sample",
                        "deletable": False
                    })

        # List uploaded runbooks (read-write)
        if RUNBOOKS_UPLOAD_DIR.exists():
            for file_path in RUNBOOKS_UPLOAD_DIR.glob("*.md"):
                stat = file_path.stat()
                runbooks.append({
                    "filename": file_path.name,
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "source": "uploaded",
                    "deletable": True
                })

        return {"runbooks": sorted(runbooks, key=lambda x: x["filename"])}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list runbooks: {str(e)}"
        )


@router.post("/upload")
async def upload_runbook(file: UploadFile = File(...), auto_index: bool = True):
    """Upload a new runbook file (max 2MB, .md or .txt only) and auto-index"""
    MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB in bytes

    # Validate filename exists
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided"
        )

    # Validate file extension
    if not file.filename.endswith(('.md', '.txt')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .md and .txt files are allowed"
        )

    # Validate filename (no path traversal)
    if "/" in file.filename or "\\" in file.filename or file.filename == "README.md":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename"
        )

    try:
        # Ensure upload directory exists
        RUNBOOKS_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

        # Read file content
        content = await file.read()

        # Validate content is not empty
        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is empty"
            )

        # Validate file size (2MB limit)
        if len(content) > MAX_FILE_SIZE:
            size_mb = len(content) / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large ({size_mb:.2f} MB). Maximum size is 2 MB"
            )

        # Validate it's actually text (check for valid UTF-8)
        try:
            content.decode('utf-8')
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be valid UTF-8 text (markdown or plain text)"
            )

        # Save file to uploads directory
        file_path = RUNBOOKS_UPLOAD_DIR / file.filename
        with open(file_path, "wb") as f:
            f.write(content)

        # Trigger re-indexing in background if requested
        if auto_index:
            indexer_script = Path("/scripts/index_runbooks.py")
            if indexer_script.exists():
                subprocess.Popen(
                    ["python3", str(indexer_script)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )

        return {
            "success": True,
            "filename": file.filename,
            "size": len(content),
            "size_mb": round(len(content) / (1024 * 1024), 2),
            "message": f"Runbook '{file.filename}' uploaded and indexing started" if auto_index else f"Runbook '{file.filename}' uploaded successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload runbook: {str(e)}"
        )


@router.delete("/{filename}")
def delete_runbook(filename: str):
    """Delete a runbook file and trigger re-indexing (only user uploads, not samples)"""
    # Validate filename
    if "/" in filename or "\\" in filename or filename == "README.md":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename"
        )

    if not filename.endswith(('.md', '.txt')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type"
        )

    try:
        # Only allow deletion from uploads directory (not samples)
        file_path = RUNBOOKS_UPLOAD_DIR / filename

        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Runbook '{filename}' not found in uploads"
            )

        file_path.unlink()

        # Trigger re-indexing in background
        indexer_script = Path("/scripts/index_runbooks.py")
        if indexer_script.exists():
            subprocess.Popen(
                ["python3", str(indexer_script)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

        return {
            "success": True,
            "filename": filename,
            "message": f"Runbook '{filename}' deleted and re-indexing started"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete runbook: {str(e)}"
        )


@router.post("/reindex")
def trigger_reindex():
    """Trigger runbook re-indexing"""
    try:
        # Try to call the indexer script
        indexer_script = Path("/scripts/index_runbooks.py")

        if not indexer_script.exists():
            return {
                "success": False,
                "message": "Indexer script not found. Please restart runbook-indexer container."
            }

        # Run indexer in background
        subprocess.Popen(
            ["python3", str(indexer_script)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        return {
            "success": True,
            "message": "Re-indexing started in background"
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to trigger re-indexing: {str(e)}"
        }
