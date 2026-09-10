from __future__ import annotations

import asyncio
import csv
import importlib
import json
import os
import sys
import tempfile
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


# Keep the phase-one suite runnable with the standard library alone.  The
# production dependency is used when installed; otherwise only its API symbol
# is stubbed because these tests never construct a real client.
try:
    import scraper
except ModuleNotFoundError as exc:  # pragma: no cover - exercised on lean CI
    if exc.name != "twscrape":
        raise
    twscrape_stub = types.ModuleType("twscrape")
    twscrape_stub.API = object
    sys.modules["twscrape"] = twscrape_stub
    scraper = importlib.import_module("scraper")


ROOT_ID = "1900000000000000001"
DIRECT_ID = "1900000000000000002"
PARENT_ID = "1900000000000000003"
NESTED_ID = "1900000000000000004"
EXTRA_ID = "1900000000000000005"
FOREIGN_ID = "1900000000000000099"

REQUIRED_FIELDS = {
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
}

_UNSET = object()


def make_tweet(
    tweet_id: str = ROOT_ID,
    *,
    conversation_id: str | None | object = _UNSET,
    parent_id: str | None = None,
    content: str = "Program MBG untuk anak sekolah bagus",
    language: str | None = "in",
    reply_count: int = 0,
    retweeted_tweet: object | None = None,
) -> SimpleNamespace:
    if conversation_id is _UNSET:
        conversation_id = tweet_id

    return SimpleNamespace(
        id=int(tweet_id),
        conversationId=(
            int(conversation_id) if conversation_id is not None else None
        ),
        inReplyToTweetId=int(parent_id) if parent_id is not None else None,
        rawContent=content,
        lang=language,
        date=datetime(2026, 9, 1, 12, 30, tzinfo=timezone.utc),
        user=SimpleNamespace(
            username="warga_mbg",
            displayname="Warga Nusantara 🇮🇩",
            followersCount=321,
        ),
        likeCount=12,
        retweetCount=3,
        replyCount=reply_count,
        quoteCount=2,
        viewCount=456,
        retweetedTweet=retweeted_tweet,
        url=None,
    )


def canonical_row(tweet_id: str, text: str = "Opini MBG warga") -> dict[str, object]:
    return scraper.build_row(
        make_tweet(tweet_id, content=text),
        scraper.SOURCE_KEYWORD,
        root_tweet_id=tweet_id,
        hierarchy=scraper.HIERARCHY_ROOT,
        keyword_matched="MBG[Latest]",
    )


def write_canonical_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=scraper.CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


class FakeAPI:
    def __init__(self, tweets: list[SimpleNamespace]):
        self.tweets = list(tweets)
        self.search_calls: list[tuple[str, int, dict[str, str]]] = []
        self.yielded_ids: list[str] = []
        self.closed = False

    def search(self, query: str, *, limit: int, kv: dict[str, str]):
        self.search_calls.append((query, limit, kv))

        async def stream():
            try:
                for tweet in self.tweets:
                    self.yielded_ids.append(str(tweet.id))
                    yield tweet
            finally:
                self.closed = True

        return stream()


class FakeReplyAPI:
    def __init__(
        self,
        replies: list[SimpleNamespace],
        root: SimpleNamespace | None = None,
    ):
        self.replies = list(replies)
        self.root = root or make_tweet(reply_count=100)
        self.reply_calls = 0
        self.detail_calls = 0

    async def tweet_details(self, root_id: int):
        self.detail_calls += 1
        return self.root

    def _stream(self, tweets=None):
        async def stream():
            for tweet in self.replies if tweets is None else tweets:
                yield tweet

        return stream()

    def tweet_replies(self, root_id: int, *, limit: int):
        self.reply_calls += 1
        return self._stream()

    def tweet_thread(self, root_id: int, *, limit: int):
        self.reply_calls += 1
        return self._stream([self.root, *self.replies])


class RecordingFile:
    def __init__(self, handle, events: list[str]):
        self._handle = handle
        self._events = events

    def write(self, value):
        self._events.append("write")
        return self._handle.write(value)

    def flush(self):
        self._events.append("flush")
        return self._handle.flush()

    def fileno(self):
        return self._handle.fileno()

    def __getattr__(self, name):
        return getattr(self._handle, name)


class ObservingCheckpoint(scraper.Checkpoint):
    def __init__(self, path: Path, csv_path: Path, events: list[str]):
        super().__init__(path)
        self.csv_path = csv_path
        self.events = events
        self.ids_visible_during_save: set[str] = set()
        self.seen_during_save: set[str] = set()

    def save(self) -> None:
        self.events.append("checkpoint_save")
        with self.csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
            self.ids_visible_during_save = {
                row["Tweet_ID"] for row in csv.DictReader(handle)
            }
        self.seen_during_save = set(self.seen_ids)


class CsvContractTests(unittest.TestCase):
    def test_canonical_schema_ids_and_unicode_multiline_round_trip(self):
        content = 'Baris pertama\n"menu MBG, enak" 😀\r\nBaris ketiga—tetap mentah'
        tweet = make_tweet(
            DIRECT_ID,
            conversation_id=ROOT_ID,
            parent_id=ROOT_ID,
            content=content,
        )
        row = scraper.build_row(
            tweet,
            scraper.SOURCE_REPLY,
            root_tweet_id=int(ROOT_ID),
        )

        self.assertTrue(REQUIRED_FIELDS.issubset(scraper.CSV_FIELDS))
        self.assertEqual(set(row), set(scraper.CSV_FIELDS))
        self.assertEqual(row["Tweet_ID"], DIRECT_ID)
        self.assertEqual(row["Root_Tweet_ID"], ROOT_ID)
        self.assertEqual(row["Conversation_ID"], ROOT_ID)
        self.assertEqual(row["In_Reply_To_Tweet_ID"], ROOT_ID)
        for field in (
            "Tweet_ID",
            "Root_Tweet_ID",
            "Conversation_ID",
            "In_Reply_To_Tweet_ID",
        ):
            self.assertIsInstance(row[field], str)
        self.assertEqual(row["Teks_Komentar"], content)
        self.assertEqual(row["Hierarki_Komentar"], scraper.HIERARCHY_DIRECT)

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "unicode.csv"
            write_canonical_csv(path, [row])

            raw_bytes = path.read_bytes()
            self.assertTrue(raw_bytes.startswith(b"\xef\xbb\xbf"))
            self.assertEqual(raw_bytes.count(b"\xef\xbb\xbf"), 1)
            self.assertGreater(len(raw_bytes.decode("utf-8-sig").splitlines()), 2)

            with path.open("r", newline="", encoding="utf-8-sig") as handle:
                records = list(csv.DictReader(handle))
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["Tweet_ID"], DIRECT_ID)
            self.assertEqual(records[0]["Teks_Komentar"], content)

            durable_ids, invalid_rows = scraper.load_durable_csv_ids(path)
            self.assertEqual(durable_ids, {DIRECT_ID})
            self.assertEqual(invalid_rows, 0)

    def test_append_keeps_a_single_utf8_bom(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "append.csv"
            write_canonical_csv(path, [canonical_row(ROOT_ID)])

            with path.open("a", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=scraper.CSV_FIELDS)
                writer.writerow(canonical_row(DIRECT_ID, "MBG bergizi 🍱"))

            raw_bytes = path.read_bytes()
            self.assertTrue(raw_bytes.startswith(b"\xef\xbb\xbf"))
            self.assertEqual(raw_bytes.count(b"\xef\xbb\xbf"), 1)
            with path.open("r", newline="", encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(
                [row["Tweet_ID"] for row in rows], [ROOT_ID, DIRECT_ID]
            )


class LegacyImportTests(unittest.TestCase):
    def test_imports_only_legacy_step1_roots_and_queues_threshold(self):
        fields = [
            "tweet_id", "created_at", "username", "display_name",
            "followers_count", "content", "lang", "like_count",
            "retweet_count", "reply_count", "quote_count", "view_count",
            "is_retweet", "step", "keyword_matched", "root_tweet_id", "url",
        ]

        def legacy(tweet_id: str, **updates):
            row = {
                "tweet_id": tweet_id,
                "created_at": "2026-09-01T12:30:00+00:00",
                "username": "warga_mbg",
                "display_name": "Warga",
                "followers_count": "10",
                "content": "Program MBG untuk siswa",
                "lang": "in",
                "like_count": "2",
                "retweet_count": "1",
                "reply_count": "50",
                "quote_count": "0",
                "view_count": "100",
                "is_retweet": "0",
                "step": "1_root",
                "keyword_matched": "MBG[Latest]",
                "root_tweet_id": "",
                "url": f"https://x.com/warga_mbg/status/{tweet_id}",
            }
            row.update(updates)
            return row

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            legacy_path = root / "legacy.csv"
            output_path = root / "canonical.csv"
            checkpoint = scraper.Checkpoint(root / "checkpoint.json")
            with legacy_path.open("w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows([
                    legacy(ROOT_ID),
                    legacy(DIRECT_ID, reply_count="49"),
                    legacy(NESTED_ID, step="2_reply", root_tweet_id=ROOT_ID),
                    legacy(EXTRA_ID, is_retweet="1"),
                ])

            write_canonical_csv(output_path, [])
            with output_path.open("a", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=scraper.CSV_FIELDS)
                summary = scraper.import_legacy_roots(
                    legacy_path,
                    writer,
                    handle,
                    checkpoint,
                    min_replies=50,
                    batch_size=1,
                )

            self.assertEqual(summary["total"], 4)
            self.assertEqual(summary["imported"], 2)
            self.assertEqual(summary["rejected"], 2)
            self.assertEqual(summary["eligible"], 1)
            self.assertEqual(checkpoint.step2_queue, {ROOT_ID: "MBG[Latest]"})
            with output_path.open("r", newline="", encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(
                [row["Tweet_ID"] for row in rows], [ROOT_ID, DIRECT_ID]
            )
            self.assertTrue(
                all(row["Hierarki_Komentar"] == "Root_Tweet" for row in rows)
            )
            self.assertTrue(
                all(row["Conversation_ID"] == row["Tweet_ID"] for row in rows)
            )


class ValidationRuleTests(unittest.TestCase):
    def test_root_validation_rejects_replies_inconsistent_threads_and_retweets(self):
        self.assertTrue(scraper.is_root_tweet(make_tweet()))
        self.assertFalse(
            scraper.is_root_tweet(
                make_tweet(DIRECT_ID, conversation_id=ROOT_ID, parent_id=ROOT_ID)
            )
        )
        self.assertFalse(
            scraper.is_root_tweet(
                make_tweet(DIRECT_ID, conversation_id=ROOT_ID, parent_id=None)
            )
        )
        self.assertFalse(
            scraper.is_root_tweet(make_tweet(conversation_id=None))
        )
        self.assertFalse(
            scraper.is_root_tweet(make_tweet(retweeted_tweet=object()))
        )
        self.assertFalse(
            scraper.is_root_tweet(make_tweet(content="RT @akun Program MBG"))
        )

    def test_language_aliases_and_filtering(self):
        self.assertEqual(scraper.normalize_language("ID"), "in")
        self.assertEqual(scraper.normalize_language("Bahasa Indonesia"), "in")
        self.assertEqual(scraper.normalize_language("all"), "")
        self.assertTrue(scraper.language_matches("in", "id"))
        self.assertTrue(scraper.language_matches("ID", "in"))
        self.assertTrue(scraper.language_matches(None, "all"))
        self.assertFalse(scraper.language_matches("en", "id"))
        self.assertFalse(scraper.language_matches("und", "id"))
        self.assertFalse(scraper.language_matches(None, "id"))

    def test_hierarchy_mapping_and_string_relational_ids(self):
        direct = make_tweet(
            DIRECT_ID, conversation_id=ROOT_ID, parent_id=ROOT_ID
        )
        nested = make_tweet(
            NESTED_ID, conversation_id=ROOT_ID, parent_id=PARENT_ID
        )
        outside = make_tweet(
            DIRECT_ID, conversation_id=FOREIGN_ID, parent_id=ROOT_ID
        )
        invalid = make_tweet(
            DIRECT_ID, conversation_id=ROOT_ID, parent_id=None
        )
        root = make_tweet(ROOT_ID)

        self.assertEqual(
            scraper.classify_reply(direct, ROOT_ID), scraper.HIERARCHY_DIRECT
        )
        self.assertEqual(
            scraper.classify_reply(nested, ROOT_ID), scraper.HIERARCHY_NESTED
        )
        self.assertEqual(
            scraper.classify_reply(outside, ROOT_ID), scraper.HIERARCHY_OUTSIDE
        )
        self.assertEqual(
            scraper.classify_reply(invalid, ROOT_ID), scraper.HIERARCHY_INVALID
        )
        self.assertEqual(
            scraper.classify_reply(root, ROOT_ID), scraper.HIERARCHY_ROOT
        )

        row = scraper.build_row(
            nested,
            scraper.SOURCE_REPLY,
            root_tweet_id=int(ROOT_ID),
        )
        self.assertEqual(row["Hierarki_Komentar"], scraper.HIERARCHY_NESTED)
        self.assertEqual(row["Root_Tweet_ID"], ROOT_ID)
        self.assertEqual(row["Conversation_ID"], ROOT_ID)
        self.assertEqual(row["In_Reply_To_Tweet_ID"], PARENT_ID)


class CheckpointDurabilityTests(unittest.TestCase):
    def test_checkpoint_atomic_round_trip_and_failed_replace_preserves_old_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "checkpoint.json"
            checkpoint = scraper.Checkpoint(path)
            checkpoint.seen_ids = {ROOT_ID}
            checkpoint.done_queries = {"s1::MBG::Latest"}
            checkpoint.step2_queue = {ROOT_ID: "MBG[Latest]"}
            checkpoint.save()

            original_bytes = path.read_bytes()
            payload = json.loads(original_bytes.decode("utf-8"))
            self.assertEqual(payload["version"], scraper.SCHEMA_VERSION)
            self.assertEqual(payload["seen_ids"], [ROOT_ID])
            self.assertIsInstance(payload["seen_ids"][0], str)

            loaded = scraper.Checkpoint(path)
            with mock.patch("builtins.print"):
                self.assertTrue(loaded.load())
            self.assertEqual(loaded.seen_ids, {ROOT_ID})
            self.assertEqual(loaded.step2_queue, {ROOT_ID: "MBG[Latest]"})

            checkpoint.seen_ids.add(DIRECT_ID)
            with mock.patch.object(
                scraper.os, "replace", side_effect=OSError("replace gagal")
            ):
                with self.assertRaises(scraper.CheckpointError):
                    checkpoint.save()

            self.assertEqual(path.read_bytes(), original_bytes)
            self.assertEqual(
                list(path.parent.glob(f".{path.name}.*.tmp")), []
            )

    def test_reconcile_makes_valid_csv_authoritative(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            csv_path = root / "dataset.csv"
            valid_a = canonical_row(ROOT_ID)
            valid_a["Jumlah_Reply"] = 150
            valid_b = canonical_row(DIRECT_ID)
            invalid = canonical_row(NESTED_ID)
            invalid["Teks_Komentar"] = ""
            write_canonical_csv(csv_path, [valid_a, valid_b, invalid])

            checkpoint = scraper.Checkpoint(root / "checkpoint.json")
            checkpoint.seen_ids = {DIRECT_ID, FOREIGN_ID}
            result = checkpoint.reconcile_from_csv(csv_path)

            self.assertEqual(checkpoint.seen_ids, {ROOT_ID, DIRECT_ID})
            self.assertEqual(result["removed_checkpoint_only"], 1)
            self.assertEqual(result["added_csv_only"], 1)
            self.assertEqual(result["recovered_queue"], 1)
            self.assertEqual(result["invalid_rows"], 1)
            self.assertEqual(result["durable_total"], 2)
            self.assertEqual(
                checkpoint.step2_queue,
                {ROOT_ID: "MBG[Latest]"},
            )

    def test_commit_flushes_and_fsyncs_before_checkpoint_save(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            csv_path = root / "dataset.csv"
            events: list[str] = []
            checkpoint = ObservingCheckpoint(
                root / "checkpoint.json", csv_path, events
            )
            pending_ids = {ROOT_ID}
            real_fsync = os.fsync

            with csv_path.open("w", newline="", encoding="utf-8-sig") as raw:
                recording_file = RecordingFile(raw, events)
                writer = csv.DictWriter(
                    recording_file, fieldnames=scraper.CSV_FIELDS
                )
                writer.writeheader()
                events.clear()
                writer.writerow(canonical_row(ROOT_ID))

                def recording_fsync(file_descriptor):
                    events.append("fsync")
                    return real_fsync(file_descriptor)

                with mock.patch.object(
                    scraper.os, "fsync", side_effect=recording_fsync
                ):
                    scraper.commit_progress(
                        recording_file,
                        checkpoint,
                        pending_ids,
                        done_query="s1::MBG::Latest",
                    )

            self.assertEqual(
                events, ["write", "flush", "fsync", "checkpoint_save"]
            )
            self.assertEqual(checkpoint.ids_visible_during_save, {ROOT_ID})
            self.assertEqual(checkpoint.seen_during_save, {ROOT_ID})
            self.assertIn("s1::MBG::Latest", checkpoint.done_queries)
            self.assertEqual(pending_ids, set())

    def test_csv_failure_does_not_advance_checkpoint(self):
        class FailingFile:
            def flush(self):
                raise OSError("disk gagal")

            def fileno(self):
                return -1

        with tempfile.TemporaryDirectory() as temp_dir:
            checkpoint = scraper.Checkpoint(Path(temp_dir) / "checkpoint.json")
            pending_ids = {ROOT_ID}
            with mock.patch.object(checkpoint, "save") as save_mock:
                with self.assertRaises(OSError):
                    scraper.commit_progress(
                        FailingFile(), checkpoint, pending_ids
                    )

            self.assertEqual(checkpoint.seen_ids, set())
            self.assertEqual(pending_ids, {ROOT_ID})
            save_mock.assert_not_called()

    def test_checkpoint_failure_after_csv_commit_is_recovered_by_reconcile(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            csv_path = root / "dataset.csv"
            checkpoint_path = root / "checkpoint.json"
            checkpoint = scraper.Checkpoint(checkpoint_path)
            checkpoint.save()

            with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=scraper.CSV_FIELDS)
                writer.writeheader()
                writer.writerow(canonical_row(ROOT_ID))
                with mock.patch.object(
                    checkpoint,
                    "save",
                    side_effect=scraper.CheckpointError("simulasi crash"),
                ):
                    with self.assertRaises(scraper.CheckpointError):
                        scraper.commit_progress(
                            handle, checkpoint, {ROOT_ID}
                        )

            resumed = scraper.Checkpoint(checkpoint_path)
            with mock.patch("builtins.print"):
                self.assertTrue(resumed.load())
            self.assertEqual(resumed.seen_ids, set())
            result = resumed.reconcile_from_csv(csv_path)
            self.assertEqual(result["added_csv_only"], 1)
            self.assertEqual(resumed.seen_ids, {ROOT_ID})


class StepOneFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_step1_filters_deduplicates_and_stops_exactly_at_target(self):
        existing_id = "1900000000000000010"
        valid_a = "1900000000000000011"
        valid_b = "1900000000000000012"
        beyond_target = "1900000000000000013"
        reply_result = "1900000000000000014"
        english_result = "1900000000000000015"

        api = FakeAPI(
            [
                make_tweet(existing_id),
                make_tweet(
                    reply_result,
                    conversation_id=ROOT_ID,
                    parent_id=ROOT_ID,
                ),
                make_tweet(english_result, language="en"),
                make_tweet(valid_a, reply_count=10),
                make_tweet(valid_b),
                make_tweet(beyond_target),
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            csv_path = root / "dataset.csv"
            checkpoint = scraper.Checkpoint(root / "checkpoint.json")
            checkpoint.seen_ids = {existing_id}
            checkpoint.save()
            write_canonical_csv(csv_path, [canonical_row(existing_id)])

            with csv_path.open("a", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=scraper.CSV_FIELDS)
                with (
                    mock.patch.object(scraper, "STEP1_KEYWORDS", ["MBG"]),
                    mock.patch.object(scraper, "SEARCH_PRODUCTS", ["Latest"]),
                    mock.patch.object(
                        scraper.asyncio, "sleep", new=mock.AsyncMock()
                    ),
                    mock.patch("builtins.print"),
                ):
                    added = await scraper.step1_collect_roots(
                        api=api,
                        limit=50,
                        lang="id",
                        writer=writer,
                        csv_file=handle,
                        checkpoint=checkpoint,
                        target=3,
                        min_replies=5,
                        delay=0,
                        batch_size=100,
                    )

            with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
            row_ids = [row["Tweet_ID"] for row in rows]

            self.assertEqual(added, 2)
            self.assertEqual(checkpoint.total, 3)
            self.assertEqual(row_ids, [existing_id, valid_a, valid_b])
            self.assertNotIn(reply_result, checkpoint.seen_ids)
            self.assertNotIn(english_result, checkpoint.seen_ids)
            self.assertNotIn(beyond_target, checkpoint.seen_ids)
            self.assertEqual(
                checkpoint.step2_queue, {valid_a: "MBG[Latest]"}
            )
            self.assertNotIn("s1::MBG::Latest", checkpoint.done_queries)
            self.assertTrue(all(isinstance(value, str) for value in checkpoint.seen_ids))
            self.assertTrue(api.closed)
            self.assertEqual(len(api.search_calls), 1)
            query, requested_limit, options = api.search_calls[0]
            self.assertIn("-filter:links", query)
            self.assertEqual(requested_limit, 50)
            self.assertEqual(options, {"product": "Latest"})

    async def test_cancelled_step1_commits_partial_batch_without_done_marker(self):
        partial_id = "1900000000000000020"

        class CancellingAPI:
            def search(self, query: str, *, limit: int, kv: dict[str, str]):
                async def stream():
                    yield make_tweet(partial_id, reply_count=10)
                    raise asyncio.CancelledError()

                return stream()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            csv_path = root / "dataset.csv"
            checkpoint = scraper.Checkpoint(root / "checkpoint.json")
            write_canonical_csv(csv_path, [])

            with csv_path.open("a", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=scraper.CSV_FIELDS)
                with (
                    mock.patch.object(scraper, "STEP1_KEYWORDS", ["MBG"]),
                    mock.patch.object(scraper, "SEARCH_PRODUCTS", ["Latest"]),
                    mock.patch.object(
                        scraper.asyncio, "sleep", new=mock.AsyncMock()
                    ),
                    mock.patch("builtins.print"),
                ):
                    with self.assertRaises(asyncio.CancelledError):
                        await scraper.step1_collect_roots(
                            api=CancellingAPI(),
                            limit=50,
                            lang="id",
                            writer=writer,
                            csv_file=handle,
                            checkpoint=checkpoint,
                            target=10,
                            min_replies=5,
                            delay=0,
                            batch_size=100,
                        )

            durable_ids, invalid_rows = scraper.load_durable_csv_ids(csv_path)
            self.assertEqual(durable_ids, {partial_id})
            self.assertEqual(invalid_rows, 0)
            self.assertEqual(checkpoint.seen_ids, {partial_id})
            self.assertEqual(
                checkpoint.step2_queue,
                {partial_id: "MBG[Latest]"},
            )
            self.assertEqual(checkpoint.done_queries, set())


class StepTwoFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_child_seed_using_live_metadata(self):
        child_seed = make_tweet(
            ROOT_ID,
            conversation_id=FOREIGN_ID,
            parent_id=FOREIGN_ID,
        )
        api = FakeReplyAPI([], root=child_seed)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            csv_path = root / "dataset.csv"
            checkpoint = scraper.Checkpoint(root / "checkpoint.json")
            checkpoint.seen_ids = {ROOT_ID}
            checkpoint.step2_queue = {ROOT_ID: "MBG[Latest]"}
            write_canonical_csv(csv_path, [canonical_row(ROOT_ID)])

            with csv_path.open("a", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=scraper.CSV_FIELDS)
                with (
                    mock.patch.object(
                        scraper.asyncio, "sleep", new=mock.AsyncMock()
                    ),
                    mock.patch("builtins.print"),
                ):
                    added = await scraper.step2_scrape_replies(
                        api=api,
                        lang="id",
                        writer=writer,
                        csv_file=handle,
                        checkpoint=checkpoint,
                        target=10,
                        delay=0,
                        batch_size=100,
                        include_nested=False,
                    )

            self.assertEqual(added, 0)
            self.assertEqual(checkpoint.root_status[ROOT_ID], "invalid_root")
            self.assertEqual(api.reply_calls, 1)
            self.assertEqual(api.detail_calls, 0)

    async def test_direct_then_nested_mode_tracks_exhaustion_separately(self):
        direct = make_tweet(
            DIRECT_ID,
            conversation_id=ROOT_ID,
            parent_id=ROOT_ID,
        )
        nested = make_tweet(
            NESTED_ID,
            conversation_id=ROOT_ID,
            parent_id=PARENT_ID,
        )
        outside = make_tweet(
            FOREIGN_ID,
            conversation_id=FOREIGN_ID,
            parent_id=ROOT_ID,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            csv_path = root / "dataset.csv"
            checkpoint = scraper.Checkpoint(root / "checkpoint.json")
            checkpoint.seen_ids = {ROOT_ID}
            checkpoint.step2_queue = {ROOT_ID: "MBG[Latest]"}
            checkpoint.save()
            write_canonical_csv(csv_path, [canonical_row(ROOT_ID)])

            with csv_path.open("a", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=scraper.CSV_FIELDS)
                with (
                    mock.patch.object(
                        scraper.asyncio, "sleep", new=mock.AsyncMock()
                    ),
                    mock.patch("builtins.print"),
                ):
                    direct_added = await scraper.step2_scrape_replies(
                        api=FakeReplyAPI([direct, nested, outside]),
                        lang="id",
                        writer=writer,
                        csv_file=handle,
                        checkpoint=checkpoint,
                        target=10,
                        delay=0,
                        batch_size=100,
                        include_nested=False,
                    )

            self.assertEqual(direct_added, 1)
            self.assertEqual(
                checkpoint.root_status[ROOT_ID],
                "direct_exhausted",
            )

            with csv_path.open("a", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=scraper.CSV_FIELDS)
                with (
                    mock.patch.object(
                        scraper.asyncio, "sleep", new=mock.AsyncMock()
                    ),
                    mock.patch("builtins.print"),
                ):
                    nested_added = await scraper.step2_scrape_replies(
                        api=FakeReplyAPI([direct, nested, outside]),
                        lang="id",
                        writer=writer,
                        csv_file=handle,
                        checkpoint=checkpoint,
                        target=10,
                        delay=0,
                        batch_size=100,
                        include_nested=True,
                    )

            self.assertEqual(nested_added, 1)
            self.assertEqual(
                checkpoint.root_status[ROOT_ID],
                "all_exhausted",
            )
            with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(
                [row["Tweet_ID"] for row in rows],
                [ROOT_ID, DIRECT_ID, NESTED_ID],
            )


if __name__ == "__main__":
    unittest.main()
