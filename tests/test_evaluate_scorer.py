"""Evaluation and demo artifacts can be regenerated from the repo."""

from pathlib import Path

import pandas as pd

from backend.ml.evaluate_scorer import evaluate_scorer
from backend.ml.run_demo import run_demo
from backend.ml.train_baselines import load_messages
from tests.test_train_baselines import _write_csv


def test_evaluate_scorer_writes_rubric_and_model_rows(tmp_path: Path) -> None:
    rows: list[tuple[str, str]] = []
    for index in range(12):
        rows.append((f"official campus internship program week {index}", "legitimate"))
        rows.append((f"please verify the recruiter profile {index}", "suspicious"))
        rows.append((f"pay the registration fee today offer letter {index}", "scam"))
    data_path = tmp_path / "messages.csv"
    models_dir = tmp_path / "models"
    _write_csv(data_path, rows)

    table = evaluate_scorer(data_path, models_dir)

    assert list(table["method"]) == ["tfidf_logreg", "random_forest", "xgboost", "rubric"]
    assert "legitimate_false_positive_rate" in table.columns
    assert (models_dir / "evaluation.csv").is_file()
    saved = pd.read_csv(models_dir / "evaluation.csv")
    assert list(saved["method"]) == list(table["method"])
    assert saved["dataset_version"].str.startswith("sha256:").all()


def test_messages_csv_has_more_than_five_suspicious_rows() -> None:
    frame = load_messages(Path("data/messages.csv"))
    assert int((frame["label"] == "suspicious").sum()) >= 15
    assert set(frame["source"].unique()) <= {"hand-written", "job_contract_scam_dataset"}


def test_demo_writes_expected_bands() -> None:
    payload = run_demo()
    expected = {
        item["id"]: item["channels"]["text"]["band"] for item in payload["results"]
    }
    assert expected["legitimate"] == "low"
    assert expected["obvious_scam"] == "high"
    assert expected["subtle"] in {"medium", "high"}
    for item in payload["results"]:
        assert item["channels"]["link"]["band"] == item["channels"]["text"]["band"]
        assert "band" in item["channels"]["email"]
