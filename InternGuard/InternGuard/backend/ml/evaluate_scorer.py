"""Compare the live rubric with the three saved baseline models.

The product score is the rubric in ``score_message``, not a model
probability. This command uses the same stratified split as
``train_baselines`` (seed 42, test size 0.2) and writes
``models/evaluation.csv``.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from backend.ml.train_baselines import (
    DEFAULT_DATA_PATH,
    DEFAULT_MODELS_DIR,
    SEED,
    TEST_SIZE,
    DatasetError,
    build_models,
    dataset_version,
    evaluate,
    load_messages,
)
from backend.services import url_features
from backend.services.risk import score_message

BAND_TO_LABEL = {"low": "legitimate", "medium": "suspicious", "high": "scam"}


def _rubric_label(text: str) -> str:
    return BAND_TO_LABEL[score_message(text)["band"]]


def _rate(y_true, y_pred, truth_index: int, pred_index: int) -> float:
    selected = 0
    hits = 0
    for truth, pred in zip(y_true, y_pred, strict=True):
        if truth != truth_index:
            continue
        selected += 1
        if pred == pred_index:
            hits += 1
    if selected == 0:
        return 0.0
    return hits / selected


def _false_positive_rate(y_true, y_pred, legit_index: int, scam_index: int) -> float:
    return _rate(y_true, y_pred, legit_index, scam_index)


def evaluate_scorer(data_path: Path, models_dir: Path) -> pd.DataFrame:
    frame = load_messages(data_path)
    version = dataset_version(data_path, len(frame))
    texts = frame["text"].tolist()
    encoder = LabelEncoder()
    encoded = encoder.fit_transform(frame["label"])
    labels = list(encoder.classes_)
    scam_index = labels.index("scam")
    legit_index = labels.index("legitimate")

    x_train, x_test, y_train, y_test = train_test_split(
        texts,
        encoded,
        test_size=TEST_SIZE,
        random_state=SEED,
        stratify=encoded,
    )

    rows: list[dict[str, object]] = []
    for name, pipeline in build_models().items():
        pipeline.fit(x_train, y_train)
        predicted = pipeline.predict(x_test)
        scores = evaluate(y_test, predicted, scam_index)
        rows.append(
            {
                "method": name,
                "accuracy": round(scores["accuracy"], 4),
                "f1_macro": round(scores["f1_macro"], 4),
                "scam_precision": round(scores["scam_precision"], 4),
                "scam_recall": round(scores["scam_recall"], 4),
                "legitimate_false_positive_rate": round(
                    _false_positive_rate(y_test, predicted, legit_index, scam_index),
                    4,
                ),
                "dataset_version": version,
                "seed": SEED,
            }
        )

    with patch.object(url_features, "_lookup_whois", return_value=datetime(2018, 1, 15)):
        with patch.object(
            url_features,
            "_lookup_redirects",
            side_effect=lambda url, timeout: {"length": 0, "destination": url},
        ):
            rubric_pred = [labels.index(_rubric_label(text)) for text in x_test]
    scores = evaluate(y_test, rubric_pred, scam_index)
    rows.append(
        {
            "method": "rubric",
            "accuracy": round(scores["accuracy"], 4),
            "f1_macro": round(scores["f1_macro"], 4),
            "scam_precision": round(scores["scam_precision"], 4),
            "scam_recall": round(scores["scam_recall"], 4),
            "legitimate_false_positive_rate": round(
                _false_positive_rate(y_test, rubric_pred, legit_index, scam_index),
                4,
            ),
            "dataset_version": version,
            "seed": SEED,
        }
    )

    models_dir.mkdir(parents=True, exist_ok=True)
    table = pd.DataFrame(rows)
    table.to_csv(models_dir / "evaluation.csv", index=False)
    counts = frame["label"].value_counts().to_dict()
    (models_dir / "evaluation_settings.json").write_text(
        json.dumps(
            {
                "seed": SEED,
                "test_size": TEST_SIZE,
                "dataset_path": "data/messages.csv" if data_path.resolve() == DEFAULT_DATA_PATH.resolve() else str(data_path),
                "dataset_version": version,
                "n_rows": int(len(frame)),
                "label_counts": {key: int(counts.get(key, 0)) for key in ("legitimate", "suspicious", "scam")},
                "rubric_mapping": "low=legitimate, medium=suspicious, high=scam",
                "url_lookups": "WHOIS and redirects are stubbed so the table can be regenerated offline",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return table


def main() -> None:
    try:
        table = evaluate_scorer(DEFAULT_DATA_PATH, DEFAULT_MODELS_DIR)
    except DatasetError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
    print(table.to_string(index=False))
    print(f"Wrote {DEFAULT_MODELS_DIR / 'evaluation.csv'}")


if __name__ == "__main__":
    main()
