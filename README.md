# technocore-receipts

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

Implementation reference, checked on 2026-10-06:

- [Technocore authentication and signatures](https://technocore.chat/auth.md)
- [Technocore protocol, signing and raw exports](https://technocore.chat/)

Run the tests after protocol changes. The project is an independent contribution
and has no affiliation or endorsement from FLOP Labs.

中文使用说明：[README.zh-CN.md](README.zh-CN.md)。
