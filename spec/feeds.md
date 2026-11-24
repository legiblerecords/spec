# Feeds

Status: draft. This file holds the table of outcome codes for now; the rest of the feeds spec is still to come.

## Outcomes

A reader of a bundle, a feed or a key set returns one of these codes when it refuses, and [the test vectors](../vectors/) expect them by these exact strings.

| Code | Meaning |
|---|---|
| `bad_signature_file` | `manifest.sig`, `feed.sig` or `keys.sig` isn't the JSON the spec defines. |
| `unknown_alg` | `alg` isn't `ed25519`. |
| `unknown_key` | No trusted key has that publisher and id. |
| `bad_signature` | The signature doesn't verify. |
| `revoked_key` | Signed by a revoked key, whatever the bundle's `published_at`. |
| `publisher_mismatch` | The signature's publisher isn't the feed's publisher. |
| `unsigned_from_pinned_publisher` | An unsigned bundle or feed index from a publisher with a pinned key. |
| `stale_feed` | `feed.json` `updated_at` is earlier than the last one accepted. |
| `plain_and_encrypted` | Both `feed.json` and `feed.json.age` are present. |
| `download_mismatch` | A bundle file's SHA-256 isn't the one `feed.json` gives. |
| `bad_bundle` | The bundle fails the bundle checks: hashes, file list or references. |
| `missing_published_at` | A signed bundle in a feed has no `published_at`. |
| `wrong_feed` / `wrong_stream` | The signed manifest's `feed.id` or `feed.stream` doesn't match where it was found. |
| `replay` | `published_at` isn't later than the last accepted one for the stream. |
| `bad_endorsement` | `keys.sig` doesn't verify, or is by a key that may not endorse. |
| `needs_approval` | A key set adds a key with no valid endorsement. |
| `key_set_rollback` | A key set is older than the held one, drops a held key, or clears a held key's retired or revoked date. |
| `bad_key_set` | A key set doesn't parse, or repeats a key id. |
