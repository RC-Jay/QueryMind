from agent.orchestrator import AgentOrchestrator
from agent.llm.base import LLMResponse, ToolCall
from db.analytics import BusinessConfig
from tests.conftest import FakeConn, FakePool, FakeLLMProvider


def _config() -> BusinessConfig:
    # JSON columns → store raw Python structures, not json.dumps strings.
    return BusinessConfig(
        id=1,
        business_name="Test Co",
        business_description="A test business.",
        db_url_encrypted="x",
        domain_context="Some domain context.",
        business_rules=[{"rule": "Amounts in paise."}],
        table_descriptions={"order_order": "orders"},
        kpi_definitions=[{"name": "GMV", "sql": "SELECT 1", "format": "currency", "icon": "rupee"}],
        starter_questions=["How are we doing?"],
        explain_cost_threshold=50000,
    )


async def test_orchestrator_runs_tool_then_streams_final_text():
    # Script: round 1 calls the KPI tool, round 2 stops → stream final text.
    responses = [
        LLMResponse(finish_reason="tool_calls",
                    tool_calls=[ToolCall(id="c1", name="get_kpi_snapshot", arguments="{}")]),
        LLMResponse(finish_reason="stop"),
    ]
    llm = FakeLLMProvider(responses, stream_text="We are doing great")
    pool = FakePool(FakeConn(fetchval_value=500000))

    orch = AgentOrchestrator.build(_config(), llm, pool)

    events = []
    async def capture(event):
        events.append(event)

    final = await orch.run(history=[], user_message="How are we doing?", send_event=capture)

    kinds = [e["event"] for e in events]
    assert "metrics" in kinds          # KPI tool emitted its rich output
    assert "text_delta" in kinds       # final answer streamed
    assert kinds[-1] == "done"         # stream terminated correctly
    assert "great" in final
    assert llm.complete_calls == 2     # one tool round + one stop round


async def test_orchestrator_no_tools_just_answers():
    responses = [LLMResponse(finish_reason="stop")]
    llm = FakeLLMProvider(responses, stream_text="Direct answer here")
    pool = FakePool(FakeConn())

    orch = AgentOrchestrator.build(_config(), llm, pool)

    events = []
    async def capture(event):
        events.append(event)

    final = await orch.run(history=[], user_message="hi", send_event=capture)
    assert "Direct" in final
    assert [e["event"] for e in events if e["event"] == "metrics"] == []  # no tools called
    assert events[-1]["event"] == "done"


async def test_orchestrator_passes_system_prompt_and_history():
    llm = FakeLLMProvider([LLMResponse(finish_reason="stop")], stream_text="ok")
    pool = FakePool(FakeConn())
    orch = AgentOrchestrator.build(_config(), llm, pool)

    history = [{"role": "user", "content": "earlier question"}]
    await orch.run(history=history, user_message="new question", send_event=lambda e: _async_noop())

    sent = llm.seen_messages[0]
    assert sent[0]["role"] == "system"
    assert "Test Co" in sent[0]["content"]        # prompt built from config
    assert sent[1] == {"role": "user", "content": "earlier question"}
    assert sent[-1] == {"role": "user", "content": "new question"}


async def _async_noop():
    return None
