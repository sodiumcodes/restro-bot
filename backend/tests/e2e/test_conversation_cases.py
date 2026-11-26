def test_model_fallback_records_log_row(monkeypatch, db_session):
    from app.llm import llm_router
    from app.database import connection
    from tests.e2e.conftest import TestSession
    from app.database.models.llm_log import LLMFallbackLog
    from sqlalchemy import select

    monkeypatch.setattr(connection, "SessionLocal", TestSession)

    class FakeModel:
        def __init__(self, name):
            self.name = name

        def invoke(self, *args, **kwargs):
            if self.name == "primary":
                raise Exception("429 Rate limit exceeded")
            return "Fallback reply"

    monkeypatch.setattr(
        llm_router,
        "create_llm",
        lambda model_config, **kw: FakeModel(model_config["model"])
    )

    router = llm_router.LLMRouter(
        model_configs=[
            {"provider": "groq", "model": "primary", "api_key_env": "K1"},
            {"provider": "openrouter", "model": "secondary", "api_key_env": "K2"},
        ]
    )

    reply = router.invoke("hello")

    assert reply == "Fallback reply"

    with TestSession() as session:
        log = session.scalar(
            select(LLMFallbackLog)
            .where(LLMFallbackLog.from_model == "primary")
            .order_by(LLMFallbackLog.id.desc())
        )

        assert log is not None
        assert log.to_model == "secondary"