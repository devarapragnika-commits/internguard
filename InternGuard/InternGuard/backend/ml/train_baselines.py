"""Train TF-IDF baselines and write a comparison table.

One command retrains Logistic Regression, Random Forest, and XGBoost on the
held-out split of data/messages.csv. DistilBERT, the risk rubric, and the API
are out of scope.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_recall_fscore_support,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier

SEED = 42
TEST_SIZE = 0.2
LABELS = ("legitimate", "suspicious", "scam")
REQUIRED_COLUMNS = ("text", "label", "source", "is_synthetic")

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATA_PATH = ROOT_DIR / "data" / "messages.csv"
DEFAULT_MODELS_DIR = ROOT_DIR / "models"

TFIDF_SETTINGS = {
    "ngram_range": (1, 2),
    "min_df": 1,
    "max_features": 20000,
}

MODEL_SETTINGS = {
    "tfidf_logreg": {
        "C": 1.0,
        "max_iter": 1000,
        "solver": "lbfgs",
    },
    "random_forest": {
        "n_estimators": 200,
        "max_depth": None,
    },
    "xgboost": {
        "n_estimators": 200,
        "max_depth": 4,
        "learning_rate": 0.1,
    },
}


class DatasetError(Exception):
    """The messages file is missing or cannot be used for this training run."""


def dataset_version(path: Path, row_count: int) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    return f"sha256:{digest}:rows:{row_count}"


def load_messages(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise DatasetError(
            f"Labeled dataset not found: {path}\n"
            "Add data/messages.csv from the dataset task before training. "
            "This command does not invent messages."
        )

    frame = pd.read_csv(path)
    missing = [name for name in REQUIRED_COLUMNS if name not in frame.columns]
    if missing:
        raise DatasetError(
            f"{path} is missing columns: {', '.join(missing)}. "
            f"Required columns: {', '.join(REQUIRED_COLUMNS)}."
        )

    frame = frame.dropna(subset=["text", "label"]).copy()
    frame["text"] = frame["text"].astype(str).str.strip()
    frame["label"] = frame["label"].astype(str).str.strip()
    frame = frame[frame["text"] != ""]

    unknown = sorted(set(frame["label"]) - set(LABELS))
    if unknown:
        raise DatasetError(
            "Labels must be legitimate, suspicious, or scam. "
            f"Found: {', '.join(unknown)}."
        )
    if "scam" not in set(frame["label"]):
        raise DatasetError("The dataset has no rows labeled scam.")

    counts = frame["label"].value_counts()
    too_small = [label for label in LABELS if int(counts.get(label, 0)) < 2]
    if too_small:
        raise DatasetError(
            "Each label needs at least 2 rows for a stratified split. "
            f"Too few rows for: {', '.join(too_small)}."
        )
    return frame


def build_models() -> dict[str, Pipeline]:
    def tfidf() -> TfidfVectorizer:
        return TfidfVectorizer(**TFIDF_SETTINGS)

    logreg = MODEL_SETTINGS["tfidf_logreg"]
    forest = MODEL_SETTINGS["random_forest"]
    boost = MODEL_SETTINGS["xgboost"]
    return {
        "tfidf_logreg": Pipeline(
            [
                ("tfidf", tfidf()),
                (
                    "clf",
                    LogisticRegression(
                        C=logreg["C"],
                        max_iter=logreg["max_iter"],
                        solver=logreg["solver"],
                        random_state=SEED,
                    ),
                ),
            ]
        ),
        "random_forest": Pipeline(
            [
                ("tfidf", tfidf()),
                (
                    "clf",
                    RandomForestClassifier(
                        n_estimators=forest["n_estimators"],
                        max_depth=forest["max_depth"],
                        random_state=SEED,
                        n_jobs=-1,
                    ),
                ),
            ]
        ),
        "xgboost": Pipeline(
            [
                ("tfidf", tfidf()),
                (
                    "clf",
                    XGBClassifier(
                        n_estimators=boost["n_estimators"],
                        max_depth=boost["max_depth"],
                        learning_rate=boost["learning_rate"],
                        objective="multi:softprob",
                        random_state=SEED,
                        n_jobs=-1,
                        verbosity=0,
                    ),
                ),
            ]
        ),
    }


def evaluate(y_true: list[int], y_pred: list[int], scam_index: int) -> dict[str, float]:
    precision, recall, _, _ = precision_recall_fscore_support(
        y_true,
        y_pred,
        labels=[scam_index],
        average=None,
        zero_division=0,
    )
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "scam_precision": float(precision[0]),
        "scam_recall": float(recall[0]),
    }


def train_baselines(data_path: Path, models_dir: Path) -> pd.DataFrame:
    frame = load_messages(data_path)
    version = dataset_version(data_path, len(frame))

    texts = frame["text"].tolist()
    encoder = LabelEncoder()
    encoded = encoder.fit_transform(frame["label"])
    if "scam" not in encoder.classes_:
        raise DatasetError("The dataset has no rows labeled scam.")
    scam_index = list(encoder.classes_).index("scam")

    x_train, x_test, y_train, y_test = train_test_split(
        texts,
        encoded,
        test_size=TEST_SIZE,
        random_state=SEED,
        stratify=encoded,
    )

    models_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for name, pipeline in build_models().items():
        pipeline.fit(x_train, y_train)
        scores = evaluate(y_test, pipeline.predict(x_test), scam_index)
        joblib.dump(
            {
                "pipeline": pipeline,
                "labels": encoder.classes_.tolist(),
                "dataset_version": version,
                "seed": SEED,
            },
            models_dir / f"{name}.joblib",
        )
        rows.append(
            {
                "model": name,
                "accuracy": round(scores["accuracy"], 4),
                "f1_macro": round(scores["f1_macro"], 4),
                "scam_precision": round(scores["scam_precision"], 4),
                "scam_recall": round(scores["scam_recall"], 4),
                "dataset_version": version,
                "seed": SEED,
            }
        )

    table = pd.DataFrame(rows)
    table.to_csv(models_dir / "comparison.csv", index=False)
    settings = {
        "seed": SEED,
        "test_size": TEST_SIZE,
        "split": "stratified train/test, random_state 42, test_size 0.2",
        "dataset_path": str(data_path),
        "dataset_version": version,
        "tfidf": {
            "ngram_range": list(TFIDF_SETTINGS["ngram_range"]),
            "min_df": TFIDF_SETTINGS["min_df"],
            "max_features": TFIDF_SETTINGS["max_features"],
        },
        "models": MODEL_SETTINGS,
        "metrics": {
            "f1_macro": "macro F1 across legitimate, suspicious, and scam",
            "scam_precision": "precision for the scam class only",
            "scam_recall": "recall for the scam class only",
        },
    }
    (models_dir / "run_settings.json").write_text(
        json.dumps(settings, indent=2),
        encoding="utf-8",
    )
    return table


def main() -> None:
    try:
        table = train_baselines(DEFAULT_DATA_PATH, DEFAULT_MODELS_DIR)
    except DatasetError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
    print(table.to_string(index=False))
    print(f"Wrote {DEFAULT_MODELS_DIR / 'comparison.csv'}")


if __name__ == "__main__":
    main()
