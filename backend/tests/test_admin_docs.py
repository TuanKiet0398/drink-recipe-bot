from io import BytesIO
from unittest.mock import MagicMock, patch

from app.db.models import AdminAuditLog, Document
from app.ingestion import Chunk


def test_upload_doc_requires_auth(client):
    response = client.post("/admin/docs", files={"file": ("brew.txt", BytesIO(b"steep 80C"))})
    assert response.status_code == 401


def test_upload_doc_chunks_embeds_and_records_metadata(client, db_session):
    fake_chunks = [Chunk(headline="H", summary="S", original_text="Steep sencha at 70C for 60 seconds.")]

    with patch("app.routers.admin_docs.chunk_document", return_value=fake_chunks) as mock_chunk, patch(
        "app.routers.admin_docs.embed_and_upsert"
    ) as mock_embed:
        response = client.post(
            "/admin/docs",
            files={"file": ("sencha_recipe.txt", BytesIO(b"Steep sencha at 70C for 60 seconds."))},
            auth=("admin", "admin"),
        )

    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "sencha_recipe.txt"
    assert body["chunk_count"] == 1
    assert db_session.query(Document).count() == 1
    mock_chunk.assert_called_once()
    mock_embed.assert_called_once()
    assert mock_embed.call_args.kwargs["chunks"] == fake_chunks
    assert mock_embed.call_args.kwargs["document_id"] == body["id"]


def test_upload_doc_rejects_pdf_extension(client, db_session):
    response = client.post(
        "/admin/docs",
        files={"file": ("brew.pdf", BytesIO(b"%PDF-1.4 fake pdf bytes"))},
        auth=("admin", "admin"),
    )
    assert response.status_code == 400
    assert "Only .txt and .md files" in response.json()["detail"]
    assert db_session.query(Document).count() == 0


def test_upload_doc_rejects_oversized_file(client, db_session):
    big_content = b"a" * (5 * 1024 * 1024 + 1)
    response = client.post(
        "/admin/docs",
        files={"file": ("big.txt", BytesIO(big_content))},
        auth=("admin", "admin"),
    )
    assert response.status_code == 413
    assert db_session.query(Document).count() == 0


def test_upload_doc_accepts_md_file(client, db_session):
    with patch("app.routers.admin_docs.chunk_document", return_value=[Chunk(headline="H", summary="S", original_text="# Matcha notes")]), patch(
        "app.routers.admin_docs.embed_and_upsert"
    ):
        response = client.post(
            "/admin/docs",
            files={"file": ("notes.md", BytesIO(b"# Matcha notes"))},
            auth=("admin", "admin"),
        )

    assert response.status_code == 201
    assert db_session.query(Document).count() == 1


def test_list_docs(client, db_session):
    db_session.add(Document(filename="a.txt", chunk_count=1))
    db_session.commit()
    response = client.get("/admin/docs", auth=("admin", "admin"))
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_delete_doc(client, db_session):
    doc = Document(filename="a.txt", chunk_count=1)
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    fake_collection = MagicMock()
    fake_chroma = MagicMock()
    fake_chroma.get_or_create_collection.return_value = fake_collection
    with patch("app.routers.admin_docs.get_chroma_client", return_value=fake_chroma):
        response = client.delete(f"/admin/docs/{doc.id}", auth=("admin", "admin"))

    assert response.status_code == 204
    assert db_session.query(Document).count() == 0
    fake_collection.delete.assert_called_once_with(where={"document_id": doc.id})


def test_delete_doc_with_duplicate_filename_only_deletes_its_own_document_id(client, db_session):
    from app.db.models import Document as DocumentModel

    doc1 = DocumentModel(filename="dup.txt", chunk_count=1)
    doc2 = DocumentModel(filename="dup.txt", chunk_count=1)
    db_session.add_all([doc1, doc2])
    db_session.commit()
    db_session.refresh(doc1)
    db_session.refresh(doc2)

    fake_collection = MagicMock()
    fake_chroma = MagicMock()
    fake_chroma.get_or_create_collection.return_value = fake_collection
    with patch("app.routers.admin_docs.get_chroma_client", return_value=fake_chroma):
        response = client.delete(f"/admin/docs/{doc1.id}", auth=("admin", "admin"))

    assert response.status_code == 204
    fake_collection.delete.assert_called_once_with(where={"document_id": doc1.id})
    assert db_session.query(DocumentModel).filter_by(id=doc2.id).count() == 1


def test_delete_doc_returns_404_when_missing(client, db_session):
    response = client.delete("/admin/docs/999", auth=("admin", "admin"))
    assert response.status_code == 404


def test_upload_doc_writes_audit_log(client, db_session):
    with patch("app.routers.admin_docs.chunk_document", return_value=[Chunk(headline="H", summary="S", original_text="content")]), patch(
        "app.routers.admin_docs.embed_and_upsert"
    ):
        client.post(
            "/admin/docs",
            files={"file": ("a.txt", BytesIO(b"content"))},
            auth=("admin", "admin"),
        )

    logs = db_session.query(AdminAuditLog).filter_by(action="upload_doc").all()
    assert len(logs) == 1
    assert logs[0].target == "a.txt"
