from fastapi.testclient import TestClient
import logging

from app.main import app
from app.services.agent_service import (
    AgentService,
    ClarityEvaluationError,
    DOCUMENTARY_JSON_INSTRUCTIONS,
    UNVERIFIED_DOCUMENTARY_ANSWER,
)
from app.services.sync_service import SyncService

client = TestClient(app)

def test_home():
    r = client.get("/")
    assert r.status_code == 200
    assert "Archivo TIC" in r.text

def test_health():
    assert client.get("/api/health").status_code == 200

def test_documents():
    r = client.get("/api/documents")
    assert r.status_code == 200
    assert isinstance(r.json()["documents"], list)

def test_question_validation():
    r = client.post("/api/ask", json={"question": "a"})
    assert r.status_code == 422

def test_sync_not_public():
    # FastAPI TestClient IP ficticia no loopback: bloqueado por diseño.
    r = client.post("/api/sync")
    assert r.status_code == 403


class FakeResponse:
    def __init__(self, output_text, output=None):
        self.output_text = output_text
        self.output = output or []


class FakeResponses:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeClient:
    def __init__(self, responses, search_results=None):
        self.responses = FakeResponses(responses)
        self.vector_stores = FakeVectorStores(search_results or [])


class FakeVectorStores:
    def __init__(self, search_results):
        self.search_results = search_results
        self.calls = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        return self.search_results


def fake_manifest():
    return {
        "vector_store_id": "vs_test",
        "documents": {
            "drive_1": {
                "name": "MentAlly.pdf",
                "url": "https://drive.google.com/file/d/drive_1/view",
                "openai_file_id": "file_1",
            },
            "drive_2": {
                "name": "imagen comercialsin impi.pdf",
                "url": "https://drive.google.com/file/d/drive_2/view",
                "openai_file_id": "file_2",
            }
        },
    }


def citation_output(file_id="file_1"):
    annotation = type("Annotation", (), {"type": "file_citation", "file_id": file_id})()
    content = type("Content", (), {"annotations": [annotation]})()
    return [type("OutputItem", (), {"content": [content]})()]


def file_search_output(file_id="file_2"):
    return [{
        "type": "file_search_call",
        "results": [{"file_id": file_id, "filename": "imagen comercialsin impi.pdf"}],
    }]


def vector_result(file_id="file_2", text="La clase 35 comprende publicidad, gestión y administración de negocios."):
    content = type("Content", (), {"text": text})()
    return type("VectorResult", (), {
        "file_id": file_id,
        "filename": "imagen comercialsin impi.pdf",
        "score": 0.91,
        "content": [content],
    })()


def service_with(monkeypatch, responses, search_results=None):
    monkeypatch.setattr(SyncService, "load_manifest", staticmethod(fake_manifest))
    return AgentService(client=FakeClient(responses, search_results))


def test_ambiguous_question_requests_clarification_without_file_search(monkeypatch):
    service = service_with(monkeypatch, [
        FakeResponse('{"clear": false, "clarification": "¿Sobre qué tema quieres conocer las ventajas?"}')
    ])

    result = service.ask("¿Cuáles son sus principales ventajas?")

    assert result["clarification_request"] is True
    assert result["sources"] == []
    assert "tema" in result["answer"]
    assert len(service.client.responses.calls) == 1
    assert "tools" not in service.client.responses.calls[0]
    assert service.client.vector_stores.calls == []


def test_documentary_contract_rejects_different_retrieved_entity():
    assert "referente principal" in DOCUMENTARY_JSON_INSTRUCTIONS
    assert "se refiere realmente a ese mismo referente" in DOCUMENTARY_JSON_INSTRUCTIONS
    assert "no supongas que dos nombres representan lo mismo" in DOCUMENTARY_JSON_INSTRUCTIONS
    assert "used_source_ids como lista vacía" in DOCUMENTARY_JSON_INSTRUCTIONS
    assert "no encontraste información documental suficiente" in DOCUMENTARY_JSON_INSTRUCTIONS


def test_documentary_contract_allows_explicit_equivalence():
    assert "equivalencia" in DOCUMENTARY_JSON_INSTRUCTIONS
    assert "abreviatura documentada" in DOCUMENTARY_JSON_INSTRUCTIONS
    assert "referencia contextual inequívoca" in DOCUMENTARY_JSON_INSTRUCTIONS


def test_clear_entity_question_uses_file_search(monkeypatch):
    service = service_with(
        monkeypatch,
        [
            FakeResponse('{"clear": true, "clarification": ""}'),
            FakeResponse('{"answer": "MentAlly ofrece apoyo emocional.", "used_source_ids": ["E1"], "insufficient_evidence": false}'),
        ],
        [vector_result("file_1", "MentAlly ofrece apoyo emocional a estudiantes.")],
    )

    result = service.ask("¿Cuáles son las ventajas de MentAlly?")

    assert result["clarification_request"] is False
    assert result["sources"] == [{"name": "MentAlly.pdf", "url": "https://drive.google.com/file/d/drive_1/view"}]
    assert service.client.vector_stores.calls[0]["vector_store_id"] == "vs_test"


def test_broad_but_clear_question_uses_file_search(monkeypatch):
    service = service_with(
        monkeypatch,
        [
            FakeResponse('{"clear": true, "clarification": ""}'),
            FakeResponse('{"answer": "Los documentos explican beneficios educativos.", "used_source_ids": ["E1"], "insufficient_evidence": false}'),
        ],
        [vector_result("file_1", "Los documentos explican beneficios educativos.")],
    )

    result = service.ask("¿Qué beneficios tiene la inteligencia artificial en educación?")

    assert result["clarification_request"] is False
    assert service.client.vector_stores.calls


def test_unknown_named_entity_is_not_rejected_by_evaluator(monkeypatch):
    service = service_with(
        monkeypatch,
        [
            FakeResponse('{"clear": true, "clarification": ""}'),
            FakeResponse('{"answer": "No encontré información suficiente en los documentos indexados.", "used_source_ids": [], "insufficient_evidence": true}'),
        ],
        [vector_result("file_2", "AWS y MentAlly son temas distintos.")],
    )

    result = service.ask("¿Qué ventajas tiene Xandoria Cloud?")

    assert result["clarification_request"] is False
    assert result["sources"] == []
    assert result["answer"] == UNVERIFIED_DOCUMENTARY_ANSWER


def test_clear_question_without_evidence_is_not_ambiguous(monkeypatch):
    service = service_with(
        monkeypatch,
        [
            FakeResponse('{"clear": true, "clarification": ""}'),
            FakeResponse('{"answer": "No encontré evidencia suficiente en los documentos indexados.", "used_source_ids": [], "insufficient_evidence": true}'),
        ],
        [],
    )

    result = service.ask("¿Qué dice el archivo sobre Kubernetes?")

    assert result == {
        "success": True,
        "answer": UNVERIFIED_DOCUMENTARY_ANSWER,
        "sources": [],
        "clarification_request": False,
    }


def test_sources_only_use_verifiable_annotations(monkeypatch):
    service = service_with(
        monkeypatch,
        [
            FakeResponse('{"clear": true, "clarification": ""}'),
            FakeResponse('{"answer": "Respuesta documental.", "used_source_ids": ["E1"], "insufficient_evidence": false}'),
        ],
        [vector_result("unknown_file", "Respuesta documental.")],
    )

    result = service.ask("¿Qué ventajas tiene MentAlly?")

    assert result["sources"] == []


def test_file_search_results_are_not_verifiable_sources_without_citations(monkeypatch):
    service = service_with(
        monkeypatch,
        [
            FakeResponse('{"clear": true, "clarification": ""}'),
            FakeResponse('{"answer": "La clase 35 se relaciona con publicidad y gestión de negocios.", "used_source_ids": [], "insufficient_evidence": false}'),
        ],
        [vector_result()],
    )

    result = service.ask("¿De qué trata la clase 35 de fonética del IMPI?")

    assert result["sources"] == []
    assert result["answer"] == UNVERIFIED_DOCUMENTARY_ANSWER


def test_valid_file_citation_resolves_to_drive_link(monkeypatch):
    service = service_with(
        monkeypatch,
        [
            FakeResponse('{"clear": true, "clarification": ""}'),
            FakeResponse('{"answer": "La clase 35 se relaciona con publicidad y gestión de negocios.", "used_source_ids": ["E1"], "insufficient_evidence": false}'),
        ],
        [vector_result("file_2")],
    )

    result = service.ask("¿De qué trata la clase 35 de fonética del IMPI?")

    assert result["sources"] == [{
        "name": "imagen comercialsin impi.pdf",
        "url": "https://drive.google.com/file/d/drive_2/view",
    }]


def test_clear_no_evidence_answer_ignores_retrieved_but_uncited_files(monkeypatch):
    service = service_with(
        monkeypatch,
        [
            FakeResponse('{"clear": true, "clarification": ""}'),
            FakeResponse('{"answer": "No encontré información suficiente en los documentos indexados.", "used_source_ids": [], "insufficient_evidence": true}'),
        ],
        [vector_result("file_1", "AWS general."), vector_result("file_2", "MentAlly general.")],
    )

    result = service.ask("¿Cuáles son las principales ventajas de Xandoria Cloud?")

    assert result["sources"] == []
    assert result["answer"] == UNVERIFIED_DOCUMENTARY_ANSWER


def test_source_diagnostics_logs_only_counts(monkeypatch, caplog):
    service = service_with(
        monkeypatch,
        [
            FakeResponse('{"clear": true, "clarification": ""}'),
            FakeResponse('{"answer": "Respuesta documental.", "used_source_ids": ["E1"], "insufficient_evidence": false}'),
        ],
        [vector_result("file_2", "Respuesta documental.")],
    )

    with caplog.at_level(logging.INFO, logger="app.services.agent_service"):
        result = service.ask("¿De qué trata la clase 35 de fonética del IMPI?")

    assert result["sources"] == [{
        "name": "imagen comercialsin impi.pdf",
        "url": "https://drive.google.com/file/d/drive_2/view",
    }]
    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "fragmentos=1" in message
        and "fragmentos_usados=1" in message
        and "fuentes_resueltas=1" in message
        for message in messages
    )
    assert all("Respuesta documental." not in message for message in messages)


def test_clarity_evaluation_requires_real_boolean(monkeypatch):
    service = service_with(monkeypatch, [
        FakeResponse('{"clear": "false", "clarification": "¿Sobre qué tema?"}')
    ])

    try:
        service.ask("¿Cuáles son sus ventajas?")
    except ClarityEvaluationError as exc:
        assert "No se pudo evaluar" in str(exc)
    else:
        raise AssertionError("Se esperaba ClarityEvaluationError")
    assert len(service.client.responses.calls) == 1


def test_clarity_evaluation_error_is_not_ambiguity(monkeypatch):
    service = service_with(monkeypatch, [RuntimeError("API down")])

    try:
        service.ask("¿Qué ventajas tiene MentAlly?")
    except ClarityEvaluationError as exc:
        assert "No se pudo evaluar" in str(exc)
    else:
        raise AssertionError("Se esperaba ClarityEvaluationError")
    assert len(service.client.responses.calls) == 1
