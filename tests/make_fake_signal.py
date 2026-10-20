"""Create a small, fake Signal Desktop data folder for end-to-end tests.

The database is encrypted with SQLCipher like the real one, but its key sits
in plain text in config.json (Signal's legacy format), so no keychain is
needed. All people and messages are invented.

Usage (needs the signal-export package, which brings sqlcipher3):
    uv tool run --from signal-export==3.9.3 python tests/make_fake_signal.py DIR
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlcipher3 import dbapi2

KEY = "00" * 32
ME = "aaaaaaaa-0000-4000-8000-000000000001"
ANNA = "aaaaaaaa-0000-4000-8000-000000000002"
BEN = "aaaaaaaa-0000-4000-8000-000000000003"
T0 = 1_767_225_600_000  # 2026-01-01T00:00:00Z in milliseconds


def build(folder: Path) -> None:
    (folder / "sql").mkdir(parents=True, exist_ok=True)
    (folder / "config.json").write_text(json.dumps({"key": KEY}), encoding="utf-8")

    db = dbapi2.connect(str(folder / "sql" / "db.sqlite"))
    c = db.cursor()
    c.execute(f"PRAGMA KEY = \"x'{KEY}'\"")
    c.execute("PRAGMA cipher_page_size = 4096")
    c.execute("PRAGMA kdf_iter = 64000")
    c.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512")
    c.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512")

    c.execute(
        "CREATE TABLE conversations (id TEXT, type TEXT, serviceId TEXT, e164 TEXT,"
        " name TEXT, profileName TEXT, members TEXT, json TEXT)"
    )
    c.execute(
        "CREATE TABLE messages (id TEXT, conversationId TEXT, type TEXT, json TEXT,"
        " body TEXT, sourceServiceId TEXT, timestamp INTEGER, sent_at INTEGER,"
        " serverTimestamp INTEGER, hasAttachments INTEGER, readStatus INTEGER,"
        " seenStatus INTEGER, expireTimer INTEGER)"
    )
    c.execute("CREATE TABLE sessions (ourServiceId TEXT)")
    c.execute("INSERT INTO sessions VALUES (?)", (ME,))
    c.execute(
        "CREATE TABLE sticker_packs (id TEXT, key TEXT, author TEXT, coverStickerId INTEGER,"
        " createdAt INTEGER, downloadAttempts INTEGER, installedAt INTEGER, lastUsed INTEGER,"
        " status TEXT, stickerCount INTEGER, title TEXT, attemptedStatus TEXT, position INTEGER,"
        " storageID TEXT, storageVersion INTEGER, storageUnknownFields BLOB, storageNeedsSync INTEGER)"
    )
    c.execute("CREATE TABLE stickers (id INTEGER, packId TEXT, emoji TEXT, height INTEGER,"
              " isCoverOnly INTEGER, lastUsed INTEGER, path TEXT, width INTEGER, version INTEGER,"
              " localKey TEXT, size INTEGER)")

    # Newer Signal versions (database version 1360+) keep attachments in their
    # own table instead of inside each message's JSON.
    c.execute("PRAGMA user_version = 1360")
    c.execute(
        "CREATE TABLE message_attachments (messageId TEXT, editHistoryIndex INTEGER,"
        " attachmentType TEXT, orderInMessage INTEGER, size INTEGER, contentType TEXT,"
        " path TEXT, fileName TEXT, localKey TEXT, version INTEGER, pending INTEGER)"
    )
    c.execute(
        "INSERT INTO message_attachments VALUES"
        " ('m3', -1, 'attachment', 0, 11, 'image/jpeg', 'ab/abcdef', 'beach.jpg', NULL, 1, 0)"
    )
    media = folder / "attachments.noindex" / "ab"
    media.mkdir(parents=True, exist_ok=True)
    (media / "abcdef").write_bytes(b"fake-jpeg!\n")

    conversations = [
        ("conv-me", "private", ME, "+41790000001", "Philip", "Philip", None, "{}"),
        ("conv-anna", "private", ANNA, "+41790000002", "Anna Muster", "Anna", None, "{}"),
        ("conv-ben", "private", BEN, "+41790000003", None, "Ben", None, "{}"),
        ("conv-group", "group", None, None, "Family Group", None, f"{ME} {ANNA} {BEN}", "{}"),
    ]
    c.executemany("INSERT INTO conversations VALUES (?,?,?,?,?,?,?,?)", conversations)

    def msg(mid, conv, mtype, body, source, offset_s, extra=None, has_attachments=0):
        sent = T0 + offset_s * 1000
        data = extra or {}
        return (mid, conv, mtype, json.dumps(data), body, source, sent, sent, sent + 50,
                has_attachments, None, None, None)

    messages = [
        msg("m1", "conv-anna", "incoming", "Hi! Are we still on for Friday?", ANNA, 60),
        msg("m2", "conv-anna", "outgoing", "Yes, 7pm 🙂", ME, 120,
            {"quote": {"id": T0 + 60_000, "authorAci": ANNA, "text": "Hi! Are we still on for Friday?"},
             "reactions": [{"emoji": "❤️", "fromId": "conv-anna", "timestamp": T0 + 130_000}]}),
        msg("m3", "conv-group", "incoming", "Photos from the weekend", BEN, 300, has_attachments=1),
        msg("m4", "conv-group", "outgoing", "Lovely!", ME, 360,
            {"reactions": [{"emoji": "👍", "fromId": "conv-ben", "timestamp": T0 + 400_000}]}),
        msg("m5", "conv-anna", "keychange", None, None, 30),  # skipped like upstream
        msg("m6", "conv-me", "outgoing", "Reminder: buy milk", ME, 500),
    ]
    c.executemany("INSERT INTO messages VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", messages)
    db.commit()
    db.close()


if __name__ == "__main__":
    build(Path(sys.argv[1]))
