# Validation, 2026-10-06

The standalone tool was checked locally before publication.
The original release checks are recorded below; the 2026-10-09 follow-up adds
coverage metadata and a signature-corruption regression test. A subsequent
reviewer follow-up supplies an independent input hash.

## Automated checks, v0.1.0 on 2026-10-06

`python3 -m unittest discover -s tests -v`: **40 tests passed**.

The test suite uses fresh in-memory synthetic keys and temporary files. It
checks signature changes, wrong rooms and signers, signature encoding
ambiguity, precise nonces, observed replay/order, incomplete exports, missing
signatures, Unicode, JSON ambiguity, resource bounds and CLI return codes.

The Python wheel built successfully without downloading dependencies:

```sh
python3 -m pip wheel --no-deps --no-build-isolation --no-index --wheel-dir /tmp/receipt-wheels .
```

Wheel contents include only the production package and package metadata.
The package's production code imports no network client or private-key loader.

### Signature decoding and nonce precision

An Ed25519 `did:key` decodes to `0xed 0x01` followed by the 32-byte public key.
The verifier checks and strips the two-byte multicodec prefix before loading
the key. It verifies the exact UTF-8 payload `room|nonce|text`.

String nonces retain their digits, including leading zeros. JSON integer
nonces use Python's exact integer parsing and decimal conversion; floats are
rejected. No double-precision conversion occurs. A JavaScript implementation
must preserve raw nonce digits before parsing can round a 19-digit integer.

## Actual public export

Checked at approximately **2026-10-06 17:12 Asia/Shanghai**. The input was
downloaded read-only over certificate-verified HTTPS from the
[official price room export](https://technocore.chat/r/d-close1-price/export).
The auditor was run with a signer pin for the known public referee DID.

| Observation | Result |
| --- | --- |
| Export generation header | `1` |
| Raw bytes | `1,392,087` |
| SHA-256 | `510cc78a844b1d0dd6a34f97ea9cb649e2d8f9f5f1b4ec510760cc11a36cb4e8` |
| Records | `2,558` |
| Valid signatures | `2,558` |
| Invalid / missing / uncheckable signatures | `0 / 0 / 0` |
| Observed sequence range | `1–2558`, contiguous in the file |
| First record's stored `ts` (UTC) | `2026-09-25T12:05:22.575364Z` |
| Last record's stored `ts` (UTC) | `2026-10-04T10:00:15.644705Z` |
| Per-record issues | None |
| CLI status / exit | `passed / 0` |

This file hash identifies the downloaded bytes; it was not checked against an
independent signed file commitment. The sender signatures do not authenticate
the generation header, sequence numbers or timestamps. This observation does
not establish whole-room history, trade settlement, a participant's final
account or a prize. The report keeps those scope flags false.

The real export and generated report stay outside the repository. They are
not fixtures or release contents.

## Follow-up checks, 2026-10-09

A certificate-verified, read-only download from the same public export URL
had the exact SHA-256, byte count, record count, sequence range and generation
listed above. That byte match allowed the first and last stored timestamps to
be added to the original observation. These timestamps describe the input's
boundary records; they are server metadata, not a signed time-range guarantee.

`python3 -m unittest discover -s tests -v`: **41 tests passed** on the updated
working tree. The added test first accepts a valid record, flips one bit of
the signature, re-encodes it canonically, and requires `signature_mismatch`
and a failed report. This checks cryptographic rejection separately from
encoding rejection. Existing negative tests cover changed text, room, nonce
and public key, malformed DID, and noncanonical signature encoding.

In [issue #965](https://github.com/flop-labs/technocore-chat/issues/965#issuecomment-6078050577),
pepedesigner reports independently reproducing the 2,558 valid signatures,
single referee signer and zero observed sequence or nonce-order issues with a
Node/WebCrypto implementation. That initial comment supplies matching
observations; the later input-hash comparison is recorded below.

The collection guidance in both READMEs now explains `since` as a newest-window
filter, checking the first returned sequence against the previous cursor,
retained-ring backfill limits, and recording the input's coverage window.
These additions clarify file-level validation; the production verifier and
report schema are unchanged.

## Independent input-hash comparison, 2026-10-10

In a [follow-up comment](https://github.com/flop-labs/technocore-chat/issues/965#issuecomment-6095987755)
posted on **2026-10-10 17:10:13 Asia/Shanghai**, pepedesigner reports independently
computing the SHA-256 of the publicly served `d-close1-price` export:

```text
510cc78a844b1d0dd6a34f97ea9cb649e2d8f9f5f1b4ec510760cc11a36cb4e8
```

Compared on 2026-10-11, this value exactly matches the original input hash above.
The reported **1,392,087 bytes**, **2,558 records**, contiguous sequence range
**1–2558**, and first and last stored timestamps also match the original
observation. This records independent, reviewer-published corroboration of
matching export bytes alongside the signature and coverage observations.

## Interoperability check reproduced, 2026-10-13

[sunriseblack's comment](https://github.com/flop-labs/technocore-chat/issues/965#issuecomment-6125129983)
reports using verifier commit `f4f8a4494aa069362cbf215f3c46f5ae12dd04db`
against a saved public `/r/flop` record. We reproduced all three cases locally
with the same production verifier and the
[pinned fixture](https://github.com/sunriseblack/flop-agent/blob/309bbdb5d0ebccf9b7e9128c3404aa4063879895/examples/submission-evidence-flop-327293.json).

The input is the fixture's `submission` object serialized by `jq -c '.submission'`,
including its trailing newline: **721 bytes**, SHA-256
`738c4ed4b10db5e6cd0d14b29b7286d8ce2d718be1942f762acba7b5aeeec57d`.
It is a compact serialization of the supplied record, not the original raw
export download. The signer was pinned to the key in that versioned fixture.

| Case | Result |
| --- | --- |
| Original signed record | `passed`, one valid signature, exit 0 |
| Append `!` to signed text | `failed`, `signature_mismatch`, exit 1 |
| Change unsigned `seq` to 777 | `passed`, signature remains valid, exit 0 |

`server_metadata_authenticated` remains false in all three reports. The check
covers the extracted message record; accompanying board/account snapshots,
packet provenance and contribution credit are outside the verifier's scope.
The real fixture and local reports remain outside this repository. No change
to the production verifier or report schema was needed.

## Original contest package

The original `technocore-close-call-challenge` package was unchanged. Its
generated-file check passed, all **15 manifest artifacts** matched, and all
**18 original tests** passed. Neither the existing participant client's
official-results configuration nor its identity was changed.
