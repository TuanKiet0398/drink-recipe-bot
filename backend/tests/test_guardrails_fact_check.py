from unittest.mock import MagicMock, patch

from nemoguardrails.rails.llm.options import GenerationResponse

from app.agent.nodes import check_facts
from app.agent.state import AgentState
from app.guardrails.fact_check import check_grounded


def test_check_grounded_skips_the_rail_when_there_are_no_relevant_chunks():
    with patch("app.guardrails.fact_check._rails") as mock_rails:
        result = check_grounded("what matcha do you have?", "Try our ceremonial matcha!", [])

    mock_rails.assert_not_called()
    assert result == "Try our ceremonial matcha!"


def test_check_grounded_skips_the_rail_when_the_reply_is_empty():
    with patch("app.guardrails.fact_check._rails") as mock_rails:
        result = check_grounded("what matcha do you have?", "", ["Ceremonial matcha, $10."])

    mock_rails.assert_not_called()
    assert result == ""


def test_check_grounded_passes_through_the_reply_when_the_rail_allows_it():
    fake_rails = MagicMock()
    fake_rails.generate.return_value = GenerationResponse(response=[{"role": "assistant", "content": ""}])
    with patch("app.guardrails.fact_check._rails", return_value=fake_rails):
        result = check_grounded(
            "what matcha do you have?",
            "We have ceremonial grade matcha.",
            ["Ceremonial grade matcha is on the menu."],
        )

    assert result == "We have ceremonial grade matcha."
    call_kwargs = fake_rails.generate.call_args.kwargs
    assert call_kwargs["options"] == {"rails": {"dialog": False}}
    context_message = call_kwargs["messages"][0]
    assert context_message["role"] == "context"
    assert context_message["content"]["check_facts"] is True
    assert "Ceremonial grade matcha is on the menu." in context_message["content"]["relevant_chunks"]


def test_check_grounded_substitutes_the_rails_refusal_when_it_blocks_the_reply():
    fake_rails = MagicMock()
    fake_rails.generate.return_value = GenerationResponse(
        response=[{"role": "assistant", "content": "Sorry, I'm not sure about that."}]
    )
    with patch("app.guardrails.fact_check._rails", return_value=fake_rails):
        result = check_grounded(
            "do you have bubble tea?",
            "Yes, we have the best bubble tea in town!",
            ["Ceremonial grade matcha is on the menu."],
        )

    assert result == "Sorry, I'm not sure about that."


def test_check_grounded_fails_open_when_the_rail_errors():
    fake_rails = MagicMock()
    fake_rails.generate.side_effect = RuntimeError("guardrails service unavailable")
    with patch("app.guardrails.fact_check._rails", return_value=fake_rails):
        result = check_grounded(
            "what matcha do you have?",
            "We have ceremonial grade matcha.",
            ["Ceremonial grade matcha is on the menu."],
        )

    assert result == "We have ceremonial grade matcha."


def test_check_facts_node_overwrites_state_reply_with_the_checked_result():
    state = AgentState(
        user_id=1,
        chat_id="1",
        incoming_text="do you have bubble tea?",
        reply="Yes, we have the best bubble tea in town!",
        retrieved_chunks=["Ceremonial grade matcha is on the menu."],
    )
    with patch("app.agent.nodes.check_grounded", return_value="Sorry, I'm not sure about that.") as mock_check:
        result = check_facts(state)

    mock_check.assert_called_once_with(
        "do you have bubble tea?",
        "Yes, we have the best bubble tea in town!",
        ["Ceremonial grade matcha is on the menu."],
    )
    assert result.reply == "Sorry, I'm not sure about that."
