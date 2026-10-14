from fastapi.testclient import TestClient
import logging
import json
from types import SimpleNamespace

from app.main import app
from app.services.agent_service import (
    AgentService,
    ClarityEvaluationError,
    DOCUMENTARY_JSON_INSTRUCTIONS,
    UNVERIFIED_DOCUMENTARY_ANSWER,
)
from app.services.sync_service import SyncService
from app.services.sync_service import InventoryConfigurationError

client = TestClient(app)

def test_home():
    r = client.get("/")
    assert r.status_code == 200
    assert "Archivo TIC" in r.text

def test_health():
    assert client.get("/api/health").status_code == 200


def test_production_health_does_not_require_drive(monkeypatch):
    import app.main as main_module

    production_settings = SimpleNamespace(
        app_env="production",
        openai_api_key="test-key",
        vector_store_id="vs_prod",
        sync_enabled=False,
        ask_enabled=False,
    )
    monkeypatch.setattr(main_module, "settings", production_settings)
    monkeypatch.setattr(SyncService, "load_inventory", staticmethod(lambda: {"documents": {"file_prod": {}}}))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["configured"] is True
    assert response.json()["sync_enabled"] is False

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


def test_sync_is_disabled_in_production_before_service_initialization(monkeypatch):
    import app.main as main_module

    production_settings = SimpleNamespace(
        sync_enabled=False,
        openai_api_key="",
        local_admin_key="",
    )
    monkeypatch.setattr(main_module, "settings", production_settings)
    monkeypatch.setattr(
        main_module,
        "SyncService",
        lambda: (_ for _ in ()).throw(AssertionError("SyncService no debe inicializarse")),
    )

    response = client.post("/api/sync")

    assert response.status_code == 404
    assert "no disponible" in response.json()["detail"]


def test_public_ask_is_disabled_without_openai_call(monkeypatch):
    import app.main as main_module

    production_settings = SimpleNamespace(
        ask_enabled=False,
        openai_api_key="",
    )
    monkeypatch.setattr(main_module, "settings", production_settings)
    monkeypatch.setattr(
        main_module,
        "AgentService",
        lambda: (_ for _ in ()).throw(AssertionError("AgentService no debe inicializarse")),
    )

    response = client.post("/api/ask", json={"question": "Pregunta vÃ¡lida"})

    assert response.status_code == 503
    assert "no disponibles" in response.json()["detail"]


def test_local_ask_remains_enabled_by_default(monkeypatch):
    import app.main as main_module

    calls = []
    local_settings = SimpleNamespace(ask_enabled=True, openai_api_key="test-key")
    monkeypatch.setattr(main_module, "settings", local_settings)

    class StubAgent:
        def __init__(self):
            calls.append("initialized")

        def ask(self, question, use_search):
            calls.append((question, use_search))
            return {"success": True, "answer": "ok", "sources": [], "clarification_request": False}

    monkeypatch.setattr(main_module, "AgentService", StubAgent)
    response = client.post("/api/ask", json={"question": "Pregunta vÃ¡lida", "use_search": False})

    assert response.status_code == 200
    assert calls == ["initialized", ("Pregunta vÃ¡lida", False)]


def test_ask_rejects_question_over_maximum_before_agent_initialization(monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(main_module, "settings", SimpleNamespace(ask_enabled=True, openai_api_key="test-key"))
    monkeypatch.setattr(
        main_module,
        "AgentService",
        lambda: (_ for _ in ()).throw(AssertionError("AgentService no debe inicializarse")),
    )

    response = client.post("/api/ask", json={"question": "x" * 3001})

    assert response.status_code == 422


def production_inventory():
    return json.dumps({
        "documents": [{
            "openai_file_id": "file_prod",
            "name": "produccion.pdf",
            "url": "https://drive.google.com/file/d/prod/view",
        }]
    })


def test_local_inventory_keeps_reading_manifest(monkeypatch):
    monkeypatch.setattr(SyncService, "load_manifest", staticmethod(fake_manifest))
    monkeypatch.setattr("app.services.sync_service.settings", SimpleNamespace(app_env="local"))

    inventory = SyncService.load_inventory()

    assert set(inventory["documents"]) == {"drive_1", "drive_2"}


def test_production_documents_use_inventory_without_manifest(monkeypatch):
    monkeypatch.setenv("DOCUMENT_INVENTORY_JSON", production_inventory())
    monkeypatch.setattr("app.services.sync_service.settings", SimpleNamespace(app_env="production"))
    monkeypatch.setattr(SyncService, "load_manifest", staticmethod(
        lambda: (_ for _ in ()).throw(AssertionError("No debe leer el manifiesto local"))
    ))

    response = client.get("/api/documents")

    assert response.status_code == 200
    assert response.json()["indexed"] == 1
    assert response.json()["documents"] == [{
        "name": "produccion.pdf",
        "url": "https://drive.google.com/file/d/prod/view",
    }]
    assert "file_prod" not in response.text


def test_production_inventory_rejects_duplicates_without_manifest_fallback(monkeypatch):
    monkeypatch.setenv("DOCUMENT_INVENTORY_JSON", json.dumps({
        "documents": [
            {"openai_file_id": "same", "name": "a.pdf", "url": "https://drive.google.com/file/d/a/view"},
            {"openai_file_id": "same", "name": "b.pdf", "url": "https://drive.google.com/file/d/b/view"},
        ]
    }))
    monkeypatch.setattr("app.services.sync_service.settings", SimpleNamespace(app_env="production"))

    response = client.get("/api/documents")

    assert response.status_code == 503
    assert "duplicados" in response.json()["detail"]


def test_production_inventory_resolves_rag_sources(monkeypatch):
    monkeypatch.setenv("DOCUMENT_INVENTORY_JSON", production_inventory())
    monkeypatch.setattr("app.services.sync_service.settings", SimpleNamespace(app_env="production"))
    service = AgentService()

    sources = service.sources_from_evidence(
        [{"id": "E1", "file_id": "file_prod"}],
        ["E1"],
        SyncService.load_inventory()["documents"],
    )

    assert sources == [{
        "name": "produccion.pdf",
        "url": "https://drive.google.com/file/d/prod/view",
    }]


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
