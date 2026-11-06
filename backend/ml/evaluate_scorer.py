"""Compare the live rubric with TF-IDF baselines and DistilBERT.

The product score is the rubric in ``score_message``, not a model
probability. DistilBERT is a comparison row only. This command uses the
same stratified split as ``train_baselines`` (seed 42, test size 0.2)
and writes ``models/evaluation.csv``.
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

from backend.ml.distilbert import DistilBertError, predict_distilbert
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
from backend.services.risk import (
    HIGH_AT,
    MEDIUM_AT,
    PREVIOUS_HIGH_AT,
    PREVIOUS_MEDIUM_AT,
    band_for_score,
    score_message,
)

BAND_TO_LABEL = {"low": "legitimate", "medium": "suspicious", "high": "scam"}
BAND_CANDIDATES = (
    (PREVIOUS_MEDIUM_AT, PREVIOUS_HIGH_AT),
    (MEDIUM_AT, HIGH_AT),
    (20, 23),
    (10, 20),
)


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


def _metric_row(
    method: str,
    y_test,
    predicted,
    scam_index: int,
    legit_index: int,
    version: str,
) -> dict[str, object]:
    scores = evaluate(y_test, predicted, scam_index)
    return {
        "method": method,
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


def evaluate_scorer(
    data_path: Path,
    models_dir: Path,
    distilbert_predict=predict_distilbert,
) -> pd.DataFrame:
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
        rows.append(
            _metric_row(name, y_test, predicted, scam_index, legit_index, version)
        )

    distilbert_pred = distilbert_predict(
        x_train,
        y_train,
        x_test,
        n_labels=len(labels),
        seed=SEED,
    )
    rows.append(
        _metric_row(
            "distilbert",
            y_test,
            distilbert_pred,
            scam_index,
            legit_index,
            version,
        )
    )

    with patch.object(url_features, "_lookup_whois", return_value=datetime(2018, 1, 15)):
        with patch.object(
            url_features,
            "_lookup_redirects",
            side_effect=lambda url, timeout: {"length": 0, "destination": url},
        ):
            rubric_scores = [score_message(text)["score"] for text in x_test]

    band_rows: list[dict[str, object]] = []
    seen_cuts: set[tuple[int, int]] = set()
    for medium_at, high_at in (
        (PREVIOUS_MEDIUM_AT, PREVIOUS_HIGH_AT),
        (MEDIUM_AT, HIGH_AT),
        *BAND_CANDIDATES,
    ):
        cut = (medium_at, high_at)
        if cut in seen_cuts:
            continue
        seen_cuts.add(cut)
        predicted = [
            labels.index(BAND_TO_LABEL[band_for_score(score, medium_at=medium_at, high_at=high_at)])
            for score in rubric_scores
        ]
        scores = evaluate(y_test, predicted, scam_index)
        metrics = {
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
        band_rows.append({"medium_at": medium_at, "high_at": high_at, **metrics})
        if (medium_at, high_at) == (PREVIOUS_MEDIUM_AT, PREVIOUS_HIGH_AT):
            rows.append({"method": "rubric_old_20_50", **metrics})
        if (medium_at, high_at) == (MEDIUM_AT, HIGH_AT):
            rows.append({"method": "rubric", **metrics})

    models_dir.mkdir(parents=True, exist_ok=True)
    table = pd.DataFrame(rows)
    table.to_csv(models_dir / "evaluation.csv", index=False)
    pd.DataFrame(band_rows).to_csv(models_dir / "band_calibration.csv", index=False)
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
                "previous_bands": {"medium_at": PREVIOUS_MEDIUM_AT, "high_at": PREVIOUS_HIGH_AT},
                "live_bands": {"medium_at": MEDIUM_AT, "high_at": HIGH_AT},
                "url_lookups": "WHOIS and redirects are stubbed so the table can be regenerated offline",
                "distilbert": "comparison only; not used by analyze routes",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return table


def main() -> None:
    try:
        table = evaluate_scorer(DEFAULT_DATA_PATH, DEFAULT_MODELS_DIR)
    except (DatasetError, DistilBertError) as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
    print(table.to_string(index=False))
    print(f"Wrote {DEFAULT_MODELS_DIR / 'evaluation.csv'}")


if __name__ == "__main__":
    main()
