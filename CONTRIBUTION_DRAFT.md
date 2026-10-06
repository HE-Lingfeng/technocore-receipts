# Contribution draft: offline transcript checks

Status: announcement draft for a future submission to FLOP Labs.

Technocore's raw exports let developers verify message signatures offline, but
application code often also needs to account for missing signatures, sequence
gaps and replayed signed content before using a transcript. I built an
independent Python CLI, `technocore-receipts`, that checks one exported room and
returns a deterministic JSON report.

The implementation verifies the exact stored UTF-8 payload, preserves
19-digit nonce precision, rejects noncanonical signatures and ambiguous JSON,
and reports missing signatures separately from invalid ones. Optional signer
and file-hash pins support application-specific trust anchors. The report
contains file and per-line hashes and omits message bodies.

Checks deliberately keep authorship separate from venue metadata: `seq` and
`ts` are not sender-signed, retained rings cannot establish complete history,
and observed nonce order is not a simulation of the server's replay cache.
The tool has no production network, key-loading, signing or payment path.
It does not evaluate contest outcomes or airdrop eligibility.

Validation covers text/nonce/sender changes, cross-room copies, base64 padding
ambiguity, nineteen-digit integers, Unicode forms, duplicate JSON fields,
missing signatures, gaps, malformed records and CLI exit behaviour. The demo
uses synthetic keys generated only in memory. Live validation evidence and its
result are recorded in `VALIDATION.md`; real exports remain outside the repo.

This can be used as an external companion tool by any client that consumes
Technocore exports. It requires no change to the server or frozen contest rules.
