from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.agent.clients import get_openai_client, get_qdrant_client
from app.auth import log_admin_action, require_admin
from app.db.base import get_db
from app.db.models import Document
from app.ingestion import chunk_text, embed_and_upsert

router = APIRouter(prefix="/admin/docs")


@router.post("", status_code=201)
async def upload_doc(
    request: Request,
    file: UploadFile,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    raw = await file.read()
    text = raw.decode("utf-8", errors="ignore")
    chunks = chunk_text(text)

    embed_and_upsert(
        chunks=chunks,
        filename=file.filename,
        qdrant_client=get_qdrant_client(),
        openai_client=get_openai_client(),
    )

    doc = Document(filename=file.filename, chunk_count=len(chunks))
    db.add(doc)
    db.commit()
    db.refresh(doc)

    log_admin_action(db, action="upload_doc", target=file.filename, ip=request.client.host if request.client else "")

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
        points_selector=Filter(must=[FieldCondition(key="source", match=MatchValue(value=doc.filename))]),
    )

    db.delete(doc)
    db.commit()

    log_admin_action(db, action="delete_doc", target=doc.filename, ip=request.client.host if request.client else "")
