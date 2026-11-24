# Feeds

Status: draft.

A **feed** is how a publisher offers records to a reader that polls for them: a set of named **streams**, each with exactly one current [bundle](records.md#bundles). A stream changes when its bundle is replaced, and a record that is no longer in the new bundle was removed at the source. A stream that only grows, such as policy acknowledgments, is still current state: its bundle holds all of them. A report is a stream of its own, published once and normally never replaced; withdrawing it removes the stream.

A feed has one audience and one credential. A bucket feed and an HTTP feed are the same files: an HTTP service may generate them on request, but what it serves is what a bucket would hold. A reader learns how to reach and trust a feed from a [connection file](#connection-files).

## Layout

At the feed's base URL, or under the bucket's prefix:

```
feed.json                 the feed index (feed.json.age when the feed is encrypted)
feed.sig                  signs the stored feed.json (or feed.json.age) bytes; see below for when it is required
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

- `id` is `<publisher>/<slug>`, a [`common.feedId`](../schemas/org.legiblerecords.common/v1.yaml): a [publisher](records.md#publication-fields), `/`, and a `common.slug`. It is stable for the feed's life, and it is what a signed bundle's `feed.id` must match. `publisher` is the domain `id` starts with.
- `audience` is for people: who the feed is for. It isn't enforced; the credential is.
- `updated_at` is when the publisher wrote this index. A reader refuses one more than 24 hours after its own clock (`bad_feed`).
- A stream's `id` is a slug, unique in the feed. `record_types` lists the `$type`s the stream carries, so a reader can decide where it goes before fetching it.
- `bundle` is the bundle's path from the feed's base, `bundles/<sha256>.zip`, or `.zip.age` for an encrypted feed. `sha256` is of the file as stored (the ciphertext, for an encrypted feed), so a reader can check the download before opening it.
- `published_at` is the bundle's, and must be the same instant as its manifest's `published_at` (`bad_bundle`).

**`feed.sig`** has the form of [`manifest.sig`](records.md#signed-bundles), with the context string `legible-records/v1 feed\n`, and signs the exact bytes of the stored `feed.json` file (of `feed.json.age`, for an encrypted feed). It lets a reader trust the list of streams, so a stream that vanishes was withdrawn by the publisher, not dropped by whoever can write to the storage. A publisher that serves a [key set](records.md#key-sets) or signs its bundles must sign its feed. A reader that trusts the feed's publisher ([§ Trust](#trust)) refuses an unsigned index or an unsigned bundle from it (`unsigned_from_pinned_publisher`).

## Publishing

1. Write the new bundle to `bundles/<sha256>.zip` (or `.zip.age`). Paths are named by content, so this never overwrites anything.
2. Write `feed.json`, and `feed.sig`, pointing at it, with `updated_at` and the stream's `published_at` later than before. A bundle in a feed has `published_at` and `feed` in its manifest ([§ Publication fields](records.md#publication-fields)).
3. Delete a bundle that no stream points at only after a grace period of at least one hour, so a reader partway through a poll still finds it.

A publisher that removes a record at its source republishes the stream without it. A publisher that withdraws a stream removes it from `feed.json`. Neither can recall copies readers already took; that is what a reader's redaction is for.

## Trust

What a reader trusts comes from four places: the keys **pinned** in its [connection file](#connection-files), the keys a person **approved**, the publisher's [key set](records.md#key-sets) that the reader **holds** (the last one it accepted), and the key set the publisher **serves** on this poll. This section says how they combine. It applies to every signature a reader checks, `feed.sig` and `manifest.sig` alike, and to a reader handed a single bundle as much as to a feed reader.

**When keys are fetched.** On every poll, before it checks `feed.sig`, a reader fetches the feed publisher's key set, if the publisher serves one, and decides on it as in [records.md § Key sets](records.md#key-sets), with its held set and its pinned and approved keys as anchors. It does this even when `feed.json` turns out unchanged (`304`, or the same ETag), so that a rotation or a revocation reaches it without waiting for the index to change. A set it accepts is held from then on, and its keys are used on this same poll.

**A refused set, or a failed fetch.** A fetched set that is refused, or one waiting for approval, adds no key the reader trusts: it keeps its held set, pins and approvals, and checks signatures with them. Only the revocations of such a set count, as below. It never treats a signature as unverified because a key set couldn't be had or was refused. A set whose `publisher` isn't the domain it was fetched from is `bad_key_set`.

A key-set fetch that fails with anything but a 404 ([§ Access](#access)) is reported. The poll goes on only if a pin, a held key set or an approved key already makes the publisher trusted, and then with those keys as they were. Otherwise the poll fails and the reader changes nothing: without the set it can't tell whether the publisher signs.

**A trusted publisher** is one the reader has any of these for:

- a pinned key;
- an approved key;
- a held key set;
- a key set the publisher served on this poll that is a valid [`org.legiblerecords.keys`](../schemas/org.legiblerecords.keys/v1.yaml) record, even one waiting for approval or refused.

A reader refuses an unsigned feed index or an unsigned bundle from a trusted publisher: `unsigned_from_pinned_publisher` (the code keeps the name it was first given). A publisher that has shown it signs can't have unsigned content accepted by leaving a signature off.

**Trusted keys.** To check a signature that names publisher `P` and key id `K`, a reader looks for `K` in its held key set for `P`, in its pins for `P` and in the keys a person approved for `P`. An approved key is trusted like a pin. A reader trusts the keys of a served set only once it accepts the set, which makes it held; a set it doesn't hold counts only for its revocations.

- If none of them has `K`, the signature is `unknown_key`. A key that a served set adds, while that set waits for approval, is not trusted until it is approved: a signature by it is `unknown_key`.
- Pins are where trust starts. Once a key set is held, its entries are authoritative: a key it marks revoked is revoked even if it is pinned. If the sources disagree about `K` (a pin or approved key whose public key or `alg` differs from the held set's entry, or from another pin or approval, for `K`), `K` names no trusted key: a signature naming it is `unknown_key`, and a `keys.sig` naming it is no endorsement, until a person fixes the pin.
- `K` is **revoked**, and a signature by it `revoked_key`, when the held set (one accepted on this poll included) marks it revoked or marks its public key revoked under another id, or when the key set served on this poll does either and the reader doesn't hold it. A served set counts for this once it passes step 1 of [records.md § Key sets](records.md#key-sets) (it parses, names the domain it was fetched from and isn't dated too far ahead), whatever the rest of the decision: waiting for approval, `bad_endorsement` or `key_set_rollback`. Every reader honours it, stateless readers included, since a revocation can only reduce trust. A revocation in a set the reader doesn't hold refuses what the key signed on this poll and does nothing else: it clears no stream, moves no watermark, and reports no stream as cleared. A set refused as `bad_key_set` changes nothing.
- If `K`'s `alg` isn't one the reader knows, the signature is `unknown_alg`.
- Otherwise the reader verifies the signature with `K`'s public key. Public keys are compared by their decoded bytes.

**Approval.** A key set that adds a key without a valid endorsement waits for a person (`needs_approval`). A person approves keys one at a time, and the reader records each approval as a publisher, a key id, an `alg` and a public key. An approved key is an anchor, so once every key a waiting set adds is approved, the set adds no new key: the reader accepts it on its next fetch and holds it. Until then a signature by one of its new keys is `unknown_key`.

**A held revocation clears what the key signed.** A reader with state records the signer (`publisher` and `key`, or none when unsigned) of each stream's last accepted bundle, and of the last accepted index ([§ Reader state](#reader-state)). When the key set it holds, including one it accepts on this poll, revokes a key, the reader, on that poll and before it checks the index:

- for every stream whose last accepted bundle that key signed, drops the stream's `sha256` and signer, keeps its `published_at`, and reports the stream as `revoked_key`. The stream isn't fetched again on this poll. On the next one it has no `sha256` to match, so it is fetched and checked anew, and the publisher can re-sign and republish what should stay. The republished bundle needs a `published_at` later than the one readers hold, because readers keep it as a replay floor and refuse an equal or earlier one as `replay` (step 12);
- drops the index's signer if that key signed the last accepted index, and keeps its `updated_at` as the watermark;
- drops its ETag if it cleared anything, so the next poll fetches `feed.json` again.

This stands even if the index is then refused. Only a held set clears anything: a set that waits for approval or is refused as `bad_endorsement` or `key_set_rollback` can be served by anyone who controls the server, with no key, and if its revocations cleared a floor, the genuine set and an old but genuinely signed index and bundles could be served on the next poll and taken as current.

The floors stay for the rest of the stream's life. A thief of the key can push one at most 24 hours past the reader's clock, since a reader refuses timestamps further ahead, and the publisher's genuine content is refused as a replay or `stale_feed` only until it is dated past that. Dropping the floor instead would let any revocation reopen replay.

A stateless reader holds none of this. It passes each bundle's signer (`publisher` and `key`) to its destination with the bundle, and the revocations it honoured on the run, each marked as from a set it holds (one it accepted on this run) or from a set it doesn't hold, so that the destination clears what a key revoked by a held set signed, keeping its floors, and does nothing for the others.

**Denial of service, by design.** A key set with no new key is accepted without an endorsement ([records.md § Key sets](records.md#key-sets), step 5). So a keyless attacker who controls the server can retire or revoke the publisher's keys, or have a reader hold a set dated up to 24 hours ahead, so that the publisher's next genuine set looks like a rollback until that time has passed. Bundles and indexes signed by a key marked revoked stop verifying. This is denial of service, which the spec accepts so that a real revocation is believed at once; it can't make a reader accept anything it would otherwise refuse.

**Connection files carry trust anchors.** A connection file's pins decide which keys a reader trusts, so it needs integrity, not secrecy ([§ Connection files](#connection-files)).

## Reading a feed

A reader polls the feed. How often is its own choice; it should poll no more than once a minute, and a publisher may answer `429` with `Retry-After`. Each poll is checked in this order, and a refusal is one of the codes in [§ Outcomes](#outcomes).

**Keys.** These steps run on every poll, whatever happens to the index after them.

1. Fetch the feed publisher's key set, if it serves one, and decide on it ([§ Trust](#trust)). A refused set leaves the keys the reader trusts as they were (`bad_key_set`, `key_set_rollback`, `bad_endorsement`); one waiting for approval is `needs_approval`. Either still has its revocations honoured on this poll, if it passed step 1 of [records.md § Key sets](records.md#key-sets). A failed fetch is reported, and fails the poll unless a pin, a held set or an approved key already makes the publisher trusted.
2. Clear what a key revoked by the held set signed, and report those streams as `revoked_key` ([§ Trust](#trust)).

**The index.** A refused index changes nothing more: the reader keeps the rest of its state and every other stream's last accepted bundle stays current.

3. Fetch `feed.json` (or `feed.json.age`), with `If-None-Match` when the source gives ETags. Unchanged: the poll is done. If both `feed.json` and `feed.json.age` are present, refuse the feed: `plain_and_encrypted`.
4. If `feed.sig` is present, check it over the stored bytes with the `feed` context, in the order of [records.md § Reading a signed bundle](records.md#reading-a-signed-bundle): the signature file (`bad_signature_file`), `alg` (`unknown_alg`), that it names the feed's publisher, the domain the connection's `feed` starts with (`publisher_mismatch`), the key (`unknown_key`, `revoked_key`, `unknown_alg`), and then the signature (`bad_signature`). If it is absent and the reader trusts the feed's publisher ([§ Trust](#trust)), refuse the index: `unsigned_from_pinned_publisher`.
5. Decrypt an encrypted index. Then, for every index, plain or decrypted: it must parse as JSON and be a valid [`org.legiblerecords.feed`](../schemas/org.legiblerecords.feed/v1.yaml), no stream `id` may appear twice, every entry's `bundle` must be `bundles/<its sha256>.zip` in a plain feed or `bundles/<its sha256>.zip.age` in an encrypted one, and `updated_at` may be no more than 24 hours after the reader's clock (`bad_feed`).
6. The index's `id` must be the connection's `feed`, and its `publisher` the domain that `id` starts with (`wrong_feed`).
7. A reader with state refuses an `updated_at` earlier than the last one it accepted (`stale_feed`). An equal one is not stale.

**Each stream.** A failure in one stream doesn't stop the others: the reader reports it and tries again next poll, and the stream's last accepted bundle stays current. A stream reported `revoked_key` in step 2 isn't checked again on this poll.

8. A stream whose `sha256` is the last one accepted for it is **unchanged**, and isn't fetched.
9. A stream in the reader's state that the index doesn't list is **withdrawn**, and the reader forgets it. What the reader does with what it delivered is its own policy.
10. Otherwise fetch the bundle and check its SHA-256 against `feed.json` (`download_mismatch`). Decrypt it if it is encrypted, read its zip's entry names, check its signature as in [records.md § Reading a signed bundle](records.md#reading-a-signed-bundle), with the feed's publisher as the publisher it must name, and then check it as a bundle (`bad_bundle`). The signature is checked before the bundle's own checks, as for any signed bundle. An unsigned bundle from a trusted publisher is `unsigned_from_pinned_publisher`.
11. Every bundle in a feed, signed or not, must have `published_at` in its manifest (`missing_published_at`), and it must be the same instant as the index entry's `published_at` (`bad_bundle`). A signed bundle's `feed.id` and `feed.stream` must be the feed's `id` and the stream's `id` (`wrong_feed`, `wrong_stream`). This stops one stream's bundle being served as another's, or another feed's as this one's.
12. A reader with state refuses a signed bundle whose `published_at` isn't later than the last accepted one for the stream, which a revocation that cleared the stream keeps (`replay`). An equal `published_at` is a replay. This stops an old signed bundle being put back.
13. Otherwise the bundle is **accepted**, and becomes the stream's current bundle. The reader records its `sha256`, its `published_at` and its signer, and passes the bundle to its destination with that `published_at`.

Timestamps are parsed and compared as instants, not as text: `2026-11-24T11:00:00+01:00` and `2026-11-24T10:00:00Z` are equal. They are [RFC 3339](https://www.rfc-editor.org/rfc/rfc3339) date-times with an offset (`Z` or `±hh:mm`), and anything else is refused like any value that doesn't validate. A reader refuses a timestamp more than 24 hours after its own clock: a key set's `updated_at` (`bad_key_set`), a feed index's `updated_at` (`bad_feed`) and a bundle's `published_at` (`bad_bundle`). Otherwise one signature with a far-future date would set a watermark that refuses every genuine key set, index or bundle after it; the 24 hours allow for clocks that differ.

An unsigned bundle from a publisher that isn't trusted is accepted as **unverified**, and the reader says so wherever it shows it, as for any [unsigned bundle](records.md#reading-a-signed-bundle).

[vectors/feeds/](../vectors/feeds/) holds the cases, one directory each. `feed/` holds the files at the feed's base URL, and `key-set/`, when present, the `keys.json` (and `keys.sig`, when there is one) that the feed's publisher serves at `/.well-known/legible-records/` on this poll; without it the publisher serves no key set. `case.json` gives `name`, `connection` (a connection file), `state` (the reader state in the form below, or `null` for a stateless reader), optionally `now` (the reader's clock, `2026-12-01T00:00:00Z` when absent) and `expect`: `index` is `ok` or the code the index is refused with; `streams` maps each stream id to `accepted`, `unchanged`, `withdrawn` or a code; `key_set`, present exactly when the case has `key-set/`, is `accepted`, `needs_approval` or the code the served set is refused with; and optionally `state`, the reader state after the poll, for a case with state (without an ETag, which the vectors don't model). A refused index expects no stream outcomes but the `revoked_key` of step 2. The reader state in a vector is a format for the vectors, not a type:

```json
{
  "feed_updated_at": "2026-11-24T10:00:00Z",
  "feed_signer": { "publisher": "acme.example", "key": "2026-11" },
  "streams": {
    "policy-acknowledgments": {
      "sha256": "…",
      "published_at": "2026-11-24T10:00:00Z",
      "signer": { "publisher": "acme.example", "key": "2026-11" }
    }
  },
  "key_sets": { "acme.example": { "$type": "org.legiblerecords.keys", "…": "…" } },
  "approved": [ { "publisher": "acme.example", "id": "2026-11", "alg": "ed25519", "public_key": "…" } ]
}
```

`feed_signer` and each stream's `signer` are `null` when what they were accepted from was unsigned, or when a revocation cleared them; a stream a revocation cleared also has `sha256` `null`, and keeps its `published_at`. `approved` entries carry `alg`, like pins. The keys a reader trusts are the connection's pins, the key set it is served on the poll once it accepts it ([§ Trust](#trust)), and with state also the held key sets and the keys a person approved; a served set it doesn't hold counts only for its revocations. Encrypted feeds have no vectors here, because age output is random; implementations test them themselves. The `stateless-replay` vector asserts only that the old bundle is accepted; that it is delivered with its older `published_at`, for the destination to refuse, is for an implementation's own tests.

## Reader state

The checks above compare against what the reader accepted before. The spec says what a reader must remember, not where it keeps it:

| State | For | Per |
|---|---|---|
| `updated_at` of the last accepted `feed.json`, and its signer | refusing an older feed index; knowing whether a revoked key signed it | feed |
| each stream's last accepted `sha256`, `published_at` and signer | fetching only what changed, refusing replays, noticing withdrawn streams, clearing what a revoked key signed | stream |
| the last accepted [key set](records.md#key-sets), and keys a person approved (each with publisher, id, `alg` and public key) | checking `keys.sig` on rotation without asking twice | publisher |
| ETag (optional) | skipping an unchanged `feed.json` | feed |

- A reader keeps no bundles (they go to its destination), no history (its destination keeps that) and no OAuth tokens (they last minutes, and fetching one per run means no secret is written to disk).
- State must be kept where the feed's writer can't change it. Someone who can write the feed and reset the reader's state can get a replay accepted.
- A signer is the `publisher` and `key` of the signature the reader accepted, or none for something unsigned.
- A stream is in the reader's state from when a bundle for it is accepted until it is withdrawn. A revocation that clears it keeps it there, with only its `published_at`. **Withdrawn** is decided against these streams: one in the state that the index no longer lists.
- State changes only when something is accepted, or when a revocation in the held set clears what a key signed ([§ Trust](#trust)): a refused index leaves the rest of it as it was, a refused stream leaves that stream's, and a revocation in a set the reader doesn't hold leaves all of it.

**A stateless reader** is allowed when what it delivers to performs the history checks instead. It skips the `stale_feed` and `replay` checks, fetches and checks every stream on every run (hash, bundle, signature, `feed.id` and `feed.stream`), and passes along, with each bundle it delivers, the bundle's `published_at`, `sha256` and signer (`publisher` and `key`) and the index's `updated_at` and list of stream ids. Its destination then does what a reader with state would: it refuses an index whose `updated_at` is earlier than the last it accepted, and marks nothing withdrawn from one; it ignores an unchanged hash; it refuses a bundle whose `published_at` is older than the one it holds, or equal to it with a different `sha256`, which is a replay; and it marks withdrawn the streams a newer index no longer lists. When the reader reports a key revoked by a set it holds (one it accepted on that run), the destination clears what that key signed as a reader with state does, keeping its `published_at` and `updated_at` floors; a revocation from a set the reader doesn't hold changes nothing there ([§ Trust](#trust)). Without the index's `updated_at`, an old index that is genuinely signed would get current streams marked withdrawn. A stateless reader's anchors come only from its connection file: it accepts a rotated key set when `keys.sig` is by a pinned key that the new set doesn't revoke ([§ Key sets](records.md#key-sets)), and anything else waits for a person to update the connection file. It still fetches the key set on every run, and honours the revocations in it as [§ Trust](#trust) says.

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
| `s3` | any S3-compatible bucket | GETs signed with AWS Signature Version 4, with an access key that has `s3:ListBucket` on the prefix and `s3:GetObject` on the objects under it |
| `none` | a public feed, or one behind a network boundary | nothing |

- `oauth-client-credentials`: the client authenticates at `token_url` with `client_secret_post`, sending `client_id` and the client secret in the form body with `grant_type=client_credentials`, `resource` and `scope`.
- `s3`: without `s3:ListBucket`, S3 answers a missing object with 403 rather than 404, and a reader can't tell a feed that isn't encrypted from one it may not read.
- For every source, only a 404 (for S3, a `NoSuchKey` error) means a file is absent: an absent `feed.sig`, `feed.json.age` or key set. Any other failure (a 403, a 5xx, a timeout, a TLS error) fails the poll, and the reader changes nothing, so that an outage or a revoked credential can't make a signed feed look unsigned. The one exception is the key set: its failed fetch is reported, and the poll goes on when a pin, a held set or an approved key already makes the publisher trusted ([§ Trust](#trust)).
- `location.url`, `endpoint` and `token_url` must be `https` URLs. Plain `http` is allowed only for a loopback host (`localhost`, `127.0.0.0/8` or `[::1]`), for testing.
- An S3 `prefix` is normalised before use: leading slashes removed, and exactly one trailing slash added unless it is empty. `feeds/track`, `/feeds/track/` and `feeds/track//` all mean `feeds/track/`; an empty prefix stays empty, the bucket's root.

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
- `auth.method` is one of [§ Access](#access). `auth` names environment variables, never values: `token_env` for `bearer`; `token_url`, `client_id`, `client_secret_env`, `resource` and `scope` for `oauth-client-credentials`; `access_key_id_env` and `secret_access_key_env` for `s3`. The schema has `token`, `client_secret`, `access_key_id` and `secret_access_key` fields in `auth`, and `age_identity` at the top level, that can only be `null`, so a file with a literal value in one of them doesn't validate.
- `keys` pins keys, each a publisher, a key id, `alg` and a public key. Absent or empty means: use the publisher's key set, and ask before trusting it the first time ([§ Key sets](records.md#key-sets)). A publisher without a key set has its key pinned here.
- `age_identity_env` names the variable holding the reader's age identity, and is required for an encrypted feed.

The fields a `kind` or `method` needs can't be required by the schema, because the published subset has no conditionals ([rules.md](rules.md#the-published-subset)), so the reader checks them. A reader refuses a connection file that lacks a field its `kind` or `method` needs, or whose `kind` or `method` it doesn't know, before it fetches anything. It also refuses one whose `url`, `endpoint` or `token_url` carries userinfo (`user:password@`), since that would put a credential in the file.

The file holds no secret, so it can be emailed, committed, or pasted into a reader's settings. It does carry trust anchors: its `keys` decide which signatures the reader believes. It needs **integrity, not secrecy**. A reader, or the person setting it up, checks a connection file out of band before using it, as for a key fingerprint: for instance, by comparing its `feed` and pinned public keys with the publisher over a channel they already trust. A reader also refuses a pinned `public_key` that isn't canonical base64url.

## Outcomes

A reader of a bundle, a feed or a key set returns one of these codes when it refuses, and [the test vectors](../vectors/) expect them by these exact strings.

| Code | Meaning |
|---|---|
| `bad_signature_file` | `manifest.sig` or `feed.sig` isn't the JSON the spec defines, or its `signature` isn't canonical base64url of 64 bytes. |
| `unknown_alg` | `manifest.sig` or `feed.sig` names an `alg` other than `ed25519`, or names a key whose `alg` the reader doesn't know. |
| `unknown_key` | No trusted key has that publisher and id, or the reader's sources disagree about it ([§ Trust](#trust)). |
| `bad_signature` | The signature doesn't verify. |
| `revoked_key` | Signed by a revoked key, whatever the bundle's `published_at`. |
| `publisher_mismatch` | The signature's publisher isn't the feed's publisher. |
| `unsigned_from_pinned_publisher` | An unsigned bundle or feed index from a trusted publisher ([§ Trust](#trust)). |
| `stale_feed` | `feed.json` `updated_at` is earlier than the last one accepted. |
| `plain_and_encrypted` | Both `feed.json` and `feed.json.age` are present. |
| `bad_feed` | A feed index doesn't parse or isn't a valid feed, repeats a stream id, lists a `bundle` path that isn't `bundles/<its sha256>.zip` (`.zip.age` in an encrypted feed), or has an `updated_at` more than 24 hours after the reader's clock. |
| `download_mismatch` | A bundle file's SHA-256 isn't the one `feed.json` gives. |
| `bad_bundle` | The bundle fails the bundle checks: zip entry names, hashes, file list or references; its `published_at` is more than 24 hours after the reader's clock; or, in a feed, its `published_at` isn't the index entry's. |
| `missing_published_at` | A bundle in a feed, signed or not, has no `published_at`. |
| `wrong_feed` / `wrong_stream` | The signed manifest's `feed.id` or `feed.stream` doesn't match where it was found, or `feed.json`'s `id` isn't the connection's `feed`. |
| `replay` | `published_at` isn't later than the last accepted one for the stream. |
| `bad_endorsement` | Any failure of `keys.sig`: it isn't the JSON the spec defines, names another `alg` or publisher, doesn't verify, or is by an anchor that may not endorse. Also a held key set's `publisher` changing. |
| `needs_approval` | A key set adds a key with no valid endorsement. |
| `key_set_rollback` | A key set is older than the held one, drops a held key, or clears a held key's retired or revoked date. |
| `bad_key_set` | A key set doesn't parse or validate, repeats a key id or a public key, has a `public_key` that isn't canonical, has an `updated_at` more than 24 hours after the reader's clock, or names a publisher other than the domain it was fetched from. |
