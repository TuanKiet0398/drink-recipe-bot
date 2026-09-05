from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.agent.clients import get_openai_client, get_qdrant_client
from app.auth import log_admin_action, require_admin
from app.db.base import get_db
from app.db.models import Document
from app.ingestion import chunk_text, embed_and_upsert

router = APIRouter(prefix="/admin/docs")

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5MB
ALLOWED_EXTENSIONS = (".txt", ".md")


@router.post("", status_code=201)
async def upload_doc(
    request: Request,
    file: UploadFile,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    filename = file.filename or ""
    if not filename.lower().endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail="Only .txt and .md files are supported currently",
        )

    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 5MB upload limit")

    text = raw.decode("utf-8", errors="ignore")
    chunks = chunk_text(text)

    doc = Document(filename=filename, chunk_count=len(chunks))
    db.add(doc)
    db.commit()
    db.refresh(doc)

    embed_and_upsert(
        chunks=chunks,
        filename=filename,
        document_id=doc.id,
        qdrant_client=get_qdrant_client(),
        openai_client=get_openai_client(),
    )

    log_admin_action(db, action="upload_doc", target=filename, ip=request.client.host if request.client else "")

    return {"id": doc.id, "filename": doc.filename, "chunk_count": doc.chunk_count}


@router.get("")
def list_docs(db: Session = Depends(get_db), admin_user: str = Depends(require_admin)):
    docs = db.query(Document).order_by(Document.uploaded_at.desc()).all()
    return [
        {"id": d.id, "filename": d.filename, "chunk_count": d.chunk_count, "uploaded_at": d.uploaded_at.isoformat()}
        for d in docs
    ]


@router.delete("/{doc_id}", status_code=204)
def delete_doc(
    doc_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    doc = db.query(Document).filter_by(id=doc_id).one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    from qdrant_client.models import Filter, FieldCondition, MatchValue

    get_qdrant_client().delete(
        collection_name="matcha_knowledge",
        points_selector=Filter(must=[FieldCondition(key="document_id", match=MatchValue(value=doc.id))]),
    )

    db.delete(doc)
    db.commit()

    log_admin_action(db, action="delete_doc", target=doc.filename, ip=request.client.host if request.client else "")
