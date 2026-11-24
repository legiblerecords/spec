# Feeds

Status: draft.

A **feed** is how a publisher offers records to a reader that polls for them: a set of named **streams**, each with exactly one current [bundle](records.md#bundles). A stream changes when its bundle is replaced, and a record that is no longer in the new bundle was removed at the source. A stream that only grows, such as policy acknowledgments, is still current state: its bundle holds all of them. A report is a stream of its own, published once and normally never replaced; withdrawing it removes the stream.

A feed has one audience and one credential. A bucket feed and an HTTP feed are the same files: an HTTP service may generate them on request, but what it serves is what a bucket would hold. A reader learns how to reach and trust a feed from a [connection file](#connection-files).

## Layout

At the feed's base URL, or under the bucket's prefix:

```
feed.json                 the feed index (feed.json.age when the feed is encrypted)
feed.sig                  optional, signs the stored feed.json (or feed.json.age) bytes
bundles/<sha256>.zip      named by the SHA-256 of the file as stored
bundles/<sha256>.zip.age
```

A feed is plain (`feed.json`) or encrypted (`feed.json.age`), never both.

## `feed.json`

The feed index is a record of type [`org.legiblerecords.feed`](../schemas/org.legiblerecords.feed/v1.yaml):

```json
{
  "$type": "org.legiblerecords.feed",
  "version": 1,
  "id": "acme.example/track",
  "publisher": "acme.example",
  "audience": "Monorail, for Track",
  "updated_at": "2026-11-24T10:00:00Z",
  "streams": [
    {
      "id": "policy-acknowledgments",
      "title": "Policy acknowledgments",
      "record_types": ["tech.monorail.policy.acknowledgment"],
      "bundle": "bundles/9f86d0….zip",
      "sha256": "9f86d0…",
      "published_at": "2026-11-24T10:00:00Z"
    }
  ]
}
```

- `id` is `<publisher>/<slug>`: a [publisher](records.md#publication-fields), `/`, and a `common.slug`. It is stable for the feed's life, and it is what a signed bundle's `feed.id` must match. `publisher` is the domain `id` starts with.
- `audience` is for people: who the feed is for. It isn't enforced; the credential is.
- `updated_at` is when the publisher wrote this index.
- A stream's `id` is a slug, unique in the feed. `record_types` lists the `$type`s the stream carries, so a reader can decide where it goes before fetching it.
- `bundle` is the bundle's path from the feed's base, `bundles/<sha256>.zip`, or `.zip.age` for an encrypted feed. `sha256` is of the file as stored (the ciphertext, for an encrypted feed), so a reader can check the download before opening it.
- `published_at` is the bundle's, as in its manifest.

**`feed.sig`** has the form of [`manifest.sig`](records.md#signed-bundles), with the context string `legible-records/v1 feed\n`, and signs the exact bytes of the stored `feed.json` file (of `feed.json.age`, for an encrypted feed). It lets a reader trust the list of streams, so a stream that vanishes was withdrawn by the publisher, not dropped by whoever can write to the storage. A publisher that signs its bundles should sign its feed too.

## Publishing

1. Write the new bundle to `bundles/<sha256>.zip` (or `.zip.age`). Paths are named by content, so this never overwrites anything.
2. Write `feed.json`, and `feed.sig`, pointing at it, with `updated_at` and the stream's `published_at` later than before. A bundle in a feed has `published_at` and `feed` in its manifest ([§ Publication fields](records.md#publication-fields)).
3. Delete a bundle that no stream points at only after a grace period of at least one hour, so a reader partway through a poll still finds it.

A publisher that removes a record at its source republishes the stream without it. A publisher that withdraws a stream removes it from `feed.json`. Neither can recall copies readers already took; that is what a reader's redaction is for.

## Reading a feed

A reader polls the feed. How often is its own choice; it should poll no more than once a minute, and a publisher may answer `429` with `Retry-After`. Each poll is checked in this order, and a refusal is one of the codes in [§ Outcomes](#outcomes).

**The index.** A refused index changes nothing: the reader keeps its state and every stream's last accepted bundle stays current.

1. Fetch `feed.json` (or `feed.json.age`), with `If-None-Match` when the source gives ETags. Unchanged: the poll is done. If both `feed.json` and `feed.json.age` are present, refuse the feed: `plain_and_encrypted`.
2. If `feed.sig` is present, verify it over the stored bytes with the `feed` context, as for a [signed bundle](records.md#reading-a-signed-bundle) (`bad_signature_file`, `unknown_alg`, `unknown_key`, `revoked_key`, `bad_signature`). The publisher it names must be the feed's, the domain its connection's `feed` starts with (`publisher_mismatch`). If it is absent and the feed's publisher is **pinned**, refuse the index: `unsigned_from_pinned_publisher`. In a feed, a publisher is pinned when the connection file pins a key for it, or the reader holds an accepted key set for it.
3. Decrypt an encrypted index. Its `id` must be the connection's `feed`, and its `publisher` the domain that `id` starts with (`wrong_feed`).
4. A reader with state refuses an `updated_at` earlier than the last one it accepted (`stale_feed`). An equal one is not stale.

**Each stream.** A failure in one stream doesn't stop the others: the reader reports it and tries again next poll, and the stream's last accepted bundle stays current.

5. A stream whose `sha256` is the last one accepted for it is **unchanged**, and isn't fetched.
6. A stream that was in the last accepted `feed.json` and isn't now is **withdrawn**. What the reader does with what it holds is its own policy.
7. Otherwise fetch the bundle and check its SHA-256 against `feed.json` (`download_mismatch`). Decrypt it if it is encrypted, then open and check it as a bundle (`bad_bundle`), including its signature as in [§ Reading a signed bundle](records.md#reading-a-signed-bundle), with the feed's publisher as the publisher it must name. An unsigned bundle from a pinned publisher is `unsigned_from_pinned_publisher`.
8. For a signed bundle: its manifest must have `published_at` (`missing_published_at`), and its `feed.id` and `feed.stream` must be the feed's `id` and the stream's `id` (`wrong_feed`, `wrong_stream`). This stops one stream's bundle being served as another's, or another feed's as this one's.
9. A reader with state refuses a signed bundle whose `published_at` isn't later than the last accepted one for the stream (`replay`). An equal `published_at` is a replay. This stops an old signed bundle being put back.
10. Otherwise the bundle is **accepted**, and becomes the stream's current bundle.

Timestamps are parsed and compared as instants, not as text: `2026-11-24T11:00:00+01:00` and `2026-11-24T10:00:00Z` are equal.

An unsigned bundle from a publisher that isn't pinned is accepted as **unverified**, and the reader says so wherever it shows it, as for any [unsigned bundle](records.md#reading-a-signed-bundle).

[vectors/feeds/](../vectors/feeds/) holds the cases, one directory each. `feed/` holds the files at the feed's base URL. `case.json` gives `name`, `connection` (a connection file), `state` (the reader state in the form below, or `null` for a stateless reader) and `expect`: `index` is `ok` or the code the index is refused with, and `streams` maps each stream id to `accepted`, `unchanged`, `withdrawn` or a code. A refused index expects no stream outcomes. The reader state in a vector is a format for the vectors, not a type:

```json
{
  "feed_updated_at": "2026-11-24T10:00:00Z",
  "streams": { "policy-acknowledgments": { "sha256": "…", "published_at": "2026-11-24T10:00:00Z" } },
  "key_sets": { "acme.example": { "$type": "org.legiblerecords.keys", "…": "…" } },
  "approved": [ { "publisher": "acme.example", "id": "2026-11", "public_key": "…" } ]
}
```

The keys a reader trusts are the connection's pins, and with state also the held key sets and the keys a person approved. Encrypted feeds have no vectors here, because age output is random; implementations test them themselves.

## Reader state

The checks above compare against what the reader accepted before. The spec says what a reader must remember, not where it keeps it:

| State | For | Per |
|---|---|---|
| `updated_at` of the last accepted `feed.json` | refusing an older feed index | feed |
| each stream's last accepted `sha256` and `published_at` | fetching only what changed, refusing replays, noticing withdrawn streams | stream |
| the last accepted [key set](records.md#key-sets), and keys a person approved | checking `keys.sig` on rotation without asking twice | publisher |
| ETag (optional) | skipping an unchanged `feed.json` | feed |

- A reader keeps no bundles (they go to its destination), no history (its destination keeps that) and no OAuth tokens (they last minutes, and fetching one per run means no secret is written to disk).
- State must be kept where the feed's writer can't change it. Someone who can write the feed and reset the reader's state can get a replay accepted.
- State changes only when something is accepted: a refused index leaves all of it as it was, and a refused stream leaves that stream's.

**A stateless reader** is allowed when what it delivers to performs the history checks instead. It skips the `stale_feed` and `replay` checks, fetches and checks every stream on every run (hash, bundle, signature, `feed.id` and `feed.stream`), and passes each bundle's `published_at` and `sha256` along. Its destination refuses a `published_at` older than the one it holds, ignores an unchanged hash, and marks withdrawn streams. A stateless reader's keys come only from its connection file: it accepts a rotated key set when `keys.sig` is by a pinned key that the new set doesn't revoke ([§ Key sets](records.md#key-sets)), and anything else waits for a person to update the connection file.

## Encrypted feeds

When a feed's bundles are encrypted with [age](records.md#encrypted-bundles), `feed.json` is too, as `feed.json.age`, so stream names such as `pentest-2026-q3` don't leak to whoever runs the storage. `feed.sig` signs the ciphertext, so a reader checks it before decrypting, and it reveals nothing about the contents: a signature over the plaintext would let anyone holding the storage confirm guesses of stream names. A bundle's `sha256` in the index is of its ciphertext too.

The recipients are the audience's age recipients. Which keys those are is decided when the feed is set up, not by this spec. The reader's identity is named by the connection file's `age_identity_env`.

A feed is either encrypted or not: a reader that finds both `feed.json` and `feed.json.age` refuses the feed (`plain_and_encrypted`), before decrypting anything.

## Access

There are three ways a reader authenticates to a feed, so that any reader can reach any publisher:

| Method | For | The reader sends |
|---|---|---|
| `bearer` | an HTTPS feed with a static token | `Authorization: Bearer <token>` |
| `oauth-client-credentials` | an HTTPS feed behind an OAuth server | a token from `token_url`, requested with `grant_type=client_credentials`, `resource` and `scope`, and fetched again before it expires |
| `s3` | any S3-compatible bucket | GETs signed with AWS Signature Version 4, with an access key that can read the prefix |

`none` is also allowed, for a public feed or one behind a network boundary.

## Connection files

A connection file is a record of type [`org.legiblerecords.feed-connection`](../schemas/org.legiblerecords.feed-connection/v1.yaml), handed from publisher to reader. It tells the reader how to reach and trust one feed.

```json
{
  "$type": "org.legiblerecords.feed-connection",
  "version": 1,
  "feed": "acme.example/track",
  "location": { "kind": "s3", "endpoint": "https://storage.acme.example", "region": "auto", "bucket": "acme-legible", "prefix": "feeds/track/" },
  "auth": { "method": "s3", "access_key_id_env": "ACME_FEED_KEY_ID", "secret_access_key_env": "ACME_FEED_SECRET" },
  "keys": [ { "publisher": "acme.example", "id": "2026-11", "alg": "ed25519", "public_key": "<base64url>" } ],
  "age_identity_env": "ACME_FEED_AGE_IDENTITY"
}
```

- `feed` is the feed's id. The feed's `feed.json` must have it.
- `location.kind` is `https`, with `url`, the feed's base URL; or `s3`, with `endpoint`, `region`, `bucket` and `prefix`, and optionally `path_style` (address the bucket in the path, not the host name; false when absent).
- `auth.method` is one of [§ Access](#access). `auth` names environment variables, never values: `token_env` for `bearer`; `token_url`, `client_id`, `client_secret_env`, `resource` and `scope` for `oauth-client-credentials`; `access_key_id_env` and `secret_access_key_env` for `s3`. The schema has a `token` field that can only be `null`, so a file with a literal token in it doesn't validate.
- `keys` pins keys, each a publisher, a key id, `alg` and a public key. Absent or empty means: use the publisher's key set, and ask before trusting it the first time ([§ Key sets](records.md#key-sets)). A publisher without a key set has its key pinned here.
- `age_identity_env` names the variable holding the reader's age identity, and is required for an encrypted feed.

The fields a `kind` or `method` needs can't be required by the schema, because the published subset has no conditionals ([rules.md](rules.md#the-published-subset)), so the reader checks them. A reader refuses a connection file that lacks a field its `kind` or `method` needs, or whose `kind` or `method` it doesn't know, before it fetches anything.

The file holds no secret, so it can be emailed, committed, or pasted into a reader's settings.

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
| `wrong_feed` / `wrong_stream` | The signed manifest's `feed.id` or `feed.stream` doesn't match where it was found, or `feed.json`'s `id` isn't the connection's `feed`. |
| `replay` | `published_at` isn't later than the last accepted one for the stream. |
| `bad_endorsement` | `keys.sig` doesn't verify, or is by a key that may not endorse. |
| `needs_approval` | A key set adds a key with no valid endorsement. |
| `key_set_rollback` | A key set is older than the held one, drops a held key, or clears a held key's retired or revoked date. |
| `bad_key_set` | A key set doesn't parse, or repeats a key id. |
