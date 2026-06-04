"""
Unit tests for the OpenAI→Anthropic translation in the Claude provider.
Pure functions — no API calls.
"""
import json
from agent.llm.claude_provider import _split_system, _to_anthropic_messages, _to_anthropic_tools


def test_split_system_extracts_system_prompt():
    messages = [
        {"role": "system", "content": "You are an analyst."},
        {"role": "user", "content": "hi"},
    ]
    system, rest = _split_system(messages)
    assert system == "You are an analyst."
    assert rest == [{"role": "user", "content": "hi"}]


def test_plain_user_assistant_passthrough():
    msgs = _to_anthropic_messages([
        {"role": "user", "content": "q"},
        {"role": "assistant", "content": "a"},
    ])
    assert msgs == [
        {"role": "user", "content": "q"},
        {"role": "assistant", "content": "a"},
    ]


def test_assistant_tool_calls_become_tool_use_blocks():
    msgs = _to_anthropic_messages([
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "t1", "type": "function",
             "function": {"name": "execute_query", "arguments": '{"sql": "SELECT 1"}'}},
        ]},
    ])
    assert msgs[0]["role"] == "assistant"
    block = msgs[0]["content"][0]
    assert block == {"type": "tool_use", "id": "t1", "name": "execute_query", "input": {"sql": "SELECT 1"}}


def test_tool_results_merge_into_one_user_message():
    # An assistant turn with TWO tool calls, followed by TWO tool results.
    msgs = _to_anthropic_messages([
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "a", "type": "function", "function": {"name": "f", "arguments": "{}"}},
            {"id": "b", "type": "function", "function": {"name": "g", "arguments": "{}"}},
        ]},
        {"role": "tool", "tool_call_id": "a", "content": "result-a"},
        {"role": "tool", "tool_call_id": "b", "content": "result-b"},
    ])
    # assistant message + a single merged user message with both tool_result blocks
    assert len(msgs) == 2
    assert msgs[1]["role"] == "user"
    results = msgs[1]["content"]
    assert [r["tool_use_id"] for r in results] == ["a", "b"]
    assert all(r["type"] == "tool_result" for r in results)


def test_tools_translated_to_anthropic_schema():
    tools = [{
        "type": "function",
        "function": {
            "name": "get_schema",
            "description": "desc",
            "parameters": {"type": "object", "properties": {"x": {"type": "string"}}},
        },
    }]
    out = _to_anthropic_tools(tools)
    assert out[0]["name"] == "get_schema"
    assert out[0]["description"] == "desc"
    assert out[0]["input_schema"]["properties"]["x"]["type"] == "string"
