"""Read-only dataset audit and non-destructive text preprocessing services."""

from __future__ import annotations

import csv
import json
import os
import re
import unicodedata
import uuid
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable, Iterable


CORE_FIELDS = [
    "Tweet_ID",
    "Root_Tweet_ID",
    "Conversation_ID",
    "In_Reply_To_Tweet_ID",
    "Waktu_Posting",
    "Username",
    "Teks_Komentar",
    "Jumlah_Likes",
    "Jumlah_Retweet",
    "Sumber_Akuisisi",
    "Hierarki_Komentar",
]
ID_FIELDS = [
    "Tweet_ID",
    "Root_Tweet_ID",
    "Conversation_ID",
    "In_Reply_To_Tweet_ID",
]
MAPPING_FIELDS = ["slang", "kata_baku", "frekuensi"]
SCIENTIFIC_ID_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?[Ee][+-]?\d+$")
URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
MENTION_RE = re.compile(r"(?<!\w)@[A-Za-z0-9_]+")
TOKEN_RE = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)*", re.IGNORECASE)
EMOJI_RE = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "]+",
    flags=re.UNICODE,
)
PUNCT_RE = re.compile(r"[^\w\s'-]", re.UNICODE)


class PipelineError(RuntimeError):
    """Raised when an input cannot be processed without risking data integrity."""


class PipelineCancelled(RuntimeError):
    """Raised after a user-requested cancellation removed the temporary output."""


@dataclass(frozen=True)
class PreprocessOptions:
    lowercase: bool = True
    url_mode: str = "token"  # token, remove, keep
    mention_mode: str = "token"  # token, remove, keep
    preserve_emoji: bool = True
    preserve_punctuation: bool = True
    normalize_slang: bool = True


def _bom_present(path: Path) -> bool:
    with path.open("rb") as handle:
        return handle.read(3) == b"\xef\xbb\xbf"


def _physical_lines(path: Path) -> int:
    count = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            count += chunk.count(b"\n")
    return count


def _counter_dict(counter: Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items(), key=lambda item: (-item[1], item[0])))


def audit_csv(path: Path, checkpoint_path: Path | None = None) -> dict:
    """Audit a CSV without modifying it or coercing long IDs to numbers."""
    path = Path(path)
    if not path.is_file():
        raise PipelineError(f"CSV tidak ditemukan: {path}")

    total = 0
    tweet_ids: set[str] = set()
    duplicate_rows = 0
    invalid_tweet_ids = 0
    scientific_ids = 0
    missing_core = Counter()
    source = Counter()
    hierarchy = Counter()
    language = Counter()
    roots: set[str] = set()
    root_row_ids: set[str] = set()
    direct_root_ids: list[str] = []
    invalid_root_relations = 0
    invalid_direct_relations = 0
    invalid_nested_relations = 0

    try:
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle, strict=True)
            headers = list(reader.fieldnames or [])
            missing_headers = [field for field in CORE_FIELDS if field not in headers]
            for row in reader:
                total += 1
                if None in row or any(value is None for value in row.values()):
                    raise PipelineError(f"Struktur kolom rusak pada record {total}")

                for field in CORE_FIELDS:
                    if field in headers and not str(row.get(field, "")).strip():
                        missing_core[field] += 1

                tweet_id = str(row.get("Tweet_ID", "")).strip()
                if SCIENTIFIC_ID_RE.fullmatch(tweet_id):
                    scientific_ids += 1
                if not tweet_id.isdigit():
                    invalid_tweet_ids += 1
                if tweet_id in tweet_ids:
                    duplicate_rows += 1
                elif tweet_id:
                    tweet_ids.add(tweet_id)

                root_id = str(row.get("Root_Tweet_ID", "")).strip()
                conversation_id = str(row.get("Conversation_ID", "")).strip()
                parent_id = str(row.get("In_Reply_To_Tweet_ID", "")).strip()
                if root_id:
                    roots.add(root_id)
                hierarchy_value = str(row.get("Hierarki_Komentar", "")).strip()
                if hierarchy_value == "Root_Tweet":
                    root_row_ids.add(tweet_id)
                    if not (
                        tweet_id
                        and tweet_id == root_id
                        and tweet_id == conversation_id
                        and not parent_id
                    ):
                        invalid_root_relations += 1
                elif hierarchy_value == "Direct_Reply":
                    direct_root_ids.append(root_id)
                    if not (
                        tweet_id
                        and root_id
                        and parent_id == root_id
                        and conversation_id == root_id
                    ):
                        invalid_direct_relations += 1
                elif hierarchy_value == "Nested_Reply":
                    if not (
                        tweet_id
                        and root_id
                        and conversation_id == root_id
                        and parent_id
                        and parent_id != root_id
                    ):
                        invalid_nested_relations += 1
                source[str(row.get("Sumber_Akuisisi", "")).strip() or "(kosong)"] += 1
                hierarchy[hierarchy_value or "(kosong)"] += 1
                if "Bahasa" in headers:
                    language[str(row.get("Bahasa", "")).strip() or "(kosong)"] += 1
    except UnicodeDecodeError as exc:
        raise PipelineError(f"CSV bukan UTF-8 yang valid: {exc}") from exc
    except csv.Error as exc:
        raise PipelineError(f"CSV rusak atau terpotong: {exc}") from exc

    orphan_direct_replies = sum(root_id not in root_row_ids for root_id in direct_root_ids)

    checkpoint = {
        "path": "",
        "seen_ids": None,
        "csv_only": None,
        "checkpoint_only": None,
        "error": "",
    }
    if checkpoint_path:
        cp_path = Path(checkpoint_path)
        checkpoint["path"] = str(cp_path)
        if cp_path.is_file():
            try:
                data = json.loads(cp_path.read_text(encoding="utf-8"))
                cp_ids = {str(value).strip() for value in data.get("seen_ids", [])}
                cp_ids.discard("")
                checkpoint.update(
                    seen_ids=len(cp_ids),
                    csv_only=len(tweet_ids - cp_ids),
                    checkpoint_only=len(cp_ids - tweet_ids),
                )
            except (OSError, json.JSONDecodeError, AttributeError) as exc:
                checkpoint["error"] = str(exc)
        else:
            checkpoint["error"] = "Checkpoint tidak ditemukan"

    errors: list[str] = []
    if missing_headers:
        errors.append("Kolom inti hilang: " + ", ".join(missing_headers))
    if scientific_ids:
        errors.append(
            f"{scientific_ids:,} Tweet_ID berbentuk notasi ilmiah; presisi ID telah rusak"
        )
    if invalid_tweet_ids:
        errors.append(f"{invalid_tweet_ids:,} Tweet_ID bukan digit utuh")
    if duplicate_rows:
        errors.append(f"{duplicate_rows:,} baris memiliki Tweet_ID duplikat")
    if invalid_root_relations:
        errors.append(f"{invalid_root_relations:,} relasi Root_Tweet tidak valid")
    if invalid_direct_relations:
        errors.append(f"{invalid_direct_relations:,} relasi Direct_Reply tidak valid")
    if invalid_nested_relations:
        errors.append(f"{invalid_nested_relations:,} relasi Nested_Reply tidak valid")
    if orphan_direct_replies:
        errors.append(f"{orphan_direct_replies:,} Direct_Reply tidak memiliki root di CSV")
    required_nonempty = [
        "Tweet_ID",
        "Root_Tweet_ID",
        "Conversation_ID",
        "Waktu_Posting",
        "Username",
        "Teks_Komentar",
        "Sumber_Akuisisi",
        "Hierarki_Komentar",
    ]
    for field in required_nonempty:
        if missing_core[field]:
            errors.append(f"{missing_core[field]:,} nilai {field} kosong")

    return {
        "path": str(path.resolve()),
        "utf8_bom": _bom_present(path),
        "physical_lines": _physical_lines(path),
        "total_rows": total,
        "unique_tweet_ids": len(tweet_ids),
        "duplicate_rows": duplicate_rows,
        "invalid_tweet_ids": invalid_tweet_ids,
        "scientific_notation_ids": scientific_ids,
        "headers": headers,
        "missing_headers": missing_headers,
        "missing_core": dict(missing_core),
        "root_coverage": len(roots),
        "root_rows": len(root_row_ids),
        "invalid_root_relations": invalid_root_relations,
        "invalid_direct_relations": invalid_direct_relations,
        "invalid_nested_relations": invalid_nested_relations,
        "orphan_direct_replies": orphan_direct_replies,
        "source_distribution": _counter_dict(source),
        "hierarchy_distribution": _counter_dict(hierarchy),
        "language_distribution": _counter_dict(language),
        "checkpoint": checkpoint,
        "contract_errors": errors,
        "contract_ok": not errors,
    }


def read_mapping(path: Path) -> list[dict[str, str]]:
    path = Path(path)
    if not path.is_file():
        raise PipelineError(f"File mapping tidak ditemukan: {path}")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, strict=True)
        required = {"slang", "kata_baku"}
        if not required.issubset(reader.fieldnames or []):
            raise PipelineError("Mapping wajib memiliki kolom slang dan kata_baku")
        for index, row in enumerate(reader, 2):
            slang = str(row.get("slang", "")).strip().lower()
            replacement = str(row.get("kata_baku", "")).strip().lower()
            frequency = str(row.get("frekuensi", "")).strip()
            if not slang or not replacement:
                raise PipelineError(f"Mapping kosong pada baris {index}")
            if slang == replacement:
                raise PipelineError(f"Mapping identitas tidak diizinkan: {slang}")
            if slang in seen:
                raise PipelineError(f"Slang duplikat: {slang}")
            seen.add(slang)
            rows.append(
                {"slang": slang, "kata_baku": replacement, "frekuensi": frequency}
            )
    return rows


def write_mapping(path: Path, rows: Iterable[dict[str, str]], overwrite: bool = False) -> int:
    path = Path(path)
    if path.exists() and not overwrite:
        raise PipelineError(f"File tujuan sudah ada: {path}")
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, row in enumerate(rows, 1):
        slang = str(row.get("slang", "")).strip().lower()
        replacement = str(row.get("kata_baku", "")).strip().lower()
        frequency = str(row.get("frekuensi", "")).strip()
        if not slang and not replacement and not frequency:
            continue
        if not slang or not replacement:
            raise PipelineError(f"Mapping ke-{index} belum lengkap")
        if slang == replacement:
            raise PipelineError(f"Mapping identitas tidak diizinkan: {slang}")
        if slang in seen:
            raise PipelineError(f"Slang duplikat: {slang}")
        seen.add(slang)
        normalized.append(
            {"slang": slang, "kata_baku": replacement, "frekuensi": frequency}
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=MAPPING_FIELDS, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(normalized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()
    return len(normalized)


def mapping_lookup(rows: Iterable[dict[str, str]]) -> dict[str, str]:
    return {row["slang"].lower(): row["kata_baku"].lower() for row in rows}


def cleanse_text(text: str, options: PreprocessOptions) -> str:
    value = unicodedata.normalize("NFC", text if isinstance(text, str) else "")
    if options.lowercase:
        value = value.lower()

    if options.url_mode == "token":
        value = URL_RE.sub(" url ", value)
    elif options.url_mode == "remove":
        value = URL_RE.sub(" ", value)
    elif options.url_mode != "keep":
        raise PipelineError(f"Mode URL tidak dikenal: {options.url_mode}")

    if options.mention_mode == "token":
        value = MENTION_RE.sub(" user ", value)
    elif options.mention_mode == "remove":
        value = MENTION_RE.sub(" ", value)
    elif options.mention_mode != "keep":
        raise PipelineError(f"Mode mention tidak dikenal: {options.mention_mode}")

    if not options.preserve_emoji:
        value = EMOJI_RE.sub(" ", value)
    if not options.preserve_punctuation:
        value = PUNCT_RE.sub(" ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_text(text: str, lookup: dict[str, str]) -> str:
    if not lookup:
        return text
    return TOKEN_RE.sub(lambda match: lookup.get(match.group(0).lower(), match.group(0)), text)


def preprocess_csv(
    input_path: Path,
    output_path: Path,
    *,
    mapping_path: Path | None = None,
    options: PreprocessOptions | None = None,
    overwrite: bool = False,
    progress: Callable[[int, int], None] | None = None,
    cancel_event: Event | None = None,
) -> dict:
    """Create a new UTF-8 BOM CSV; the source and raw text remain untouched."""
    input_path = Path(input_path)
    output_path = Path(output_path)
    options = options or PreprocessOptions()
    if input_path.resolve() == output_path.resolve():
        raise PipelineError("Output preprocessing harus berbeda dari file sumber")
    if output_path.exists() and not overwrite:
        raise PipelineError(f"File tujuan sudah ada: {output_path}")

    audit = audit_csv(input_path)
    if audit["contract_errors"]:
        raise PipelineError(
            "Preprocessing dihentikan karena kontrak data gagal: "
            + "; ".join(audit["contract_errors"])
        )

    lookup: dict[str, str] = {}
    if options.normalize_slang:
        if not mapping_path:
            raise PipelineError("Normalisasi slang aktif tetapi file mapping belum dipilih")
        lookup = mapping_lookup(read_mapping(Path(mapping_path)))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp = output_path.with_name(f".{output_path.name}.{uuid.uuid4().hex}.tmp")
    processed = 0
    normalized_hits = 0
    try:
        with (
            input_path.open("r", newline="", encoding="utf-8-sig") as source,
            temp.open("w", newline="", encoding="utf-8-sig") as destination,
        ):
            reader = csv.DictReader(source, strict=True)
            headers = list(reader.fieldnames or [])
            output_headers = [field for field in headers if field not in {"Content_Cleansing", "Content_Normalisasi"}]
            text_index = output_headers.index("Teks_Komentar") + 1
            output_headers[text_index:text_index] = ["Content_Cleansing", "Content_Normalisasi"]
            writer = csv.DictWriter(
                destination,
                fieldnames=output_headers,
                quoting=csv.QUOTE_ALL,
                extrasaction="ignore",
            )
            writer.writeheader()

            for row in reader:
                if cancel_event and cancel_event.is_set():
                    raise PipelineCancelled("Preprocessing dibatalkan pengguna")
                raw = str(row.get("Teks_Komentar", ""))
                cleaned = cleanse_text(raw, options)
                normalized = normalize_text(cleaned, lookup) if options.normalize_slang else cleaned
                if normalized != cleaned:
                    normalized_hits += 1
                row["Content_Cleansing"] = cleaned
                row["Content_Normalisasi"] = normalized
                writer.writerow(row)
                processed += 1
                if progress and (processed % 250 == 0 or processed == audit["total_rows"]):
                    progress(processed, audit["total_rows"])

            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temp, output_path)
    finally:
        if temp.exists():
            temp.unlink()

    return {
        "input": str(input_path.resolve()),
        "output": str(output_path.resolve()),
        "rows": processed,
        "mapping_entries": len(lookup),
        "rows_changed_by_normalization": normalized_hits,
        "utf8_bom": _bom_present(output_path),
    }


def load_preview(path: Path, limit: int = 200) -> tuple[list[str], list[list[str]]]:
    """Load only the newest records into memory for QTableView."""
    records: deque[dict[str, str]] = deque(maxlen=max(1, limit))
    with Path(path).open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        headers = list(reader.fieldnames or [])
        for row in reader:
            records.append(row)
    preferred = [
        "Tweet_ID",
        "Root_Tweet_ID",
        "Waktu_Posting",
        "Username",
        "Teks_Komentar",
        "Content_Cleansing",
        "Content_Normalisasi",
        "Sumber_Akuisisi",
        "Hierarki_Komentar",
    ]
    visible = [field for field in preferred if field in headers]
    if not visible:
        visible = headers[:10]
    return visible, [[str(row.get(field, "")) for field in visible] for row in records]
