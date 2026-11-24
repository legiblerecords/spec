---
title: Feeds
lede: A feed is how a publisher offers records to a reader that polls for them.
---

A feed is a set of named **streams**, each with exactly one current bundle. A stream changes when its bundle is replaced. A record that is no longer in the new bundle was removed at the source. A report is a stream of its own, published once.

A feed has one audience and one credential. It can be served over HTTPS or kept in an S3-compatible bucket: the files are the same.

## Layout

```text
feed.json                 the feed index (feed.json.age when the feed is encrypted)
feed.sig                  signs feed.json (or feed.json.age) as stored
bundles/<sha256>.zip      named by the SHA-256 of the file as stored
bundles/<sha256>.zip.age
```

## The index

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

A publisher that serves a key set or signs its bundles must sign its feed, so a stream that vanishes was withdrawn by the publisher, not dropped by whoever can write to the storage.

## Publishing

1. Write the new bundle to `bundles/<sha256>.zip`. Paths are named by content, so this never overwrites anything.
2. Write `feed.json` and `feed.sig` pointing at it, with later `updated_at` and `published_at` than before.
3. Delete bundles no stream points at only after at least an hour, so a reader partway through a poll still finds them.

```sh
legible feed publish ./site/track --feed acme.example/track --audience "Monorail, for Track" \
  --stream policy-acknowledgments --title "Policy acknowledgments" -k acme-2026-11.key.json acks/
```

`feed publish` writes into a directory and never deploys. Getting the directory to the web or a bucket is yours.

## Connection files

A reader learns where a feed is, how to authenticate and which keys to trust from a connection file. It names environment variables, never secrets.

```json
{
  "$type": "org.legiblerecords.feed-connection",
  "version": 1,
  "feed": "acme.example/track",
  "location": { "kind": "https", "url": "https://feeds.acme.example/track/" },
  "auth": { "method": "bearer", "token_env": "ACME_FEED_TOKEN" },
  "keys": [{ "publisher": "acme.example", "id": "2026-11", "alg": "ed25519", "public_key": "<base64url>" }],
  "age_identity_env": "ACME_AGE_IDENTITY"
}
```

## Reading

```sh
ACME_FEED_TOKEN=... legible feed check connection.json
ACME_FEED_TOKEN=... legible feed pull connection.json --state ~/.legible/state --out ~/records
```

Both fetch the publisher's key set on every poll, before the index, so a rotation or revocation reaches them even when the feed hasn't changed. They print one line per stream:

```text
policy-acknowledgments: accepted (verified acme.example 2026-11)
access-reviews: unchanged
q3-report: withdrawn
```

`feed check` keeps nothing, so it can't detect a replay. Use it to see whether a feed and its signatures are good. `feed pull` keeps reader state, so a bundle older than the last one accepted is refused as `replay`.

Spec: [feeds.md](https://github.com/legiblerecords/spec/blob/main/spec/feeds.md).
