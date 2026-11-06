"""Fine-tune DistilBERT for the evaluation table only.

This is not the live scorer. Analyze routes must keep using ``score_message``.
Weights are not written under ``models/`` and are not served by the API.
"""

from __future__ import annotations

import os
import random
from typing import Sequence

MODEL_NAME = "distilbert-base-uncased"
MAX_LENGTH = 128
EPOCHS = 2
BATCH_SIZE = 8
LEARNING_RATE = 2e-5


class DistilBertError(Exception):
    """Transformers extras are missing or training cannot run."""


def predict_distilbert(
    x_train: Sequence[str],
    y_train: Sequence[int],
    x_test: Sequence[str],
    n_labels: int,
    seed: int = 42,
) -> list[int]:
    """Return encoded test labels from a DistilBERT model trained on the split."""
    try:
        import numpy as np
        import torch
        from torch.utils.data import DataLoader, Dataset
        from transformers import DistilBertForSequenceClassification, DistilBertTokenizerFast
        from transformers.utils import logging as hf_logging
    except ImportError as exc:
        raise DistilBertError(
            "DistilBERT extras are not installed. From the repo root run:\n"
            "pip install -r requirements-ml.txt"
        ) from exc

    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    hf_logging.set_verbosity_error()
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = DistilBertTokenizerFast.from_pretrained(MODEL_NAME)
    model = DistilBertForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=n_labels,
    )
    model.to(device)

    class _EncodedSet(Dataset):
        def __init__(self, texts: Sequence[str], labels: Sequence[int] | None) -> None:
            encoded = tokenizer(
                list(texts),
                truncation=True,
                padding="max_length",
                max_length=MAX_LENGTH,
            )
            self._ids = encoded["input_ids"]
            self._mask = encoded["attention_mask"]
            self._labels = [int(value) for value in labels] if labels is not None else None

        def __len__(self) -> int:
            return len(self._ids)

        def __getitem__(self, index: int) -> dict:
            item = {
                "input_ids": torch.tensor(self._ids[index], dtype=torch.long),
                "attention_mask": torch.tensor(self._mask[index], dtype=torch.long),
            }
            if self._labels is not None:
                item["labels"] = torch.tensor(self._labels[index], dtype=torch.long)
            return item

    generator = torch.Generator()
    generator.manual_seed(seed)
    train_loader = DataLoader(
        _EncodedSet(x_train, y_train),
        batch_size=BATCH_SIZE,
        shuffle=True,
        generator=generator,
    )
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE)
    model.train()
    for _epoch in range(EPOCHS):
        for batch in train_loader:
            optimizer.zero_grad()
            outputs = model(
                input_ids=batch["input_ids"].to(device),
                attention_mask=batch["attention_mask"].to(device),
                labels=batch["labels"].to(device),
            )
            outputs.loss.backward()
            optimizer.step()

    model.eval()
    predicted: list[int] = []
    test_loader = DataLoader(_EncodedSet(x_test, None), batch_size=BATCH_SIZE)
    with torch.no_grad():
        for batch in test_loader:
            logits = model(
                input_ids=batch["input_ids"].to(device),
                attention_mask=batch["attention_mask"].to(device),
            ).logits
            predicted.extend(int(index) for index in logits.argmax(dim=-1).cpu())
    return predicted
