"""Unit tests for signal_jsonl.py. Standard library only, no Signal data.

Run: python3 -m unittest discover -s tests -p "test_*.py"
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT = Path(__file__).resolve().parent.parent / "plugins/chat-export-for-signal/skills/signal-export/scripts/signal_jsonl.py"
spec = importlib.util.spec_from_file_location("signal_jsonl", SCRIPT)
sj = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sj)

ME, ANNA, BEN = "uuid-me", "uuid-anna", "uuid-ben"
T0 = 1_767_225_600_000  # 2026-01-01T00:00:00Z


@dataclass
class Contact:  # same attributes as sigexport.models.Contact
    id: str
    serviceId: str | None
    name: str | None
    number: str | None = None
    profile_name: str | None = None
    is_group: bool = False
    members: list[str] | None = None
    display: str | None = None
    is_owner: bool = False


@dataclass
class Raw:  # same attributes as sigexport.models.RawMessage
    conversation_id: str
    id: str
    type: str
    body: str | None
    source: str | None
    sent_at: int
    server_timestamp: int | None = None
    timestamp: int | None = None
    attachments: list[dict[str, Any]] = field(default_factory=list)
    call_history: dict[str, Any] | None = None
    reactions: list[dict[str, Any]] = field(default_factory=list)
    sticker: dict[str, Any] | None = None
    quote: dict[str, Any] | None = None
    deleted: bool = False

    def get_ts(self) -> int:
        return self.sent_at


def fixture() -> tuple[dict, dict, Contact, dict]:
    contacts = {
        "c-me": Contact("c-me", ME, "NotetoSelf", "+41000000001", "Philip"),
        "c-anna": Contact("c-anna", ANNA, "AnnaMuster", "+41000000002", "Anna"),
        "c-ben": Contact("c-ben", BEN, "Ben", None, "Ben"),
        "c-grp": Contact("c-grp", None, "FamilyGroup", is_group=True, members=[ME, ANNA, "c-ben"]),
    }
    names = {"c-me": "Philip", "c-anna": "Anna Muster", "c-ben": "Ben", "c-grp": "Family Group"}
    convos = {
        "c-anna": [
            Raw("c-anna", "m1", "incoming", "Hi!", None, T0 + 60_000),
            Raw(
                "c-anna", "m2", "outgoing", "Hello", None, T0 + 120_000,
                quote={"id": T0 + 60_000, "authorAci": ANNA, "text": "Hi!"},
                reactions=[{"emoji": "❤️", "fromId": "c-anna", "timestamp": T0 + 130_000}],
            ),
        ],
        "c-grp": [
            Raw(
                "c-grp", "m3", "incoming", "Look", BEN, T0 + 300_000,
                attachments=[{"fileName": "beach day.jpg", "contentType": "image/jpeg", "size": 11, "path": "ab/cd"}],
            ),
            Raw("c-grp", "m4", "incoming", "From a stranger", "uuid-unknown", T0 + 200_000),
        ],
    }
    return convos, contacts, contacts["c-me"], names


class BuildRecordsTest(unittest.TestCase):
    def setUp(self) -> None:
        convos, contacts, owner, names = fixture()
        self.people, self.chats, self.messages = sj.build_records(convos, contacts, owner, names)
        self.msg = {m["message_id"]: m for m in self.messages}

    def test_people_use_service_ids_and_mark_me_first(self) -> None:
        self.assertEqual(self.people[0]["person_id"], ME)
        self.assertTrue(self.people[0]["is_me"])
        self.assertEqual({p["person_id"] for p in self.people}, {ME, ANNA, BEN})
        anna = next(p for p in self.people if p["person_id"] == ANNA)
        self.assertEqual(anna["name"], "Anna Muster")
        self.assertEqual(anna["conversation_id"], "c-anna")

    def test_group_members_resolve_by_service_or_conversation_id(self) -> None:
        group = next(c for c in self.chats if c["chat_id"] == "c-grp")
        self.assertEqual(group["type"], "group")
        self.assertEqual(group["member_ids"], [ME, ANNA, BEN])
        self.assertIsNone(group["person_id"])

    def test_direct_chat_and_counts(self) -> None:
        anna = next(c for c in self.chats if c["chat_id"] == "c-anna")
        self.assertEqual(anna["type"], "direct")
        self.assertEqual(anna["name"], "Anna Muster")
        self.assertEqual(anna["folder"], "AnnaMuster")
        self.assertEqual(anna["member_ids"], [ME, ANNA])
        self.assertEqual(anna["message_count"], 2)
        self.assertEqual(anna["first_message_at"], "2026-01-01T00:01:00.000Z")

    def test_senders_and_directions(self) -> None:
        self.assertEqual(self.msg["m1"]["sender_id"], ANNA)  # direct chat: no source needed
        self.assertEqual(self.msg["m1"]["direction"], "incoming")
        self.assertEqual(self.msg["m2"]["sender_id"], ME)
        self.assertEqual(self.msg["m2"]["sender_name"], "Me")
        self.assertEqual(self.msg["m3"]["sender_id"], BEN)
        self.assertEqual(self.msg["m4"]["sender_id"], "uuid-unknown")  # kept, though unknown

    def test_signal_keys_link_replies(self) -> None:
        self.assertEqual(self.msg["m1"]["signal_key"], f"{ANNA}:{T0 + 60_000}")
        self.assertEqual(self.msg["m2"]["reply_to"]["signal_key"], self.msg["m1"]["signal_key"])
        self.assertEqual(self.msg["m2"]["reply_to"]["author_id"], ANNA)

    def test_reactions(self) -> None:
        reaction = self.msg["m2"]["reactions"][0]
        self.assertEqual(reaction["person_id"], ANNA)
        self.assertEqual(reaction["emoji"], "❤️")
        self.assertEqual(reaction["reacted_at"], "2026-01-01T00:02:10.000Z")

    def test_timestamps_are_utc_iso(self) -> None:
        self.assertEqual(self.msg["m1"]["sent_at"], "2026-01-01T00:01:00.000Z")
        self.assertEqual(self.msg["m1"]["sent_at_ms"], T0 + 60_000)

    def test_messages_sorted_by_time(self) -> None:
        times = [m["sent_at_ms"] for m in self.messages]
        self.assertEqual(times, sorted(times))

    def test_attachment_path_points_into_chat_folder(self) -> None:
        att = self.msg["m3"]["attachments"][0]
        self.assertEqual(att["file_name"], "beach day.jpg")
        self.assertEqual(att["content_type"], "image/jpeg")
        self.assertTrue(att["path"].startswith("FamilyGroup/media/"))
        self.assertTrue(att["path"].endswith("_00_beach_day.jpg"))

    def test_no_attachment_paths_when_not_exported(self) -> None:
        convos, contacts, owner, names = fixture()
        _, _, messages = sj.build_records(convos, contacts, owner, names, attachments_exported=False)
        att = next(m for m in messages if m["message_id"] == "m3")["attachments"][0]
        self.assertIsNone(att["path"])

    def test_note_to_self_has_single_member(self) -> None:
        convos, contacts, owner, names = fixture()
        convos["c-me"] = [Raw("c-me", "m9", "outgoing", "memo", None, T0)]
        _, chats, _ = sj.build_records(convos, contacts, owner, names)
        note = next(c for c in chats if c["chat_id"] == "c-me")
        self.assertEqual(note["name"], "Note to Self")
        self.assertEqual(note["member_ids"], [ME])


class ExportedFileNameTest(unittest.TestCase):
    def local(self, ms: int) -> str:
        return datetime.fromtimestamp(ms / 1000).isoformat(timespec="milliseconds").replace(":", "-")

    def test_mirrors_signal_export_naming(self) -> None:
        name = sj.exported_file_name({"fileName": "a b,c?.jpg"}, T0, 3)
        self.assertEqual(name, f"{self.local(T0)}_03_a_bc_.jpg")

    def test_adds_extension_from_content_type(self) -> None:
        name = sj.exported_file_name({"fileName": "voice", "contentType": "audio/aac"}, T0, 0)
        self.assertTrue(name.endswith("_00_voice.aac"))

    def test_missing_file_name(self) -> None:
        name = sj.exported_file_name({"contentType": "image/png"}, T0, 1)
        self.assertTrue(name.endswith("_01_None.png"))


class WriteOutputsTest(unittest.TestCase):
    def test_files_manifest_and_checksums(self) -> None:
        convos, contacts, owner, names = fixture()
        people, chats, messages = sj.build_records(convos, contacts, owner, names)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            manifest = sj.write_outputs(
                out, people, chats, messages,
                exporter_version="3.9.3",
                filters={"chats": None, "since": None, "until": None, "include_disappearing": False},
                owner_id=ME,
                platform="test",
                now=datetime(2026, 10, 20, 9, 0, tzinfo=timezone.utc),
            )
            on_disk = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(on_disk, manifest)
            self.assertEqual(manifest["schema_version"], "1.0")
            self.assertEqual(manifest["created_at"], "2026-10-20T09:00:00Z")
            self.assertEqual(manifest["counts"], {"people": 3, "chats": 2, "messages": 4})
            for name in ("people.jsonl", "chats.jsonl", "messages.jsonl"):
                data = (out / name).read_bytes()
                self.assertEqual(manifest["files"][name]["sha256"], hashlib.sha256(data).hexdigest())
                lines = data.decode("utf-8").splitlines()
                self.assertEqual(len(lines), manifest["files"][name]["records"])
                for line in lines:
                    json.loads(line)  # every line is valid JSON
            self.assertIn("Anna Muster", (out / "people.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(sorted(p.name for p in out.iterdir()),
                             ["chats.jsonl", "manifest.json", "messages.jsonl", "people.jsonl"])


if __name__ == "__main__":
    unittest.main()
