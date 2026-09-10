from __future__ import annotations

import re
import unicodedata


def normalize_for_transformer(text: object) -> str:
    if not isinstance(text, str):
        return ""
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_pair_text(comment_text: object, root_text: object = "") -> str:
    comment = normalize_for_transformer(comment_text)
    root = normalize_for_transformer(root_text)
    if root:
        return f"{root} [SEP] {comment}"
    return comment
