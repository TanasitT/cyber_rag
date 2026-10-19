import importlib

import pytest

from scripts import generator
from scripts.chunking import Chunk
from scripts.generator import REFUSAL, GroundedResponse, generate_grounded_answer

RETRIEVED = [
    (Chunk("dataset/a.pdf", f"dataset/a.pdf::page_{i}", f"text {i}", i), 1.0 / i)
    for i in (1, 2, 3)
]


def fake_model(monkeypatch, response):
    monkeypatch.setattr(generator, "_ask_model", lambda question, chunks: response)


def test_import_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    importlib.reload(generator)


def test_only_cited_pages_are_returned(monkeypatch):
    fake_model(monkeypatch, GroundedResponse(answer="An answer.", source_ids=[2, 2, 9, 0]))
    ans = generate_grounded_answer("q", RETRIEVED)
    assert ans.citations == ["dataset/a.pdf#page_2"]
    assert ans.used_chunks == ["dataset/a.pdf::page_2"]


def test_no_source_ids_falls_back_to_all_retrieved(monkeypatch):
    fake_model(monkeypatch, GroundedResponse(answer="An answer.", source_ids=[]))
    assert len(generate_grounded_answer("q", RETRIEVED).citations) == 3


@pytest.mark.parametrize("text", [
    REFUSAL,
    "'Insufficient information in dataset.'",
    "insufficient information in dataset",
    "  Insufficient information in dataset.  \n",
])
def test_refusal_variants(monkeypatch, text):
    fake_model(monkeypatch, GroundedResponse(answer=text, source_ids=[1]))
    ans = generate_grounded_answer("q", RETRIEVED)
    assert ans.answer == REFUSAL and ans.citations == [] and ans.used_chunks == []


def test_model_declines(monkeypatch):
    fake_model(monkeypatch, None)
    assert generate_grounded_answer("q", RETRIEVED).answer == REFUSAL


def test_nothing_retrieved_skips_the_model(monkeypatch):
    def fail(*args):
        raise AssertionError("model should not be called")

    monkeypatch.setattr(generator, "_ask_model", fail)
    assert generate_grounded_answer("q", []).answer == REFUSAL
