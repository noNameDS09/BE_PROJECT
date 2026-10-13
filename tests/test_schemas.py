import pytest
from pydantic import ValidationError

from loupe.core.schemas import Answer, Citation, Claim, Event, RunConfig


def test_config_hash_is_stable_and_sensitive_to_changes():
    a = RunConfig(arm="loupe", model="groq-llama-70b", retrieval={"top_k": 10, "embed": "bge"})
    b = RunConfig(arm="loupe", model="groq-llama-70b", retrieval={"embed": "bge", "top_k": 10})
    c = RunConfig(arm="loupe", model="groq-llama-70b", retrieval={"top_k": 5, "embed": "bge"})

    assert a.config_hash() == b.config_hash()
    assert a.config_hash() != c.config_hash()


def test_event_quality_score_is_bounded():
    with pytest.raises(ValidationError):
        Event(
            event_id="e1",
            company_id="AMD",
            event_type="auditor_change",
            label_source="8k_item",
            doc_id="d1",
            quote="...",
            quality_score=6,
        )


def test_answer_round_trips_through_json():
    answer = Answer(
        text="Revenue rose 14%.",
        claims=[Claim(text="Revenue rose 14%.", citations=[Citation(fact_id="f1")])],
    )
    assert Answer.model_validate_json(answer.model_dump_json()) == answer
