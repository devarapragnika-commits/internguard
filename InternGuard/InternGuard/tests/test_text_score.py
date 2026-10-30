"""Explainable text score and the analyze route."""

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from backend.routes.analyze import AnalyzeTextRequest, analyze_text
from backend.services.text_score import score_text

FEE_MESSAGE = "Congratulations. Pay a registration fee of 2500 today to receive your offer letter."
POLITE_FEE = "We are pleased to offer the internship. Kindly pay the joining fee to confirm your seat."
CLEAN_MESSAGE = "Our campus internship is unpaid. Apply on the company careers page. There is no fee."


def test_same_text_returns_the_same_score() -> None:
    assert score_text(FEE_MESSAGE) == score_text(FEE_MESSAGE)


def test_fee_request_raises_financial_risk_even_when_polite() -> None:
    result = score_text(POLITE_FEE)
    assert result["slices"]["financial"] == 25
    assert result["slices"]["company"] == 0
    assert result["reasons"]
    assert result["score"] >= 40


def test_clean_offer_stays_low_and_company_slice_is_zero() -> None:
    result = score_text(CLEAN_MESSAGE)
    assert result["band"] == "low"
    assert result["slices"]["company"] == 0
    assert result["slices"]["financial"] == 0


def test_analyze_route_rejects_blank_text() -> None:
    with pytest.raises(ValidationError):
        AnalyzeTextRequest(text="")
    with pytest.raises(HTTPException) as caught:
        analyze_text(AnalyzeTextRequest(text="   "))
    assert caught.value.status_code == 422


def test_analyze_route_returns_scorer_result() -> None:
    response = analyze_text(AnalyzeTextRequest(text=FEE_MESSAGE))
    assert response == score_text(FEE_MESSAGE)
    assert "score" in response
    assert "recommendation" in response
