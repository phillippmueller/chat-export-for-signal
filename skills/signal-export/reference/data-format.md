# Machine-readable data format (schema 1.0)

Every export (unless run with `--no-data`) contains four files next to the
chat folders:

| File | Contents |
| :- | :- |
| `manifest.json` | What the export contains: versions, filters, counts, time span, checksums |
| `people.jsonl` | One line per person |
| `chats.jsonl` | One line per chat |
| `messages.jsonl` | One line per message, oldest first |

The `.jsonl` files are [JSON Lines](https://jsonlines.org/): one complete JSON
object per line, UTF-8. Each file maps to one database table, and the IDs
link them like foreign keys:

```
people.person_id  <-  chats.person_id, chats.member_ids[],
                      messages.sender_id, messages.reactions[].person_id,
                      messages.reply_to.author_id
chats.chat_id     <-  messages.chat_id
```

All timestamps are ISO-8601 in UTC (`2026-01-01T00:01:00.000Z`). Messages
also carry `sent_at_ms`, Signal's raw millisecond timestamp.

## Which ID to use

| ID | Stable across | Use it for |
| :- | :- | :- |
| `person_id` | everything: devices, name and number changes | identifying people |
| `signal_key` | devices and reinstalls | de-duplicating messages from different sources |
| `message_id` | exports from the same computer | upserting repeated exports |
| `chat_id` | exports from the same computer | linking messages to chats |

- `person_id` is the person's Signal service ID (ACI UUID). If Signal Desktop
  doesn't know it, the local conversation ID is used instead.
- `signal_key` is `<sender service ID>:<sent_at_ms>`. This is how Signal
  itself identifies a message across devices, for example in replies.
- `message_id` and `chat_id` are Signal Desktop's local IDs. They stay the same
  between exports on the same computer, but differ after relinking Signal
  Desktop or on another computer.

To load repeated exports without duplicates, upsert on `message_id`, or on
`signal_key` when combining data from several computers.

## manifest.json

```json
{
  "schema_version": "1.0",
  "generator": {"name": "chat-export-for-signal", "version": "0.3.0", "url": "..."},
  "created_at": "2026-10-20T09:21:23Z",
  "source": {"app": "Signal Desktop", "exporter": "signal-export",
             "exporter_version": "3.9.3", "platform": "darwin"},
  "owner_id": "<your person_id>",
  "filters": {"chats": ["Anna Muster"], "since": null, "until": null,
              "include_disappearing": false},
  "counts": {"people": 3, "chats": 1, "messages": 1520},
  "period": {"first_message_at": "...", "last_message_at": "..."},
  "files": {
    "messages.jsonl": {"format": "jsonl", "records": 1520, "sha256": "..."}
  }
}
```

Check `schema_version` before loading. A change in the major number (2.0)
means fields were renamed or removed; a minor change (1.1) only adds fields.
The `sha256` values let you verify that no file was changed or cut off.

## people.jsonl

| Field | Type | Meaning |
| :- | :- | :- |
| `person_id` | string | Stable ID (see above) |
| `service_id` | string or null | Signal service ID (ACI) |
| `conversation_id` | string | Signal Desktop's local ID for this person |
| `name` | string or null | Name as saved in your contacts, else profile name; "Me" for you |
| `profile_name` | string or null | Name the person set in their Signal profile |
| `phone` | string or null | Phone number in E.164 format, if known |
| `is_me` | boolean | True for the account owner |

## chats.jsonl

| Field | Type | Meaning |
| :- | :- | :- |
| `chat_id` | string | Signal Desktop's ID for the chat |
| `name` | string or null | Contact or group name; "Note to Self" for your own notes |
| `type` | `"direct"` or `"group"` | |
| `folder` | string | The chat's folder in this export (HTML, Markdown, media) |
| `person_id` | string or null | The other person, for direct chats |
| `member_ids` | list of strings | People in the chat, you included |
| `message_count` | integer | Messages exported for this chat |
| `first_message_at`, `last_message_at` | string or null | Time span of the exported messages |

## messages.jsonl

| Field | Type | Meaning |
| :- | :- | :- |
| `message_id` | string | Signal Desktop's ID for the message |
| `signal_key` | string or null | Cross-device message key (see above) |
| `chat_id` | string | Chat the message belongs to |
| `sender_id` | string or null | `person_id` of the sender |
| `sender_name` | string or null | Sender's name at export time; "Me" for you |
| `direction` | `"incoming"` or `"outgoing"` | |
| `type` | string | Signal's message type, e.g. `incoming`, `outgoing`, `call-history` |
| `sent_at` | string or null | When the message was sent (UTC) |
| `sent_at_ms` | integer or null | Same, as Unix milliseconds |
| `server_received_at` | string or null | When Signal's server received it |
| `text` | string | Message text, empty if there is none |
| `reply_to` | object or null | The message this one replies to (below) |
| `reactions` | list | Emoji reactions (below) |
| `attachments` | list | Files sent with the message (below) |
| `sticker` | object or null | `emoji`, `pack_id`, `sticker_id` |
| `call` | object or null | Call details for call entries, as Signal stores them |
| `deleted` | boolean | Deleted for everyone |

`reply_to`: `signal_key` and `sent_at` of the quoted message, `author_id`,
the quoted `text`, and `found` (false if Signal no longer has the original).

`reactions[]`: `emoji`, `person_id`, `name`, `reacted_at`.

`attachments[]`: original `file_name`, `content_type`, `size_bytes`, and
`path`, the file's location relative to the export folder (null when the
export ran with `--no-attachments`).

## Examples

DuckDB, straight from the files:

```sql
SELECT p.name, count(*) AS messages
FROM 'messages.jsonl' m JOIN 'people.jsonl' p ON m.sender_id = p.person_id
GROUP BY p.name ORDER BY messages DESC;
```

pandas:

```python
import pandas as pd
messages = pd.read_json("messages.jsonl", lines=True)
```

PostgreSQL, keeping each record as JSONB and upserting repeated exports:

```sql
CREATE TABLE signal_messages (message_id text PRIMARY KEY, data jsonb);
-- for each line of messages.jsonl:
INSERT INTO signal_messages VALUES ($1, $2)
ON CONFLICT (message_id) DO UPDATE SET data = EXCLUDED.data;
```

## Notes

- The data files always cover everything Signal Desktop currently holds for
  the selected chats and dates, also in `update` mode. They are not merged
  with the earlier export; upsert them into your database instead.
- Messages from disappearing chats and empty chats are left out unless the
  export passes `-- --include-disappearing` or `-- --include-empty`.
- Like the rest of the export, these files contain private messages and
  phone numbers, unencrypted.
