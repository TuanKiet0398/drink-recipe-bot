from io import BytesIO
from unittest.mock import MagicMock, patch

from app.db.models import AdminAuditLog, Document


def test_upload_doc_requires_auth(client):
    response = client.post("/admin/docs", files={"file": ("brew.txt", BytesIO(b"steep 80C"))})
    assert response.status_code == 401


def test_upload_doc_chunks_embeds_and_records_metadata(client, db_session):
    fake_qdrant = MagicMock()
    fake_openai = MagicMock()
    fake_openai.embeddings.create.return_value.data = [MagicMock(embedding=[0.1])]

    with patch("app.routers.admin_docs.get_qdrant_client", return_value=fake_qdrant), patch(
        "app.routers.admin_docs.get_openai_client", return_value=fake_openai
    ):
        response = client.post(
            "/admin/docs",
            files={"file": ("sencha_recipe.txt", BytesIO(b"Steep sencha at 70C for 60 seconds."))},
            auth=("admin", "admin"),
        )

    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "sencha_recipe.txt"
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

    fake_qdrant = MagicMock()
    with patch("app.routers.admin_docs.get_qdrant_client", return_value=fake_qdrant):
        response = client.delete(f"/admin/docs/{doc.id}", auth=("admin", "admin"))

    assert response.status_code == 204
    assert db_session.query(Document).count() == 0
    fake_qdrant.delete.assert_called_once()


def test_upload_doc_writes_audit_log(client, db_session):
    fake_qdrant = MagicMock()
    fake_openai = MagicMock()
    fake_openai.embeddings.create.return_value.data = [MagicMock(embedding=[0.1])]

    with patch("app.routers.admin_docs.get_qdrant_client", return_value=fake_qdrant), patch(
        "app.routers.admin_docs.get_openai_client", return_value=fake_openai
    ):
        client.post(
            "/admin/docs",
            files={"file": ("a.txt", BytesIO(b"content"))},
            auth=("admin", "admin"),
        )

    logs = db_session.query(AdminAuditLog).filter_by(action="upload_doc").all()
    assert len(logs) == 1
    assert logs[0].target == "a.txt"
