import asyncio
from types import SimpleNamespace
from fastapi import FastAPI
from app import main

def test_root_endpoint():
    # root() is an async function, so asyncio.run() is needed to execute it
    result = asyncio.run(main.root())

    # The test fails unless the endpoint returns exactly this message
    assert result == {"message": "Welcome to Cafe Chatbot API"}


def test_lifespan_initializes_and_closes_resources(monkeypatch):
    # Records what happens, and in what order, so we can check it at the end
    events = []

    # Stand-in objects. We don't need real ones, only something to compare against.
    fake_llm = object()
    fake_graph = object()

    # A fake retriever: `retrieve` returns nothing, `close` logs that it was called
    fake_retriever = SimpleNamespace(
        retrieve=lambda **kwargs: [],
        close=lambda: events.append("retriever_closed"),
    )

    def fake_build_graph(llm, retrieval_fn):
        # Log whether build_graph received the right llm and retrieval function
        events.append(("graph_built", llm is fake_llm, retrieval_fn is fake_retriever.retrieve))
        return fake_graph

    # Swap the real functions/classes in main.py for our fakes (undone after the test)
    monkeypatch.setattr(main, "get_llm", lambda temperature: fake_llm)
    monkeypatch.setattr(main, "MenuRetriever", lambda: fake_retriever)
    monkeypatch.setattr(main, "build_graph", fake_build_graph)

    async def run_lifespan():
        app = FastAPI()

        # Entering the block runs the startup code; leaving it runs the shutdown code
        async with main.lifespan(app):
            # While the app is "running", all three resources should be stored on app.state
            assert app.state.llm is fake_llm
            assert app.state.menu_retriever is fake_retriever
            assert app.state.graph is fake_graph

    asyncio.run(run_lifespan())

    # The graph was built correctly at startup, then the retriever was closed at shutdown
    assert events == [("graph_built", True, True), "retriever_closed"]