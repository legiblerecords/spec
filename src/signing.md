---
title: Signing and keys
lede: A publisher signs a bundle's manifest with an ed25519 key. Readers check the signature against keys they trust.
---

## Signed bundles

`manifest.sig` is a JSON object with exactly four members:

```json
{
  "alg": "ed25519",
  "publisher": "acme.example",
  "key": "2026-11",
  "signature": "<base64url, no padding>"
}
```

The signature covers a context line, then the exact bytes of `manifest.json` as stored:

```text
legible-records/v1 manifest\n
```

Every kind of signature has its own context (`manifest`, `feed`, `keys`), so a signature of one kind can't be passed off as another. The manifest lists every file's hash, so the signature covers every record and attachment.

A `publisher` is a lowercase domain the signer controls, with no scheme, port or path. An IP address is not a publisher.

## Key sets

A publisher that controls a domain serves its keys over HTTPS:

```text
https://<publisher>/.well-known/legible-records/keys.json
https://<publisher>/.well-known/legible-records/keys.sig   (optional endorsement)
```

```json
{
  "$type": "org.legiblerecords.keys",
  "version": 1,
  "publisher": "acme.example",
  "updated_at": "2026-11-24T00:00:00Z",
  "keys": [
    { "id": "2026-11", "alg": "ed25519", "public_key": "<base64url>", "created_at": "2026-11-24T00:00:00Z" },
    { "id": "2025-06", "alg": "ed25519", "public_key": "<base64url>", "created_at": "2025-06-01T00:00:00Z", "retired_at": "2026-11-24T00:00:00Z" }
  ]
}
```

Whoever controls the domain controls its key set.

- **Retired** keys were rotated out. What they signed still verifies.
- **Revoked** keys are compromised. Nothing they signed verifies, at any date, because whoever holds the key can write any date into a manifest.
- A key set endorsed by a key the reader already trusts is accepted, new keys included.
- A key set that adds a key with no valid endorsement is `needs_approval`: a person decides.
- A key set older than the one the reader holds, or one that drops a key or clears a revocation, is `key_set_rollback`.

A publisher without a key set, such as a script in CI, still names a domain it controls. Readers pin its public key in their configuration.

## Commands

```sh
# The secret key goes to a new file, readable by you alone. The entry for keys.json is printed.
legible keys new --publisher acme.example --id 2026-11 -o acme-2026-11.key.json

legible bundle sign evidence.zip -k acme-2026-11.key.json -o evidence.signed.zip
legible bundle verify evidence.signed.zip --pin acme.example/2026-11=<public_key>
legible bundle verify evidence.signed.zip --key-set keys.json

# Endorse a new key set with a key readers already hold.
legible keys sign keys.json -k acme-2026-11.key.json -o keys.sig
```

`verify` prints one line about the signature: `signature: verified (<publisher> <key>)`, `signature: unverified`, or an [outcome code](/outcomes/).

> Exit 0 from `verify` doesn't mean a signature was checked. Only `signature: verified` means that, and it needs `--pin` or `--key-set`.

Spec: [records.md § Signed bundles](https://github.com/legiblerecords/spec/blob/main/spec/records.md#signed-bundles).
