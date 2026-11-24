---
title: Outcome codes
lede: A reader of a bundle, a feed or a key set returns one of these codes when it refuses. The test vectors expect these exact strings.
---

## Signatures

| Code | Meaning |
|---|---|
| `bad_signature_file` | `manifest.sig` or `feed.sig` isn't the JSON the spec defines |
| `unknown_alg` | An algorithm other than `ed25519` |
| `unknown_key` | No trusted key has that publisher and id, or the reader's sources disagree about it |
| `bad_signature` | The signature doesn't verify |
| `revoked_key` | Signed by a revoked key, whatever the bundle's `published_at` |
| `publisher_mismatch` | The signature's publisher isn't the feed's |
| `unsigned_from_pinned_publisher` | An unsigned bundle or index from a publisher the reader trusts |

## Bundles

| Code | Meaning |
|---|---|
| `bad_bundle` | Zip entry names, hashes, file list or references fail, or `published_at` is wrong |
| `missing_published_at` | A bundle in a feed has no `published_at` |

## Feeds

| Code | Meaning |
|---|---|
| `bad_feed` | The index doesn't parse, isn't valid, repeats a stream, or is dated in the future |
| `stale_feed` | The index is older than the last one accepted |
| `plain_and_encrypted` | Both `feed.json` and `feed.json.age` are present |
| `download_mismatch` | A bundle's SHA-256 isn't the one the index gives |
| `wrong_feed` / `wrong_stream` | The bundle was published for a different feed or stream |
| `replay` | `published_at` isn't later than the last accepted one for the stream |

## Key sets

| Code | Meaning |
|---|---|
| `bad_key_set` | Doesn't parse or validate, repeats a key, or names another publisher |
| `bad_endorsement` | `keys.sig` fails, or is by a key that may not endorse |
| `needs_approval` | Adds a key with no valid endorsement |
| `key_set_rollback` | Older than the held set, drops a key, or clears a retired or revoked date |

Spec: [feeds.md § Outcomes]({{ site.spec }}/blob/main/spec/feeds.md#outcomes).
