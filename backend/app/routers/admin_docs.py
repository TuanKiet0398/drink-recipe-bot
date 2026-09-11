import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.agent.clients import (
    get_chat_client,
    get_chat_model,
    get_chroma_client,
    get_embedding_client,
    get_or_create_collection,
)
from app.auth import log_admin_action, require_admin
from app.db.base import get_db
from app.db.models import Document
from app.ingestion import chunk_document, embed_and_upsert

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
    # chunk_document and embed_and_upsert make blocking OpenAI/Chroma calls;
    # run them off the event loop thread so a large upload's chunking time
    # doesn't stall every other request the single uvicorn process is
    # serving (health checks, other admin pages, the chat webhook).
    chunks = await asyncio.to_thread(
        chunk_document,
        text,
        filename,
        chat_client=get_chat_client(db),
        chat_model=get_chat_model(db),
        db=db,
    )

    doc = Document(filename=filename, chunk_count=len(chunks))
    db.add(doc)
    db.commit()
    db.refresh(doc)

    await asyncio.to_thread(
        embed_and_upsert,
        chunks=chunks,
        filename=filename,
        document_id=doc.id,
        chroma_client=get_chroma_client(),
        embedding_client=get_embedding_client(),
    )

    log_admin_action(
        db, action="upload_doc", target=filename, ip=request.client.host if request.client else ""
    )

    return {"id": doc.id, "filename": doc.filename, "chunk_count": doc.chunk_count}


@router.get("")
def list_docs(db: Session = Depends(get_db), admin_user: str = Depends(require_admin)):
    docs = db.query(Document).order_by(Document.uploaded_at.desc()).all()
    return [
        {
            "id": d.id,
            "filename": d.filename,
            "chunk_count": d.chunk_count,
            "uploaded_at": d.uploaded_at.isoformat(),
        }
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

    collection = get_or_create_collection(get_chroma_client(), "matcha_knowledge")
    collection.delete(where={"document_id": doc.id})

    db.delete(doc)
    db.commit()

    log_admin_action(
        db, action="delete_doc", target=doc.filename, ip=request.client.host if request.client else ""
    )
