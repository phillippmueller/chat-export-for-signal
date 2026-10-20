#!/usr/bin/env python3
"""Write machine-readable files for a Signal Desktop export.

Reads Signal Desktop's local database through the signal-export package and
writes, into the export folder:

    people.jsonl    one record per person (stable IDs, names, phone numbers)
    chats.jsonl     one record per chat (stable IDs, type, members, counts)
    messages.jsonl  one record per message (stable IDs, sender, timestamps,
                    text, replies, reactions, attachments)
    manifest.json   what the export contains: versions, filters, counts and
                    a SHA-256 checksum for each file

Each .jsonl file holds one JSON object per line, so it can be streamed into a
database (Postgres, DuckDB, SQLite), pandas or an AI pipeline line by line.
The schema is documented in reference/data-format.md.

Normally run by signal-export.sh through uv, which supplies the signal-export
package. The conversion itself (build_records) uses only the standard library.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
GENERATOR = {
    "name": "signal-skill",
    "version": "0.2.0",
    "url": "https://github.com/phillippmueller/signal-skill",
}

JsonDict = dict[str, Any]


# --------------------------------------------------------------- helpers ---


def ms_to_iso(ms: int | None) -> str | None:
    """Convert Signal's millisecond Unix timestamps to ISO-8601 UTC."""
    if not ms:
        return None
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def person_id(contact: Any) -> str:
    """The stable ID for a person: their Signal service ID (ACI) when known.

    The service ID is the same on every device and survives name and phone
    number changes. Signal Desktop's conversation ID is the fallback; it is
    stable on this computer only.
    """
    return contact.serviceId or contact.id


class Lookup:
    """Finds contacts by conversation ID or service ID."""

    def __init__(self, contacts: dict[str, Any]) -> None:
        self.by_id = dict(contacts)
        self.by_service_id = {c.serviceId: c for c in contacts.values() if c.serviceId}

    def find(self, key: str | None) -> Any | None:
        if not key:
            return None
        return self.by_id.get(key) or self.by_service_id.get(key)


# ------------------------------------------------------------ conversion ---


def build_records(
    convos: dict[str, list[Any]],
    contacts: dict[str, Any],
    owner: Any | None,
    names: dict[str, str | None],
    attachments_exported: bool = True,
) -> tuple[list[JsonDict], list[JsonDict], list[JsonDict]]:
    """Turn signal-export's raw data into people, chat and message records.

    convos:   conversation ID -> raw messages (signal-export RawMessage)
    contacts: conversation ID -> contact (signal-export Contact), with folder
              names already made unique
    owner:    the contact of the account owner, if known
    names:    conversation ID -> human-readable name, taken before the folder
              names were made filesystem-safe
    attachments_exported: whether the files were copied into the export, so
              each attachment record can point to its file
    """
    lookup = Lookup(contacts)
    people: dict[str, JsonDict] = {}

    def add_person(contact: Any | None) -> str | None:
        if contact is None or contact.is_group:
            return None
        pid = person_id(contact)
        if pid not in people:
            is_me = owner is not None and contact.id == owner.id
            people[pid] = {
                "person_id": pid,
                "service_id": contact.serviceId,
                "conversation_id": contact.id,
                "name": "Me" if is_me else names.get(contact.id),
                "profile_name": contact.profile_name,
                "phone": contact.number,
                "is_me": is_me,
            }
        return pid

    owner_pid = add_person(owner)
    messages: list[JsonDict] = []
    chats: list[JsonDict] = []

    for cid, raw_messages in convos.items():
        chat = contacts[cid]
        member_ids: list[str] = []
        if chat.is_group:
            for member in chat.members or []:
                pid = add_person(lookup.find(member))
                if pid and pid not in member_ids:
                    member_ids.append(pid)
        else:
            pid = add_person(chat)
            # dict.fromkeys de-duplicates "Note to Self", where both are you
            member_ids = list(dict.fromkeys(p for p in (owner_pid, pid) if p))

        sent_times: list[int] = []
        for raw in raw_messages:
            record = message_record(raw, chat, lookup, owner, owner_pid, add_person, names, attachments_exported)
            messages.append(record)
            if record["sent_at_ms"]:
                sent_times.append(record["sent_at_ms"])

        chats.append(
            {
                "chat_id": cid,
                "name": "Note to Self" if owner is not None and cid == owner.id else names.get(cid),
                "type": "group" if chat.is_group else "direct",
                "folder": chat.name,
                "person_id": None if chat.is_group else person_id(chat),
                "member_ids": member_ids,
                "message_count": len(raw_messages),
                "first_message_at": ms_to_iso(min(sent_times)) if sent_times else None,
                "last_message_at": ms_to_iso(max(sent_times)) if sent_times else None,
            }
        )

    messages.sort(key=lambda m: (m["sent_at_ms"] or 0, m["chat_id"], m["message_id"]))
    chats.sort(key=lambda c: (c["name"] or "", c["chat_id"]))
    people_list = sorted(people.values(), key=lambda p: (not p["is_me"], p["name"] or "", p["person_id"]))
    return people_list, chats, messages


def message_record(
    raw: Any,
    chat: Any,
    lookup: Lookup,
    owner: Any | None,
    owner_pid: str | None,
    add_person: Any,
    names: dict[str, str | None],
    attachments_exported: bool = True,
) -> JsonDict:
    call = raw.call_history if isinstance(raw.call_history, dict) else None
    outgoing = raw.type == "outgoing" or (
        raw.type == "call-history" and call is not None and call.get("direction") == "Outgoing"
    )

    if outgoing:
        sender = owner
    elif raw.source:
        sender = lookup.find(raw.source)
    elif not chat.is_group:
        sender = chat
    else:
        sender = None

    sender_id = owner_pid if outgoing else add_person(sender)
    if sender_id is None and raw.source:
        sender_id = raw.source  # known ID, but no contact entry for it

    if outgoing:
        sender_name = "Me"
    elif sender is not None:
        sender_name = names.get(sender.id)
    else:
        sender_name = None

    sent_ms = raw.get_ts() or None
    service_id = sender.serviceId if sender is not None else (raw.source or None)

    return {
        "message_id": raw.id,
        "signal_key": f"{service_id}:{raw.sent_at}" if service_id and raw.sent_at else None,
        "chat_id": raw.conversation_id,
        "sender_id": sender_id,
        "sender_name": sender_name,
        "direction": "outgoing" if outgoing else "incoming",
        "type": raw.type,
        "sent_at": ms_to_iso(sent_ms),
        "sent_at_ms": sent_ms,
        "server_received_at": ms_to_iso(raw.server_timestamp),
        "text": raw.body or "",
        "reply_to": quote_record(raw.quote, lookup, add_person),
        "reactions": reaction_records(raw.reactions, lookup, owner, add_person, names),
        "attachments": attachment_records(
            raw.attachments, sent_ms, chat.name if attachments_exported else None
        ),
        "sticker": sticker_record(raw.sticker),
        "call": call,
        "deleted": bool(raw.deleted),
    }


def quote_record(quote: Any, lookup: Lookup, add_person: Any) -> JsonDict | None:
    if not isinstance(quote, dict):
        return None
    author = quote.get("authorAci") or quote.get("authorUuid") or quote.get("author")
    author_id = add_person(lookup.find(author)) or author
    sent_ms = quote.get("id")
    return {
        "signal_key": f"{author}:{sent_ms}" if author and sent_ms else None,
        "author_id": author_id,
        "sent_at": ms_to_iso(sent_ms) if isinstance(sent_ms, int) else None,
        "text": quote.get("text") or "",
        "found": not quote.get("referencedMessageNotFound", False),
    }


def reaction_records(
    reactions: Iterable[Any] | None,
    lookup: Lookup,
    owner: Any | None,
    add_person: Any,
    names: dict[str, str | None],
) -> list[JsonDict]:
    records = []
    for reaction in reactions or []:
        if not isinstance(reaction, dict):
            continue
        reactor = lookup.find(reaction.get("fromId"))
        is_me = owner is not None and reactor is not None and reactor.id == owner.id
        records.append(
            {
                "emoji": reaction.get("emoji"),
                "person_id": add_person(reactor) or reaction.get("fromId"),
                "name": "Me" if is_me else (names.get(reactor.id) if reactor else None),
                "reacted_at": ms_to_iso(reaction.get("timestamp")),
            }
        )
    return records


def attachment_records(
    attachments: Iterable[Any] | None, sent_ms: int | None, folder: str | None
) -> list[JsonDict]:
    """Describe attachments; with a folder, also give each file's path in the export."""
    records = []
    for index, att in enumerate(attachments or []):
        if not isinstance(att, dict):
            continue
        path = None
        if folder is not None and att.get("path"):
            path = f"{folder}/media/{exported_file_name(att, sent_ms, index)}"
        records.append(
            {
                "file_name": att.get("fileName"),
                "content_type": att.get("contentType"),
                "size_bytes": att.get("size"),
                "path": path,
            }
        )
    return records


def exported_file_name(att: dict[str, Any], sent_ms: int | None, index: int) -> str:
    """The name signal-export 3.9.x gives an attachment in the media folder.

    Mirrors sigexport.files.copy_attachments: local send time, position in the
    message, then the original file name, made filesystem-safe.
    """
    file_name = str(att["fileName"]) if "fileName" in att else "None"
    overlength = len(file_name) > 200
    if overlength:
        file_name = file_name[:200]
    if "." not in file_name or overlength:
        content_type = (att.get("contentType") or "").split("/")
        file_name += "." + (content_type[1] if len(content_type) > 1 else content_type[0])
    date = (
        datetime.fromtimestamp((sent_ms or 0) / 1000)
        .isoformat(timespec="milliseconds")
        .replace(":", "-")
    )
    name = f"{date}_{index:02}_{file_name}"
    for old, new in (
        (" ", "_"), ("/", "-"), (",", ""), (":", "-"), ("|", "-"), ("*", "_"),
        ("\\", "-"), ("<", "_"), (">", "_"), ('"', "_"), ("?", "_"),
    ):
        name = name.replace(old, new)
    return name


def sticker_record(sticker: Any) -> JsonDict | None:
    if not isinstance(sticker, dict):
        return None
    return {
        "emoji": sticker.get("emoji"),
        "pack_id": sticker.get("packId"),
        "sticker_id": sticker.get("stickerId"),
    }


# ---------------------------------------------------------------- output ---


def write_jsonl(path: Path, records: Iterable[JsonDict]) -> tuple[int, str]:
    """Write records atomically; return (record count, SHA-256 hex digest)."""
    digest = hashlib.sha256()
    count = 0
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            for record in records:
                line = json.dumps(record, ensure_ascii=False, sort_keys=False) + "\n"
                f.write(line)
                digest.update(line.encode("utf-8"))
                count += 1
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return count, digest.hexdigest()


def write_outputs(
    out: Path,
    people: list[JsonDict],
    chats: list[JsonDict],
    messages: list[JsonDict],
    *,
    exporter_version: str,
    filters: JsonDict,
    owner_id: str | None,
    platform: str,
    now: datetime | None = None,
) -> JsonDict:
    out.mkdir(parents=True, exist_ok=True)
    files: JsonDict = {}
    for name, records in (
        ("people.jsonl", people),
        ("chats.jsonl", chats),
        ("messages.jsonl", messages),
    ):
        count, sha256 = write_jsonl(out / name, records)
        files[name] = {"format": "jsonl", "records": count, "sha256": sha256}

    times = [m["sent_at_ms"] for m in messages if m["sent_at_ms"]]
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generator": GENERATOR,
        "created_at": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "source": {
            "app": "Signal Desktop",
            "exporter": "signal-export",
            "exporter_version": exporter_version,
            "platform": platform,
        },
        "owner_id": owner_id,
        "filters": filters,
        "counts": {"people": len(people), "chats": len(chats), "messages": len(messages)},
        "period": {
            "first_message_at": ms_to_iso(min(times)) if times else None,
            "last_message_at": ms_to_iso(max(times)) if times else None,
        },
        "files": files,
    }
    fd, tmp = tempfile.mkstemp(dir=out, prefix=".manifest.json.")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, out / "manifest.json")
    return manifest


# ------------------------------------------------------------ signal I/O ---


def load_from_signal(args: argparse.Namespace) -> tuple[Any, Any, Any, dict[str, str | None]]:
    """Read Signal Desktop's database with the signal-export package."""
    from sigexport import data, files, utils
    from sigexport.main import parse_input_dt

    source = Path(args.source).expanduser() if args.source else utils.source_location()
    cursor = data.get_signal_database(source, password=None, key=None)
    convos, contacts, owner = data.fetch_data(
        source,
        cursor,
        chats=args.chats or "",
        include_empty=args.include_empty,
        include_disappearing=args.include_disappearing,
        start_date=parse_input_dt(args.since) if args.since else None,
        end_date=parse_input_dt(args.until) if args.until else None,
    )
    # Signal 7.x+ (database version 1360+) keeps attachments in their own
    # table, which signal-export only reads while copying files. Read it here.
    db_version = cursor.execute("PRAGMA user_version").fetchone()[0]
    if db_version and db_version >= 1360:
        for raw_messages in convos.values():
            for raw in raw_messages:
                raw.attachments = files.get_attachments_from_db(cursor, raw.id)

    names = {cid: c.name for cid, c in contacts.items()}
    # Same steps as signal-export's main(), so folder names match the
    # HTML/Markdown export exactly.
    if owner is not None:
        owner.name = "Note to Self"
        owner.is_owner = True
    utils.fix_names(contacts)
    return convos, contacts, owner, names


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, help="export folder to write into")
    parser.add_argument("--source", help="Signal Desktop data folder")
    parser.add_argument("--chats", help="comma-separated chat names")
    parser.add_argument("--since", help="ISO-8601 start date")
    parser.add_argument("--until", help="ISO-8601 end date")
    parser.add_argument("--include-empty", action="store_true")
    parser.add_argument("--include-disappearing", action="store_true")
    parser.add_argument(
        "--no-attachments",
        action="store_true",
        help="attachments were not copied, so give them no path",
    )
    parser.add_argument("--exporter-version", default="unknown")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    convos, contacts, owner, names = load_from_signal(args)
    people, chats, messages = build_records(
        convos, contacts, owner, names, attachments_exported=not args.no_attachments
    )
    manifest = write_outputs(
        Path(args.out).expanduser(),
        people,
        chats,
        messages,
        exporter_version=args.exporter_version,
        filters={
            "chats": [c for c in (args.chats or "").split(",") if c] or None,
            "since": args.since,
            "until": args.until,
            "include_disappearing": args.include_disappearing,
        },
        owner_id=person_id(owner) if owner is not None else None,
        platform=sys.platform,
    )
    counts = manifest["counts"]
    print(
        f"Wrote machine-readable data: {counts['messages']} messages, "
        f"{counts['chats']} chats, {counts['people']} people (see manifest.json)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
