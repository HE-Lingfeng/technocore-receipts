# Validation, 2026-10-06

The standalone tool was checked locally before publication.

## Automated checks

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
| Per-record issues | None |
| CLI status / exit | `passed / 0` |

This file hash identifies the downloaded bytes; it was not checked against an
independent signed file commitment. The sender signatures do not authenticate
the generation header, sequence numbers or timestamps. This observation does
not establish whole-room history, trade settlement, a participant's final
account or a prize. The report keeps those scope flags false.

The real export and generated report stay outside the repository. They are
not fixtures or release contents.

## Original contest package

The original `technocore-close-call-challenge` package was unchanged. Its
generated-file check passed, all **15 manifest artifacts** matched, and all
**18 original tests** passed. Neither the existing participant client's
official-results configuration nor its identity was changed.
