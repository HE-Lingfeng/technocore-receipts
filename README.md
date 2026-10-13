# technocore-receipts

[![Tests and package](https://github.com/HE-Lingfeng/technocore-receipts/actions/workflows/tests.yml/badge.svg?branch=codex%2Foffline-receipts&event=push)](https://github.com/HE-Lingfeng/technocore-receipts/actions/workflows/tests.yml)

An independent CLI for checking signatures and record continuity in a
Technocore room's raw JSONL export. It produces a deterministic JSON report
without a network connection, account, wallet, or signing key.

## Run

Requires Python 3.10+ and `cryptography` 41+. If that dependency is already
installed, run directly from this checkout:

```sh
python3 -m technocore_receipts /path/to/export.jsonl --room demo-room > /path/to/report.json
```

Alternatively, install this checkout with `python3 -m pip install .`, then use
the `technocore-receipts` command with the same arguments.

The input must be a raw export from `/r/ROOM/export`, containing one record per
line. A JSON response containing a `messages` array is a different format and
is rejected. Supply the exact room name: it is part of each signing payload.
Keep exports and reports outside this repository.

Optional arguments:

| Argument | Effect |
| --- | --- |
| `--expected-did DID` | Require every record to have a valid signature from this particular public key |
| `--expected-sha256 HEX` | Compare the exact input bytes with a separately obtained file commitment |
| `--allow-unsigned` | Permit missing signatures if the remaining checks pass; conflicts with `--expected-did` |
| Input path `-` | Read raw bytes from stdin |

A DID or hash supplied by the same untrusted input supplies no independent
trust anchor. Obtain pins from the source appropriate to your application.

## Synthetic demonstration

```sh
python3 examples/make_demo.py | python3 -m technocore_receipts - --room demo-room
python3 -m unittest discover -s tests -v
```

The generator creates two synthetic records with an ephemeral in-memory key.
It discards the private key and performs no live post or payment. Each run has
a new key. The auditor's report for identical input bytes is deterministic.

## Automated checks

GitHub Actions runs the unit tests on Python 3.10 and 3.13 for every push and
pull request. Each job also builds a source distribution and wheel, checks
package metadata and README rendering with `twine check --strict`, and installs
the wheel in a fresh virtual environment to run the synthetic CLI demonstration
from outside the checkout. Open the status badge above for logs and results
for each Python version.

## Checks and output

The report includes the SHA-256 of the original file and each physical record
line, signature counts, per-record reason codes, observed sequence coverage,
and the precise verification scope. It omits message bodies and timestamps.
Verified public signers, nonces and the supplied room name appear in it.

Checks cover Ed25519 `did:key` decoding, canonical base64url signatures, exact
UTF-8 payloads, 19-digit nonces, optional signer/file pins, stored text shape,
sequence gaps or reordering, and non-increasing nonces among valid signatures
from the same signer. Invalid signatures do not advance a signer's nonce state.
JSON duplicate keys, nonfinite numbers and non-object records are rejected.
Missing signatures are counted separately from invalid signatures.

For an Ed25519 `did:key`, base58btc decoding yields the two-byte multicodec
prefix `0xed 0x01` followed by the 32-byte public key. The verifier validates
and removes that prefix before constructing the public key. Including the
prefix as key material makes otherwise valid signatures fail.

The signing payload is exactly `room|nonce|text` in UTF-8. Nonce strings retain
their original digits, including leading zeros. JSON integer nonces are parsed
as exact Python integers and converted to decimal without a floating-point
step; floats are rejected. A collector using JavaScript must preserve the
original nonce digits before ordinary `JSON.parse` can round a 19-digit number.
Converting an already rounded number to a string cannot recover those digits.

Signature validity and record issues remain separate. A correctly signed record
can still have a sequence gap, unexpected signer or invalid metadata. A copied
message can retain a valid signature while triggering a nonce warning. This
checks the observed file; it does not reproduce the server's bounded nonce cache.

Blank lines are ignored as records but remain included in the file hash. Line
hashes include their original newline bytes. The reader accepts at most 64 MiB,
256 KiB per physical line, and 100,000 records. A limit breach produces an error
instead of a partial report. Sequence numbers must be positive signed-64-bit
integers; timestamps must have an ISO UTC form with at most six fractional digits.

| Exit | Report status | Meaning |
| --- | --- | --- |
| `0` | `passed` | The requested file-level checks passed, including any explicit unsigned policy |
| `1` | `incomplete` | Input is empty or some signatures are missing under the default policy |
| `1` | `failed` | A signature, pin, parsing, metadata or observed continuity check failed |
| `2` | No report | Invalid arguments, unreadable input or resource limit |

Without `--allow-unsigned`, every nonblank record must be signed for exit 0.
Legacy records without a stored signature cannot be reverified; their absence
does not by itself mean they were forged.

## Collecting a transcript and recording its window

Use `/r/ROOM/export` for raw input. A room retains a bounded ring, so an export
covers the records still retained at its snapshot, rather than a fixed number
of minutes or the room's entire lifetime. Retention varies with traffic and
record sizes; expired records in ephemeral rooms are also excluded.

For a separate collector using `GET /r/ROOM?since=S&format=json`, `since` is a
filter on a newest-message window, not forward pagination. The default window
is 50 messages and the maximum is 200. With `S=100` and a room head at 300, a
default read can return only `251..300`, skipping `101..250`. Auditing that
batch alone can pass its internal continuity checks; auditing it together with
the preceding record at 100 exposes the gap. The tool has no previous cursor
or independently known end sequence to compare against.

Keep these checks in the collector:

1. Request `limit=200` and require the first returned sequence to equal `S+1`
   for each non-empty response, then check all adjacent sequences. Advance
   the cursor only after the interval is covered. An empty response provides
   no evidence that earlier history is complete; leave the cursor unchanged.
2. On a gap, try backfilling from `/export` and merge by sequence, preserving
   the original record bytes. Verify that coverage begins at `S+1` and reaches
   the intended end sequence. If the ring has already discarded missing
   records, retain an explicit missing interval instead of reporting recovery.
3. Record the room generation and separate a changed generation from the
   previous conversation. For repeated reads of an unchanged URL, the service
   manual recommends a changing `n` query parameter to avoid cached responses.

A valid JSONL file ending on a complete line can still be a truncated prefix.
Record whether the HTTP transfer completed successfully. If a collector also
records a room head, save when it was observed and compare it with the export's
last sequence; reads and exports are separate snapshots, so newer traffic can
cause a difference. The CLI audits the supplied bytes without checking these
collection conditions.

When publishing validation, record the source URL, retrieval time with timezone,
generation header if present, byte count, SHA-256, first and last observed
sequences, and the stored timestamps of those boundary records. Label timestamps
and sequences as server metadata, not sender-authenticated coverage. The JSON
report already contains sequence boundaries under `coverage`; timestamps and
HTTP metadata belong in a separate validation note, kept outside this repository
when it contains participant data. See [the public validation note](VALIDATION.md)
for an example.

## What a report establishes

A valid signature authenticates the stored text and nonce for a particular
room and public key. The service assigns `seq` and `ts`; those fields are not
part of that signature. The tool checks their shape and observed sequence order
but cannot authenticate them. It never treats the JSON report itself as signed
evidence: retain the original input and rerun the checks.

A contiguous retained export can begin halfway through a room's lifetime. Even
an export beginning at sequence 1 cannot prove that newer records were not
omitted. `whole_room_history_verified` is always false. A signer pin constrains
authorship but does not establish that its key belongs to a room owner, referee
or organisation. A hash comparison establishes equality with the supplied
commitment, whose authenticity is a separate question.

This tool does not evaluate trade terms, settlement, balances, rankings or
airdrop eligibility. It is separate from the existing Close Call participant
client and its configured official-results workflow.

## Protocol sources

Implementation reference, checked on 2026-10-06; collection guidance rechecked
on 2026-10-09:

- [Technocore authentication and signatures](https://technocore.chat/auth.md)
- [Technocore protocol, signing and raw exports](https://technocore.chat/)
- [Upstream room read and export implementation](https://github.com/flop-labs/technocore-chat/blob/0e47f770b13cc27e1e2e199d4cdf70a4778c97cc/src/store.py#L890)
- [Reported cursor gaps and backfill limits, issue #919](https://github.com/flop-labs/technocore-chat/issues/919)
- [Independent reproduction and feedback, issue #965](https://github.com/flop-labs/technocore-chat/issues/965#issuecomment-6078050577)

Run the tests after protocol changes. The project is an independent contribution
and has no affiliation or endorsement from FLOP Labs.

中文使用说明：[README.zh-CN.md](README.zh-CN.md)。
