"""Training script checks. These rows exist only inside the test."""

from pathlib import Path

import pandas as pd
import pytest

from backend.ml.train_baselines import DatasetError, load_messages, train_baselines


def _write_csv(path: Path, rows: list[tuple[str, str]]) -> None:
    frame = pd.DataFrame(
        [
            {
                "text": text,
                "label": label,
                "source": "unit-test",
                "is_synthetic": True,
            }
            for text, label in rows
        ]
    )
    frame.to_csv(path, index=False)


def test_missing_dataset_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(DatasetError, match="does not invent messages"):
        load_messages(tmp_path / "messages.csv")


def test_train_baselines_writes_table_and_artifacts(tmp_path: Path) -> None:
    rows: list[tuple[str, str]] = []
    for index in range(12):
        rows.append((f"official campus internship program week {index}", "legitimate"))
        rows.append((f"please verify the recruiter profile {index}", "suspicious"))
        rows.append((f"pay the registration fee today offer letter {index}", "scam"))

    data_path = tmp_path / "messages.csv"
    models_dir = tmp_path / "models"
    _write_csv(data_path, rows)

    table = train_baselines(data_path, models_dir)

    assert list(table["model"]) == ["tfidf_logreg", "random_forest", "xgboost"]
    assert set(table.columns) == {
        "model",
        "accuracy",
        "f1_macro",
        "scam_precision",
        "scam_recall",
        "dataset_version",
        "seed",
    }
    assert table["dataset_version"].str.startswith("sha256:").all()
    assert set(table["seed"]) == {42}
    for column in ("accuracy", "f1_macro", "scam_precision", "scam_recall"):
        assert table[column].between(0, 1).all()
    for name in ("tfidf_logreg", "random_forest", "xgboost"):
        assert (models_dir / f"{name}.joblib").is_file()
    assert (models_dir / "comparison.csv").is_file()
    assert (models_dir / "run_settings.json").is_file()
