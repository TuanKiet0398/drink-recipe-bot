import json
from unittest.mock import MagicMock, patch

from chromadb import PersistentClient

from app.agent.clients import get_or_create_collection
from app.ingestion import Chunk, chunk_document, chunk_text, embed_and_upsert, split_into_pieces


def test_chunk_text_splits_into_word_count_windows():
    text = " ".join(f"word{i}" for i in range(1200))
    chunks = chunk_text(text, chunk_size=500)
    assert len(chunks) == 3
    assert chunks[0].split()[0] == "word0"


def test_chunk_text_returns_whole_text_when_shorter_than_chunk_size():
    assert chunk_text("just a few words") == ["just a few words"]


def test_split_into_pieces_returns_whole_text_as_one_piece_when_short():
    text = "Paragraph one.\n\nParagraph two."
    assert split_into_pieces(text, max_chars=1000) == [text]


def test_split_into_pieces_splits_on_paragraph_boundaries_within_char_budget():
    paragraphs = [f"Paragraph {i}. " + ("x" * 40) for i in range(10)]
    text = "\n\n".join(paragraphs)

    pieces = split_into_pieces(text, max_chars=120)

    assert len(pieces) > 1
    assert "".join(pieces).replace("\n\n", "") == text.replace("\n\n", "")
    for piece in pieces:
        assert len(piece) <= 120 or "\n\n" not in piece


def test_split_into_pieces_keeps_an_oversized_single_paragraph_whole():
    huge_paragraph = "x" * 500
    text = f"short one\n\n{huge_paragraph}\n\nshort two"

    pieces = split_into_pieces(text, max_chars=100)

    assert huge_paragraph in pieces


def test_chunk_document_parses_bilingual_llm_response_into_chunks(db_session):
    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps(
                    {
                        "chunks": [
                            {
                                "headline": "Matcha Latte / Trà Sữa Matcha",
                                "summary": "How to make a matcha latte. / Cách pha trà sữa matcha.",
                                "original_text": "Whisk 2g matcha with steamed milk.",
                            }
                        ]
                    }
                )
            )
        )
    ]
    fake_openai.chat.completions.create.return_value.usage = None

    chunks = chunk_document(
        "Whisk 2g matcha with steamed milk.",
        "matcha-latte.txt",
        chat_client=fake_openai,
        chat_model="gpt-4o-mini",
        db=db_session,
    )

    assert len(chunks) == 1
    assert chunks[0].original_text == "Whisk 2g matcha with steamed milk."
    assert "Trà Sữa" in chunks[0].headline
    fake_openai.chat.completions.create.assert_called_once()
    assert fake_openai.chat.completions.create.call_args.kwargs["response_format"] == {"type": "json_object"}


def test_chunk_document_prompt_asks_for_bilingual_headline_and_summary(db_session):
    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps({"chunks": [{"headline": "H", "summary": "S", "original_text": "T"}]})
            )
        )
    ]
    fake_openai.chat.completions.create.return_value.usage = None

    chunk_document("T", "doc.txt", chat_client=fake_openai, chat_model="gpt-4o-mini", db=db_session)

    prompt = fake_openai.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    assert "Vietnamese" in prompt
    assert "English" in prompt


def test_chunk_document_calls_llm_once_per_piece_for_a_long_document(db_session):
    paragraphs = [f"Paragraph {i}. " + ("x" * 40) for i in range(10)]
    long_text = "\n\n".join(paragraphs)

    fake_openai = MagicMock()

    def fake_create(*, messages, **kwargs):
        piece_text = messages[0]["content"]
        return MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content=json.dumps(
                            {"chunks": [{"headline": "H", "summary": "S", "original_text": piece_text}]}
                        )
                    )
                )
            ],
            usage=None,
        )

    fake_openai.chat.completions.create.side_effect = fake_create

    chunks = chunk_document(
        long_text,
        "long-doc.txt",
        chat_client=fake_openai,
        chat_model="gpt-4o-mini",
        db=db_session,
        max_chars=120,
    )

    assert fake_openai.chat.completions.create.call_count > 1
    assert len(chunks) == fake_openai.chat.completions.create.call_count


def test_chunk_document_falls_back_to_naive_chunking_when_llm_fails(db_session):
    fake_openai = MagicMock()
    fake_openai.chat.completions.create.side_effect = RuntimeError("provider down")

    with patch("app.retry.time.sleep"):
        chunks = chunk_document(
            "word " * 10, "doc.txt", chat_client=fake_openai, chat_model="gpt-4o-mini", db=db_session
        )

    assert len(chunks) == 1
    assert chunks[0].original_text.startswith("word")
    assert chunks[0].summary == ""


def test_chunk_document_falls_back_when_llm_response_is_malformed_json(db_session):
    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="not valid json"))
    ]
    fake_openai.chat.completions.create.return_value.usage = None

    chunks = chunk_document(
        "some document text", "doc.txt", chat_client=fake_openai, chat_model="gpt-4o-mini", db=db_session
    )

    assert len(chunks) == 1
    assert chunks[0].original_text == "some document text"


def test_embed_and_upsert_writes_chunk_text_and_metadata_to_chroma():
    fake_openai = MagicMock()
    fake_openai.embeddings.create.return_value.data = [MagicMock(embedding=[0.1, 0.2])]
    fake_collection = MagicMock()
    fake_chroma = MagicMock()
    fake_chroma.get_or_create_collection.return_value = fake_collection

    chunk = Chunk(headline="H", summary="S", original_text="T")
    embed_and_upsert(
        [chunk], filename="a.txt", document_id=42, chroma_client=fake_chroma, embedding_client=fake_openai
    )

    fake_collection.upsert.assert_called_once()
    kwargs = fake_collection.upsert.call_args.kwargs
    assert kwargs["documents"] == ["H\n\nS\n\nT"]
    assert kwargs["metadatas"] == [{"filename": "a.txt", "document_id": 42}]
    assert len(kwargs["ids"]) == 1


def test_embed_and_upsert_round_trips_through_real_chroma(tmp_path):
    # One non-mocked test against a real (local, file-backed) Chroma
    # instance, so a Chroma API mistake (wrong kwarg name, wrong return
    # shape) fails here instead of only in fully-mocked unit tests.
    fake_openai = MagicMock()
    fake_openai.embeddings.create.return_value.data = [MagicMock(embedding=[1.0, 0.0])]
    real_chroma = PersistentClient(path=str(tmp_path))

    chunk = Chunk(headline="Matcha Latte", summary="A latte.", original_text="Whisk matcha with milk.")
    embed_and_upsert(
        [chunk], filename="matcha.txt", document_id=1, chroma_client=real_chroma, embedding_client=fake_openai
    )

    collection = get_or_create_collection(real_chroma, "matcha_knowledge")
    result = collection.query(query_embeddings=[[1.0, 0.0]], n_results=1)
    assert "Whisk matcha with milk." in result["documents"][0][0]
    assert result["metadatas"][0][0]["document_id"] == 1
