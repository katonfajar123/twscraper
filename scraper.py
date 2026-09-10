"""
MBG crawler CLI - hardened acquisition engine.

Step 1 discovers verified root tweets through keyword search.
Step 2 expands verified roots into direct replies by default, or the complete
conversation tree when --include-nested is selected.

The v2 engine writes the canonical FSD schema, commits CSV bytes before state,
and keeps legacy output/checkpoint files untouched.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import importlib.util
import json
import os
import re
import sys
import uuid
from contextlib import aclosing
from datetime import datetime
from pathlib import Path
from collections.abc import Callable, Iterable
from typing import Any, TextIO

# Bab 7 FSD requires the browser-like curl-cffi transport. An explicit user
# override is still respected for diagnostics or controlled fallback runs.
os.environ.setdefault("TWS_HTTP_BACKEND", "curl")

from twscrape import API


# ---------------------------------------------------------------------------
# Acquisition configuration
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 2
DB_PATH = os.getenv("TWS_DB", "accounts.db")
HTTP_BACKEND = os.getenv("TWS_HTTP_BACKEND", "curl").strip().lower()
OUTPUT_DIR = Path("output")
DEFAULT_CHECKPOINT = OUTPUT_DIR / "checkpoint_v2.json"
DEFAULT_KEYWORD_CONFIG = Path(__file__).resolve().parent / "config" / "scraping_keywords.txt"

DEFAULT_LIMIT = 200
DEFAULT_TARGET = 20_000
DEFAULT_MIN_REPLIES = 100
DEFAULT_DELAY = 5.0
DEFAULT_LANG = "in"
DEFAULT_BATCH_SIZE = 100

FALLBACK_STEP1_KEYWORDS = [
    "MBG",
    "makan bergizi gratis",
    "embege",
    "#MBG",
    "#MakanBergiziGratis",
    "mbg prabowo",
    "program mbg",
    "makan gratis sekolah",
    "mbg sekolah",
    "dapur mbg",
    "mbg gagal",
    "mbg korupsi",
    "mbg basi",
    "mbg enak",
    "mbg merata",
]


def load_keyword_config(path: Path = DEFAULT_KEYWORD_CONFIG) -> list[str]:
    """Load one search keyword or Boolean query per line from a user-editable file."""
    if not path.is_file():
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


STEP1_KEYWORDS = load_keyword_config() or FALLBACK_STEP1_KEYWORDS

SEARCH_PRODUCTS = ["Latest", "Top"]
SEARCH_NEGATIVE_FILTERS = "-filter:links -filter:media"
MBG_OFFICIAL_DOMAINS = ["mbg.go.id", "mbg.kemdikbud.go.id"]

SOURCE_KEYWORD = "KEYWORD_SEARCH"
SOURCE_REPLY = "REPLY_TWEET_ID"

HIERARCHY_ROOT = "Root_Tweet"
HIERARCHY_DIRECT = "Direct_Reply"
HIERARCHY_NESTED = "Nested_Reply"
HIERARCHY_OUTSIDE = "Outside_Conversation"
HIERARCHY_INVALID = "Invalid_Reply"

CSV_FIELDS = [
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
    "Display_Name",
    "Followers_Count",
    "Bahasa",
    "Jumlah_Reply",
    "Jumlah_Quote",
    "Jumlah_View",
    "Keyword_Matched",
    "URL",
]

RECONCILE_REQUIRED_FIELDS = (
    "Tweet_ID",
    "Teks_Komentar",
    "Sumber_Akuisisi",
    "Hierarki_Komentar",
)

LEGACY_ROOT_REQUIRED_FIELDS = {
    "tweet_id",
    "created_at",
    "username",
    "content",
    "like_count",
    "retweet_count",
    "reply_count",
    "step",
    "root_tweet_id",
    "is_retweet",
}

URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
MENTION_RE = re.compile(r"@\w+")
MBG_RELEVANCE_RE = re.compile(
    r"\bmbg\b|makan\s+bergizi|makan\s+siang\s+gratis|"
    r"makan\s+gratis\s+(?:anak\s+)?sekolah|embege|makanbergizigratis",
    re.IGNORECASE,
)
BOOLEAN_QUERY_RE = re.compile(
    r"\b(?:OR|AND|NOT)\b|[()]|(?:^|\s)-?filter:",
    re.IGNORECASE,
)
TWEET_URL_ID_RE = re.compile(r"(?:status/)?(\d{6,})/?(?:\?.*)?$", re.IGNORECASE)


class SchemaMismatchError(RuntimeError):
    """Raised when an existing CSV cannot safely receive canonical rows."""


class CheckpointError(RuntimeError):
    """Raised when checkpoint state is invalid or cannot be persisted."""


# ---------------------------------------------------------------------------
# Tweet mapping and validation
# ---------------------------------------------------------------------------

def normalize_id(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "none" else text


def _tweet_id(tweet: Any) -> str:
    return normalize_id(getattr(tweet, "id_str", None) or getattr(tweet, "id", None))


def _conversation_id(tweet: Any) -> str:
    return normalize_id(
        getattr(tweet, "conversationIdStr", None)
        or getattr(tweet, "conversationId", None)
    )


def _parent_id(tweet: Any) -> str:
    return normalize_id(
        getattr(tweet, "inReplyToTweetIdStr", None)
        or getattr(tweet, "inReplyToTweetId", None)
    )


def normalize_language(language: str | None) -> str:
    value = (language or "").strip().lower()
    if value in {"", "*", "all", "semua"}:
        return ""
    if value in {"id", "ind", "indonesia", "bahasa indonesia"}:
        return "in"
    return value


def language_matches(tweet_language: str | None, required_language: str | None) -> bool:
    required = normalize_language(required_language)
    if not required:
        return True
    actual = normalize_language(tweet_language)
    return bool(actual) and actual == required


def is_root_tweet(tweet: Any) -> bool:
    tweet_id = _tweet_id(tweet)
    conversation_id = _conversation_id(tweet)
    parent_id = _parent_id(tweet)
    content = (getattr(tweet, "rawContent", None) or "").lstrip()
    is_retweet = getattr(tweet, "retweetedTweet", None) is not None
    return bool(
        tweet_id
        and conversation_id == tweet_id
        and not parent_id
        and not is_retweet
        and not content.startswith("RT @")
    )


def classify_reply(tweet: Any, root_tweet_id: str | int) -> str:
    root_id = normalize_id(root_tweet_id)
    tweet_id = _tweet_id(tweet)
    conversation_id = _conversation_id(tweet)
    parent_id = _parent_id(tweet)

    if not root_id or conversation_id != root_id:
        return HIERARCHY_OUTSIDE
    if tweet_id == root_id:
        return HIERARCHY_ROOT
    if not parent_id:
        return HIERARCHY_INVALID
    if parent_id == root_id:
        return HIERARCHY_DIRECT
    return HIERARCHY_NESTED


def is_relevant_mbg_text(content: str) -> bool:
    return bool(MBG_RELEVANCE_RE.search(content or ""))


def is_official_link_only(content: str) -> bool:
    content_lower = (content or "").lower()
    if not any(domain in content_lower for domain in MBG_OFFICIAL_DOMAINS):
        return False
    text_without_url = URL_RE.sub("", content or "").strip()
    return len(text_without_url) < 30


def is_meaningful_text(content: str) -> bool:
    text = URL_RE.sub("", content or "")
    text = MENTION_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return len(text) >= 3


def build_search_query(keyword: str) -> str:
    term = keyword.strip()
    if " " in term and not term.startswith('"') and not BOOLEAN_QUERY_RE.search(term):
        term = f'"{term}"'
    filters = [
        value
        for value in SEARCH_NEGATIVE_FILTERS.split()
        if value.lower() not in term.lower()
    ]
    return " ".join([term, *filters]).strip()


def parse_seed_ids(values: Iterable[str]) -> list[str]:
    """Parse Tweet IDs or status URLs while preserving ID precision."""
    parsed: list[str] = []
    seen: set[str] = set()
    for value in values:
        for token in re.split(r"[\s,;]+", value.strip()):
            if not token:
                continue
            match = TWEET_URL_ID_RE.search(token)
            tweet_id = match.group(1) if match else token
            if not tweet_id.isdigit() or len(tweet_id) < 6:
                raise ValueError(f"Seed Tweet ID tidak valid: {token}")
            if tweet_id not in seen:
                parsed.append(tweet_id)
                seen.add(tweet_id)
    return parsed


def queue_manual_seeds(
    checkpoint: "Checkpoint",
    values: Iterable[str],
    *,
    label: str = "MANUAL_SEED",
) -> int:
    """Add user-supplied roots to Step 2 without pretending they are durable rows."""
    added = 0
    for tweet_id in parse_seed_ids(values):
        if tweet_id not in checkpoint.step2_queue:
            checkpoint.step2_queue[tweet_id] = label
            added += 1
    return added


def retry_wait_seconds(error: Exception, rate_wait: int, default_wait: int) -> int:
    error_text = str(error).lower()
    if (
        "rate" in error_text
        or "429" in error_text
        or "no account available" in error_text
    ):
        return rate_wait
    return default_wait


def build_row(
    tweet: Any,
    source: str,
    *,
    root_tweet_id: str | int | None = None,
    hierarchy: str | None = None,
    keyword_matched: str = "",
) -> dict[str, Any]:
    tweet_id = _tweet_id(tweet)
    if not tweet_id:
        raise ValueError("Tweet tidak memiliki ID")

    conversation_id = _conversation_id(tweet)
    parent_id = _parent_id(tweet)
    root_id = normalize_id(root_tweet_id)

    if source == SOURCE_KEYWORD:
        if conversation_id != tweet_id or parent_id:
            raise ValueError("Keyword result bukan root tweet tervalidasi")
        root_id = tweet_id
        hierarchy = hierarchy or HIERARCHY_ROOT
    elif source == SOURCE_REPLY:
        if not root_id or not conversation_id or not parent_id:
            raise ValueError("Metadata relasi reply tidak lengkap")
        hierarchy = hierarchy or classify_reply(tweet, root_id)
        if hierarchy not in {HIERARCHY_DIRECT, HIERARCHY_NESTED}:
            raise ValueError("Reply berada di luar percakapan target")
    else:
        raise ValueError(f"Sumber akuisisi tidak dikenal: {source}")

    user = getattr(tweet, "user", None)
    username = getattr(user, "username", "") if user else ""
    display_name = getattr(user, "displayname", "") if user else ""
    followers_count = getattr(user, "followersCount", 0) if user else 0
    posted_at = getattr(tweet, "date", None)

    return {
        "Tweet_ID": tweet_id,
        "Root_Tweet_ID": normalize_id(root_id),
        "Conversation_ID": normalize_id(conversation_id),
        "In_Reply_To_Tweet_ID": normalize_id(parent_id),
        "Waktu_Posting": posted_at.isoformat() if posted_at else "",
        "Username": username or "",
        "Teks_Komentar": getattr(tweet, "rawContent", None) or "",
        "Jumlah_Likes": getattr(tweet, "likeCount", 0) or 0,
        "Jumlah_Retweet": getattr(tweet, "retweetCount", 0) or 0,
        "Sumber_Akuisisi": source,
        "Hierarki_Komentar": hierarchy,
        "Display_Name": display_name or "",
        "Followers_Count": followers_count or 0,
        "Bahasa": getattr(tweet, "lang", None) or "",
        "Jumlah_Reply": getattr(tweet, "replyCount", 0) or 0,
        "Jumlah_Quote": getattr(tweet, "quoteCount", 0) or 0,
        "Jumlah_View": getattr(tweet, "viewCount", 0) or 0,
        "Keyword_Matched": keyword_matched,
        "URL": getattr(tweet, "url", None)
        or (f"https://x.com/{username}/status/{tweet_id}" if username else ""),
    }


# ---------------------------------------------------------------------------
# CSV and checkpoint durability
# ---------------------------------------------------------------------------

def read_csv_header(path: Path) -> list[str]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        return next(reader, [])


def validate_csv_schema(path: Path) -> None:
    header = read_csv_header(path)
    if header != CSV_FIELDS:
        raise SchemaMismatchError(
            f"Schema CSV tidak kompatibel: {path}. "
            "File legacy dipertahankan; gunakan output/checkpoint v2."
        )


def load_durable_csv_state(
    path: Path,
    min_replies: int = DEFAULT_MIN_REPLIES,
) -> tuple[set[str], int, dict[str, str]]:
    durable_ids: set[str] = set()
    invalid_rows = 0
    recovered_queue: dict[str, str] = {}

    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, strict=True)
        if reader.fieldnames != CSV_FIELDS:
            raise SchemaMismatchError(f"Schema CSV tidak kompatibel: {path}")

        try:
            rows = iter(reader)
            for row in rows:
                if None in row or any(value is None for value in row.values()):
                    invalid_rows += 1
                    continue
                if any(not (row.get(field) or "").strip() for field in RECONCILE_REQUIRED_FIELDS):
                    invalid_rows += 1
                    continue
                for id_field in (
                    "Tweet_ID",
                    "Root_Tweet_ID",
                    "Conversation_ID",
                    "In_Reply_To_Tweet_ID",
                ):
                    relation_id = normalize_id(row.get(id_field))
                    if relation_id and not relation_id.isdigit():
                        raise SchemaMismatchError(
                            f"{id_field} bukan digit utuh pada record "
                            f"{reader.line_num}; kemungkinan rusak oleh notasi ilmiah"
                        )
                tweet_id = normalize_id(row.get("Tweet_ID"))
                if not tweet_id:
                    invalid_rows += 1
                    continue
                durable_ids.add(tweet_id)

                try:
                    reply_count = int(row.get("Jumlah_Reply") or 0)
                except (TypeError, ValueError):
                    reply_count = 0
                if (
                    row.get("Sumber_Akuisisi") == SOURCE_KEYWORD
                    and row.get("Hierarki_Komentar") == HIERARCHY_ROOT
                    and reply_count >= min_replies
                ):
                    recovered_queue[tweet_id] = row.get("Keyword_Matched") or ""
        except csv.Error as exc:
            raise SchemaMismatchError(f"CSV rusak atau terpotong: {path}: {exc}") from exc

    return durable_ids, invalid_rows, recovered_queue


def load_durable_csv_ids(path: Path) -> tuple[set[str], int]:
    durable_ids, invalid_rows, _ = load_durable_csv_state(path)
    return durable_ids, invalid_rows


def _legacy_integer(value: Any) -> int:
    try:
        return int(str(value or "0").strip())
    except (TypeError, ValueError):
        return 0


def build_legacy_root_row(row: dict[str, Any]) -> dict[str, Any]:
    """Map one legacy Step-1 row to the canonical root schema.

    The legacy format did not persist conversationId. Its acquisition contract
    represented verified Step-1 roots with ``step=1_root``, an empty
    ``root_tweet_id``, and ``is_retweet=0``. Every imported seed is validated
    again against live relationship metadata immediately before Step 2.
    """
    tweet_id = normalize_id(row.get("tweet_id"))
    step = str(row.get("step") or "").strip()
    legacy_parent = normalize_id(row.get("root_tweet_id"))
    is_retweet = str(row.get("is_retweet") or "0").strip().lower()
    content = str(row.get("content") or "")

    if not tweet_id or not tweet_id.isdigit():
        raise ValueError("Tweet ID legacy tidak valid")
    if step != "1_root" or legacy_parent:
        raise ValueError("Baris legacy bukan root Step 1")
    if is_retweet in {"1", "true", "yes", "y"}:
        raise ValueError("Baris legacy adalah retweet")
    if not is_meaningful_text(content):
        raise ValueError("Teks root legacy tidak bermakna")

    return {
        "Tweet_ID": tweet_id,
        "Root_Tweet_ID": tweet_id,
        "Conversation_ID": tweet_id,
        "In_Reply_To_Tweet_ID": "",
        "Waktu_Posting": str(row.get("created_at") or ""),
        "Username": str(row.get("username") or ""),
        "Teks_Komentar": content,
        "Jumlah_Likes": _legacy_integer(row.get("like_count")),
        "Jumlah_Retweet": _legacy_integer(row.get("retweet_count")),
        "Sumber_Akuisisi": SOURCE_KEYWORD,
        "Hierarki_Komentar": HIERARCHY_ROOT,
        "Display_Name": str(row.get("display_name") or ""),
        "Followers_Count": _legacy_integer(row.get("followers_count")),
        "Bahasa": str(row.get("lang") or ""),
        "Jumlah_Reply": _legacy_integer(row.get("reply_count")),
        "Jumlah_Quote": _legacy_integer(row.get("quote_count")),
        "Jumlah_View": _legacy_integer(row.get("view_count")),
        "Keyword_Matched": str(row.get("keyword_matched") or ""),
        "URL": str(row.get("url") or ""),
    }


def import_legacy_roots(
    path: Path,
    writer: csv.DictWriter,
    csv_file: TextIO,
    checkpoint: "Checkpoint",
    min_replies: int,
    batch_size: int,
) -> dict[str, int]:
    """Import legacy Step-1 roots without changing the source CSV/checkpoint."""
    if not path.exists():
        raise SchemaMismatchError(f"CSV legacy tidak ditemukan: {path}")

    total = 0
    imported = 0
    duplicate = 0
    rejected = 0
    eligible = 0
    pending_ids: set[str] = set()
    pending_queue: dict[str, str] = {}

    try:
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle, strict=True)
            missing = LEGACY_ROOT_REQUIRED_FIELDS - set(reader.fieldnames or [])
            if missing:
                raise SchemaMismatchError(
                    "Schema CSV legacy tidak kompatibel; field hilang: "
                    + ", ".join(sorted(missing))
                )

            for legacy_row in reader:
                total += 1
                try:
                    row = build_legacy_root_row(legacy_row)
                except ValueError:
                    rejected += 1
                    continue

                tweet_id = row["Tweet_ID"]
                if tweet_id in checkpoint.seen_ids or tweet_id in pending_ids:
                    duplicate += 1
                    continue

                writer.writerow(row)
                pending_ids.add(tweet_id)
                imported += 1

                if int(row["Jumlah_Reply"]) >= min_replies:
                    pending_queue[tweet_id] = row["Keyword_Matched"]
                    eligible += 1

                if len(pending_ids) >= batch_size:
                    commit_progress(
                        csv_file,
                        checkpoint,
                        pending_ids,
                        queue_updates=pending_queue,
                    )
    except csv.Error as exc:
        if pending_ids:
            commit_progress(
                csv_file,
                checkpoint,
                pending_ids,
                queue_updates=pending_queue,
            )
        raise SchemaMismatchError(f"CSV legacy rusak: {path}: {exc}") from exc

    commit_progress(
        csv_file,
        checkpoint,
        pending_ids,
        queue_updates=pending_queue,
    )
    return {
        "total": total,
        "imported": imported,
        "duplicate": duplicate,
        "rejected": rejected,
        "eligible": eligible,
    }


class Checkpoint:
    def __init__(self, path: Path):
        self.path = path
        self.seen_ids: set[str] = set()
        self.done_queries: set[str] = set()
        self.step2_queue: dict[str, str] = {}
        self.root_status: dict[str, str] = {}
        self.output_file = ""

    @property
    def total(self) -> int:
        return len(self.seen_ids)

    @property
    def has_state(self) -> bool:
        return bool(
            self.seen_ids
            or self.done_queries
            or self.step2_queue
            or self.root_status
            or self.output_file
        )

    def _payload(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "seen_ids": sorted(self.seen_ids),
            "done_queries": sorted(self.done_queries),
            "step2_queue": dict(sorted(self.step2_queue.items())),
            "root_status": dict(sorted(self.root_status.items())),
            "output_file": self.output_file,
            "saved_at": datetime.now().astimezone().isoformat(),
        }

    def load(self) -> bool:
        if not self.path.exists():
            return False

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CheckpointError(f"Gagal membaca checkpoint {self.path}: {exc}") from exc

        if data.get("version") != SCHEMA_VERSION:
            raise CheckpointError(
                f"Checkpoint {self.path} bukan schema v{SCHEMA_VERSION}. "
                "Checkpoint legacy tidak diubah."
            )

        self.seen_ids = {normalize_id(value) for value in data.get("seen_ids", [])}
        self.seen_ids.discard("")
        self.done_queries = set(data.get("done_queries", []))
        self.step2_queue = {
            normalize_id(key): str(value)
            for key, value in data.get("step2_queue", {}).items()
            if normalize_id(key)
        }
        self.root_status = {
            normalize_id(key): str(value)
            for key, value in data.get("root_status", {}).items()
            if normalize_id(key)
        }
        self.output_file = str(data.get("output_file", ""))

        print(
            f"[RESUME] {self.total:,} data durable | "
            f"{len(self.done_queries)} query selesai | "
            f"{len(self.step2_queue)} root di antrean"
        )
        return True

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_name(
            f".{self.path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        )

        try:
            with temp_path.open("w", encoding="utf-8", newline="") as handle:
                json.dump(self._payload(), handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.path)
        except OSError as exc:
            raise CheckpointError(f"Gagal menyimpan checkpoint atomik: {exc}") from exc
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

    def reset(self) -> None:
        self.seen_ids.clear()
        self.done_queries.clear()
        self.step2_queue.clear()
        self.root_status.clear()
        self.output_file = ""
        if self.path.exists():
            self.path.unlink()
        print(f"[RESET] Checkpoint v{SCHEMA_VERSION} dihapus: {self.path}")

    def reconcile_from_csv(
        self,
        csv_path: Path,
        min_replies: int = DEFAULT_MIN_REPLIES,
    ) -> dict[str, int]:
        durable_ids, invalid_rows, recovered_queue = load_durable_csv_state(
            csv_path,
            min_replies,
        )
        checkpoint_only = self.seen_ids - durable_ids
        csv_only = durable_ids - self.seen_ids
        queue_only_in_csv = set(recovered_queue) - set(self.step2_queue)
        self.seen_ids = durable_ids
        self.step2_queue.update(recovered_queue)
        return {
            "removed_checkpoint_only": len(checkpoint_only),
            "added_csv_only": len(csv_only),
            "recovered_queue": len(queue_only_in_csv),
            "invalid_rows": invalid_rows,
            "durable_total": len(durable_ids),
        }

    def root_completed(self, root_id: str, include_nested: bool) -> bool:
        status = self.root_status.get(root_id, "")
        if include_nested:
            return status in {"all_exhausted", "invalid_root"}
        return status in {"direct_exhausted", "all_exhausted", "invalid_root"}


def commit_progress(
    csv_file: TextIO,
    checkpoint: Checkpoint,
    pending_ids: set[str],
    *,
    queue_updates: dict[str, str] | None = None,
    done_query: str | None = None,
    root_status: tuple[str, str] | None = None,
) -> None:
    """
    Make CSV bytes durable before advancing checkpoint state.

    If checkpoint persistence fails after fsync, the next resume reconciles
    CSV-only IDs and safely reruns the unfinished query/root.
    """
    csv_file.flush()
    os.fsync(csv_file.fileno())

    checkpoint.seen_ids.update(pending_ids)
    if queue_updates:
        checkpoint.step2_queue.update(queue_updates)
    if done_query:
        checkpoint.done_queries.add(done_query)
    if root_status:
        checkpoint.root_status[root_status[0]] = root_status[1]
    checkpoint.save()

    pending_ids.clear()
    if queue_updates is not None:
        queue_updates.clear()


# ---------------------------------------------------------------------------
# Step 1 - verified root collection
# ---------------------------------------------------------------------------

async def step1_collect_roots(
    api: API,
    limit: int,
    lang: str | None,
    writer: csv.DictWriter,
    csv_file: TextIO,
    checkpoint: Checkpoint,
    target: int,
    min_replies: int,
    delay: float,
    batch_size: int,
    keywords: list[str] | None = None,
    stop_requested: Callable[[], bool] | None = None,
) -> int:
    count = 0
    selected_keywords = keywords or STEP1_KEYWORDS
    combinations = [
        (keyword, product)
        for keyword in selected_keywords
        for product in SEARCH_PRODUCTS
    ]

    print("\n" + "=" * 60)
    print("STEP 1 -- Verified Root Tweet Collection")
    print(f"  Kombinasi          : {len(combinations)}")
    print(f"  Limit per kombinasi: {limit}")
    print(f"  Bahasa             : {normalize_language(lang) or 'semua'}")
    print(f"  Root -> Step 2     : reply_count >= {min_replies}")
    print("=" * 60 + "\n")

    for index, (keyword, product) in enumerate(combinations, 1):
        if stop_requested and stop_requested():
            print("\n[STOP] Permintaan berhenti diterima sebelum query berikutnya.")
            break
        if checkpoint.total >= target:
            print(f"\n[OK] Target {target:,} data durable tercapai.")
            break

        query_key = (
            f"s1v{SCHEMA_VERSION}::{normalize_language(lang) or 'all'}::"
            f"{keyword}::{product}::{SEARCH_NEGATIVE_FILTERS}"
        )
        if query_key in checkpoint.done_queries:
            continue

        query = build_search_query(keyword)
        percent = index / len(combinations) * 100
        print(f"  [{percent:5.1f}%] [{product}] {query}", end=" ... ", flush=True)
        await asyncio.sleep(delay)

        pending_ids: set[str] = set()
        pending_queue: dict[str, str] = {}
        new_count = 0
        skipped_reply = 0
        skipped_language = 0
        skipped_quality = 0
        target_reached = False
        exhausted = False

        try:
            async with aclosing(
                api.search(query, limit=limit, kv={"product": product})
            ) as tweets:
                async for tweet in tweets:
                    if stop_requested and stop_requested():
                        print("STOP diminta; menyimpan batch saat ini ... ", end="")
                        break
                    if checkpoint.total + len(pending_ids) >= target:
                        target_reached = True
                        break

                    tweet_id = _tweet_id(tweet)
                    if not tweet_id or tweet_id in checkpoint.seen_ids or tweet_id in pending_ids:
                        continue
                    if not is_root_tweet(tweet):
                        skipped_reply += 1
                        continue
                    if not language_matches(getattr(tweet, "lang", None), lang):
                        skipped_language += 1
                        continue

                    content = getattr(tweet, "rawContent", None) or ""
                    if (
                        not is_meaningful_text(content)
                        or not is_relevant_mbg_text(content)
                        or URL_RE.search(content)
                        or is_official_link_only(content)
                    ):
                        skipped_quality += 1
                        continue

                    row = build_row(
                        tweet,
                        SOURCE_KEYWORD,
                        root_tweet_id=tweet_id,
                        hierarchy=HIERARCHY_ROOT,
                        keyword_matched=f"{keyword}[{product}]",
                    )
                    writer.writerow(row)
                    pending_ids.add(tweet_id)
                    new_count += 1
                    count += 1

                    if (getattr(tweet, "replyCount", 0) or 0) >= min_replies:
                        pending_queue[tweet_id] = f"{keyword}[{product}]"

                    if len(pending_ids) >= batch_size:
                        commit_progress(
                            csv_file,
                            checkpoint,
                            pending_ids,
                            queue_updates=pending_queue,
                        )

            stopped = bool(stop_requested and stop_requested())
            exhausted = not target_reached and not stopped
        except asyncio.CancelledError:
            if pending_ids:
                commit_progress(
                    csv_file,
                    checkpoint,
                    pending_ids,
                    queue_updates=pending_queue,
                )
            raise
        except Exception as exc:
            if pending_ids:
                commit_progress(
                    csv_file,
                    checkpoint,
                    pending_ids,
                    queue_updates=pending_queue,
                )
            error_text = str(exc)
            wait_seconds = retry_wait_seconds(exc, rate_wait=120, default_wait=15)
            print(f"ERROR ({wait_seconds}s): {error_text[:120]}")
            await asyncio.sleep(wait_seconds)
            continue

        commit_progress(
            csv_file,
            checkpoint,
            pending_ids,
            queue_updates=pending_queue,
            done_query=query_key if exhausted else None,
        )

        print(
            f"+{new_count} | skip reply={skipped_reply}, "
            f"lang={skipped_language}, quality={skipped_quality} | "
            f"Durable={checkpoint.total:,} | Queue={len(checkpoint.step2_queue):,}"
        )

        if target_reached:
            print(f"\n[OK] Target {target:,} data durable tercapai.")
            break
        if stop_requested and stop_requested():
            print("[STOP] Step 1 berhenti aman setelah CSV dan checkpoint sinkron.")
            break

    return count


# ---------------------------------------------------------------------------
# Step 2 - direct/all conversation replies
# ---------------------------------------------------------------------------

async def step2_scrape_replies(
    api: API,
    lang: str | None,
    writer: csv.DictWriter,
    csv_file: TextIO,
    checkpoint: Checkpoint,
    target: int,
    delay: float,
    batch_size: int,
    include_nested: bool,
    stop_requested: Callable[[], bool] | None = None,
) -> int:
    pending_roots = [
        (root_id, keyword)
        for root_id, keyword in checkpoint.step2_queue.items()
        if not checkpoint.root_completed(root_id, include_nested)
    ]

    mode_label = "Direct + Nested" if include_nested else "Direct Reply"
    print("\n" + "=" * 60)
    print(f"STEP 2 -- {mode_label}")
    print(f"  Root pending: {len(pending_roots):,}")
    print("  Pagination  : sampai endpoint exhausted")
    print("=" * 60 + "\n")

    count = 0
    for index, (root_id, keyword_matched) in enumerate(pending_roots, 1):
        if stop_requested and stop_requested():
            print("\n[STOP] Permintaan berhenti diterima sebelum root berikutnya.")
            break
        if checkpoint.total >= target:
            print(f"\n[OK] Target {target:,} data durable tercapai.")
            break

        percent = index / len(pending_roots) * 100 if pending_roots else 100
        print(f"  [{percent:5.1f}%] Root {root_id}", end=" ... ", flush=True)
        await asyncio.sleep(delay)

        pending_ids: set[str] = set()
        new_count = 0
        skipped_invalid = 0
        skipped_language = 0
        skipped_quality = 0
        target_reached = False

        if not root_id.isdigit():
            checkpoint.root_status[root_id] = "invalid_root"
            checkpoint.save()
            print("SKIP: root ID bukan angka")
            continue

        def accept_reply(tweet: Any) -> bool:
            nonlocal new_count
            nonlocal skipped_invalid
            nonlocal skipped_language
            nonlocal skipped_quality
            nonlocal target_reached
            nonlocal count

            if checkpoint.total + len(pending_ids) >= target:
                target_reached = True
                return False

            tweet_id = _tweet_id(tweet)
            if (
                not tweet_id
                or tweet_id in checkpoint.seen_ids
                or tweet_id in pending_ids
            ):
                return True

            hierarchy = classify_reply(tweet, root_id)
            allowed = {HIERARCHY_DIRECT}
            if include_nested:
                allowed.add(HIERARCHY_NESTED)
            if hierarchy not in allowed:
                skipped_invalid += 1
                return True
            if not language_matches(getattr(tweet, "lang", None), lang):
                skipped_language += 1
                return True

            content = getattr(tweet, "rawContent", None) or ""
            if not is_meaningful_text(content):
                skipped_quality += 1
                return True

            writer.writerow(
                build_row(
                    tweet,
                    SOURCE_REPLY,
                    root_tweet_id=root_id,
                    hierarchy=hierarchy,
                    keyword_matched=keyword_matched,
                )
            )
            pending_ids.add(tweet_id)
            new_count += 1
            count += 1

            if len(pending_ids) >= batch_size:
                commit_progress(csv_file, checkpoint, pending_ids)
            return True

        try:
            # tweet_thread contains the focal tweet and its conversation in a
            # single TweetDetail stream. This proves the seed relationship and
            # avoids spending a second request on api.tweet_details().
            root_verified = False
            deferred: list[Any] = []
            async with aclosing(
                api.tweet_thread(int(root_id), limit=-1)
            ) as replies:
                async for tweet in replies:
                    if stop_requested and stop_requested():
                        print("STOP diminta; menyimpan batch saat ini ... ", end="")
                        break
                    hierarchy = classify_reply(tweet, root_id)
                    if hierarchy == HIERARCHY_ROOT:
                        if not is_root_tweet(tweet):
                            break
                        root_verified = True
                        root_tweet_id = _tweet_id(tweet)
                        if (
                            root_tweet_id not in checkpoint.seen_ids
                            and root_tweet_id not in pending_ids
                            and checkpoint.total + len(pending_ids) < target
                        ):
                            writer.writerow(
                                build_row(
                                    tweet,
                                    SOURCE_KEYWORD,
                                    root_tweet_id=root_id,
                                    hierarchy=HIERARCHY_ROOT,
                                    keyword_matched=keyword_matched,
                                )
                            )
                            pending_ids.add(root_tweet_id)
                            new_count += 1
                            count += 1
                        for candidate in deferred:
                            if not accept_reply(candidate):
                                break
                        deferred.clear()
                        if target_reached:
                            break
                        continue

                    if not root_verified:
                        deferred.append(tweet)
                        continue
                    if not accept_reply(tweet):
                        break

            if not root_verified:
                checkpoint.root_status[root_id] = "invalid_root"
                checkpoint.save()
                print("SKIP: metadata live menunjukkan seed bukan root")
                continue
        except asyncio.CancelledError:
            if pending_ids:
                commit_progress(csv_file, checkpoint, pending_ids)
            raise
        except Exception as exc:
            if pending_ids:
                commit_progress(csv_file, checkpoint, pending_ids)
            checkpoint.root_status[root_id] = "failed"
            checkpoint.save()
            error_text = str(exc)
            wait_seconds = retry_wait_seconds(exc, rate_wait=90, default_wait=10)
            print(f"ERROR ({wait_seconds}s): {error_text[:120]}")
            await asyncio.sleep(wait_seconds)
            continue

        completion_status = None
        stopped = bool(stop_requested and stop_requested())
        if not target_reached and not stopped:
            completion_status = (
                "all_exhausted" if include_nested else "direct_exhausted"
            )

        commit_progress(
            csv_file,
            checkpoint,
            pending_ids,
            root_status=(root_id, completion_status) if completion_status else None,
        )
        print(
            f"+{new_count} | skip invalid={skipped_invalid}, "
            f"lang={skipped_language}, quality={skipped_quality} | "
            f"Durable={checkpoint.total:,}"
        )

        if target_reached:
            print(f"\n[OK] Target {target:,} data durable tercapai.")
            break
        if stopped:
            print("[STOP] Step 2 berhenti aman setelah CSV dan checkpoint sinkron.")
            break

    return count


# ---------------------------------------------------------------------------
# Main and CLI
# ---------------------------------------------------------------------------

def resolve_user_path(value: str, default_parent: Path) -> Path:
    path = Path(value)
    if path.is_absolute() or path.parent != Path("."):
        return path
    return default_parent / path


def choose_output_path(args: argparse.Namespace, checkpoint: Checkpoint, resumed: bool) -> Path:
    if args.output:
        candidate = resolve_user_path(args.output, OUTPUT_DIR)
        if resumed and checkpoint.output_file and checkpoint.has_state:
            existing = Path(checkpoint.output_file)
            if candidate.resolve() != existing.resolve():
                raise CheckpointError(
                    "Checkpoint aktif terikat ke output berbeda. "
                    "Gunakan checkpoint baru untuk output baru."
                )
        return candidate

    if resumed and checkpoint.output_file:
        return Path(checkpoint.output_file)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    method = "Hybrid" if args.step == 0 else "Keyword" if args.step == 1 else "Replies"
    return OUTPUT_DIR / f"MBG_Dataset_{method}_{timestamp}.csv"


async def main(args: argparse.Namespace) -> None:
    if args.target <= 0:
        raise ValueError("Target harus lebih besar dari nol")
    if args.limit <= 0:
        raise ValueError("Limit Step 1 harus lebih besar dari nol")
    if args.min_replies < 0:
        raise ValueError("Minimum replies tidak boleh negatif")
    if args.delay < 0:
        raise ValueError("Delay tidak boleh negatif")
    if args.batch_size <= 0:
        raise ValueError("Batch size harus lebih besar dari nol")
    if HTTP_BACKEND == "curl" and importlib.util.find_spec("curl_cffi") is None:
        raise RuntimeError(
            'Backend curl dipilih tetapi curl-cffi belum terpasang. '
            'Jalankan: python -m pip install "twscrape[curl]==0.20.1"'
        )

    OUTPUT_DIR.mkdir(exist_ok=True)
    checkpoint_path = Path(args.checkpoint)
    checkpoint = Checkpoint(checkpoint_path)

    if args.reset:
        checkpoint.reset()

    resumed = checkpoint.load()
    output_path = choose_output_path(args, checkpoint, resumed)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    file_exists = output_path.exists() and output_path.stat().st_size > 0
    if file_exists:
        validate_csv_schema(output_path)
        reconciliation = checkpoint.reconcile_from_csv(
            output_path,
            args.min_replies,
        )
        if (
            reconciliation["removed_checkpoint_only"]
            or reconciliation["added_csv_only"]
            or reconciliation["recovered_queue"]
            or reconciliation["invalid_rows"]
        ):
            print(
                "[RECONCILE] "
                f"remove checkpoint-only={reconciliation['removed_checkpoint_only']} | "
                f"add csv-only={reconciliation['added_csv_only']} | "
                f"recover queue={reconciliation['recovered_queue']} | "
                f"invalid rows={reconciliation['invalid_rows']}"
            )
    elif checkpoint.has_state:
        raise CheckpointError(
            "Checkpoint memiliki data tetapi CSV output tidak tersedia. "
            "Pemulihan otomatis dihentikan agar state tidak dipalsukan."
        )

    checkpoint.output_file = str(output_path)

    if args.seed_id:
        new_seeds = queue_manual_seeds(checkpoint, args.seed_id)
        print(
            f"[SEED] {new_seeds} root manual baru; "
            f"total antrean={len(checkpoint.step2_queue)}"
        )

    if not file_exists:
        with output_path.open("w", newline="", encoding="utf-8-sig") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
            writer.writeheader()
            csv_file.flush()
            os.fsync(csv_file.fileno())

    checkpoint.save()

    stop_path = Path(args.stop_file) if args.stop_file else None

    def stop_requested() -> bool:
        return bool(stop_path and stop_path.exists())

    api = API(DB_PATH, raise_when_no_account=True)
    if args.include_nested and not hasattr(api, "tweet_thread"):
        raise RuntimeError(
            "Versi twscrape ini tidak mendukung tweet_thread untuk nested reply."
        )
    accounts = await api.pool.get_all()
    active_accounts = [
        account
        for account in accounts
        if account.active and account.has_session
    ]
    if not active_accounts:
        raise RuntimeError(
            "Tidak ada akun aktif dengan session. Jalankan setup akun terlebih dahulu."
        )

    print(f"[OK] {len(active_accounts)} akun aktif.")
    if len(active_accounts) < 5:
        print(
            "[WARN] Pool di bawah rekomendasi FSD 5-10 akun; "
            "rate limit dapat memperlambat proses."
        )
    print(f"[SCHEMA] v{SCHEMA_VERSION}")
    print(f"[HTTP] {HTTP_BACKEND}")
    if HTTP_BACKEND != "curl":
        print(
            "[WARN] FSD merekomendasikan TWS_HTTP_BACKEND=curl untuk "
            "TLS fingerprint browser-like."
        )
    print(f"[TARGET] {args.target:,} data valid")
    print(f"[LANG] {normalize_language(args.lang) or 'semua'}")
    print(f"[CHECKPOINT] {checkpoint_path}")
    print(f"[CSV] {'Append' if file_exists else 'Baru'} -> {output_path}")

    with output_path.open("a", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)

        if args.import_legacy_roots:
            legacy_path = Path(args.import_legacy_roots)
            summary = import_legacy_roots(
                legacy_path,
                writer,
                csv_file,
                checkpoint,
                args.min_replies,
                args.batch_size,
            )
            print(
                "[IMPORT LEGACY] "
                f"total={summary['total']:,} | "
                f"baru={summary['imported']:,} | "
                f"duplikat={summary['duplicate']:,} | "
                f"ditolak={summary['rejected']:,} | "
                f"eligible>={args.min_replies}={summary['eligible']:,}"
            )

        step1_count = 0
        step2_count = 0

        if args.step in (0, 1):
            step1_count = await step1_collect_roots(
                api=api,
                limit=args.limit,
                lang=args.lang,
                writer=writer,
                csv_file=csv_file,
                checkpoint=checkpoint,
                target=args.target,
                min_replies=args.min_replies,
                delay=args.delay,
                batch_size=args.batch_size,
                keywords=args.keyword or None,
                stop_requested=stop_requested,
            )

        if args.step in (0, 2):
            step2_count = await step2_scrape_replies(
                api=api,
                lang=args.lang,
                writer=writer,
                csv_file=csv_file,
                checkpoint=checkpoint,
                target=args.target,
                delay=args.delay,
                batch_size=args.batch_size,
                include_nested=args.include_nested,
                stop_requested=stop_requested,
            )

    completed_roots = sum(
        status in {"direct_exhausted", "all_exhausted"}
        for status in checkpoint.root_status.values()
    )
    print("\n" + "=" * 60)
    print("SELESAI")
    print(f"  Total data durable : {checkpoint.total:,}")
    print(f"  Step 1 baru        : {step1_count:,}")
    print(f"  Step 2 baru        : {step2_count:,}")
    print(f"  Root selesai       : {completed_roots}/{len(checkpoint.step2_queue)}")
    print(f"  Output             : {output_path.resolve()}")
    print("=" * 60)

    if checkpoint.total < args.target:
        print(
            f"[INFO] Masih kurang {args.target - checkpoint.total:,} data valid. "
            "Jalankan ulang untuk resume."
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="MBG crawler v2: verified roots and durable reply extraction"
    )
    parser.add_argument(
        "--step",
        type=int,
        default=0,
        choices=[0, 1, 2],
        help="0=hybrid, 1=root keyword, 2=reply extraction",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Timeline entries per keyword query (default: {DEFAULT_LIMIT})",
    )
    parser.add_argument(
        "--target",
        type=int,
        default=DEFAULT_TARGET,
        help=f"Target data valid dan durable (default: {DEFAULT_TARGET:,})",
    )
    parser.add_argument(
        "--min-replies",
        type=int,
        default=DEFAULT_MIN_REPLIES,
        help=f"Threshold root masuk Step 2 (default: {DEFAULT_MIN_REPLIES})",
    )
    parser.add_argument(
        "--lang",
        default=DEFAULT_LANG,
        help="Filter bahasa hasil; id dan in dianggap Indonesia, all=tanpa filter",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=f"Delay antar request utama (default: {DEFAULT_DELAY})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Flush durable setiap N data (default: {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--include-nested",
        action="store_true",
        help="Step 2 memakai tweet_thread untuk direct dan nested replies",
    )
    parser.add_argument(
        "--keyword",
        action="append",
        default=[],
        help=(
            "Keyword/query Step 1; dapat diulang. Jika kosong memakai mapping "
            "bawaan. Query Boolean diteruskan tanpa dibungkus kutip."
        ),
    )
    parser.add_argument(
        "--seed-id",
        action="append",
        default=[],
        help="Tweet ID atau URL root manual untuk antrean Step 2; dapat diulang.",
    )
    parser.add_argument(
        "--stop-file",
        default="",
        help="File kontrol opsional; scraper berhenti aman saat file tersedia.",
    )
    parser.add_argument(
        "--import-legacy-roots",
        default="",
        help=(
            "Import CSV legacy Step-1 ke output canonical sebelum scraping; "
            "file sumber tidak diubah"
        ),
    )
    parser.add_argument(
        "--output",
        default="",
        help="Output CSV canonical; default dibuat otomatis di output/",
    )
    parser.add_argument(
        "--checkpoint",
        default=str(DEFAULT_CHECKPOINT),
        help=f"Checkpoint v2 (default: {DEFAULT_CHECKPOINT})",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Mulai session v2 baru; CSV lama tidak dihapus",
    )
    return parser


if __name__ == "__main__":
    try:
        asyncio.run(main(build_parser().parse_args()))
    except KeyboardInterrupt:
        print(
            "\n[STOP] Dihentikan pengguna. Baris yang sudah ter-flush "
            "akan direkonsiliasi saat resume."
        )
        raise SystemExit(130)
    except (CheckpointError, SchemaMismatchError, RuntimeError, ValueError) as exc:
        print(f"[ERROR] {exc}")
        raise SystemExit(1)
