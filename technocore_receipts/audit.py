"""Audit stored bytes without contacting a server or loading a signing key."""

import base64
import hashlib
import json
import re
import unicodedata
from datetime import datetime
from typing import BinaryIO

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from . import __version__

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
ROOM = re.compile(r"[a-z0-9][a-z0-9_-]{0,47}")
DID = re.compile(r"did:key:z6Mk[1-9A-HJ-NP-Za-km-z]{44}")
NONCE = re.compile(r"[0-9]{1,19}")
SIGNATURE = re.compile(r"[A-Za-z0-9_-]{86}")
TIMESTAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|\+00:00)")
FORBIDDEN_TEXT_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Co", "Zl", "Zp"})
MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_LINE_BYTES = 256 * 1024
MAX_RECORDS = 100_000


class InputError(ValueError):
    """Invalid arguments or input too large for a bounded report."""


class RecordError(ValueError):
    """A record cannot be authenticated; the message is a stable reason code."""


def public_key(did: str) -> Ed25519PublicKey:
    """Resolve an Ed25519 did:key locally and require its canonical encoding."""
    if not isinstance(did, str) or not DID.fullmatch(did):
        raise RecordError("invalid_did")
    encoded = did[9:]
    value = 0
    for char in encoded:
        value = value * 58 + ALPHABET.index(char)
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    raw = b"\x00" * (len(encoded) - len(encoded.lstrip("1"))) + raw
    if len(raw) != 34 or raw[:2] != b"\xed\x01":
        raise RecordError("invalid_did")
    return Ed25519PublicKey.from_public_bytes(raw[2:])


def nonce_text(value) -> str:
    # Stored records may carry a string or an exact JSON integer. Never accept a
    # float or coerce a bool; 19-digit nonces exceed JavaScript's safe integer range.
    if type(value) is int:
        value = str(value)
    if not isinstance(value, str) or not NONCE.fullmatch(value):
        raise RecordError("invalid_nonce")
    return value


def verify_record(room: str, record: dict) -> tuple[str, str]:
    """Return (signer, exact nonce) after checking the stored signing payload."""
    if not ROOM.fullmatch(room):
        raise InputError("invalid_room")
    key = public_key(record.get("from"))
    nonce = nonce_text(record.get("nonce"))
    text = record.get("text")
    if not isinstance(text, str):
        raise RecordError("invalid_text")
    signature = record.get("sig")
    if not isinstance(signature, str) or not SIGNATURE.fullmatch(signature):
        raise RecordError("invalid_signature_encoding")
    raw = base64.urlsafe_b64decode(signature + "==")
    if base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=") != signature:
        raise RecordError("invalid_signature_encoding")
    try:
        payload = f"{room}|{nonce}|{text}".encode("utf-8")
    except UnicodeEncodeError:
        raise RecordError("invalid_text") from None
    try:
        key.verify(raw, payload)
    except InvalidSignature:
        raise RecordError("signature_mismatch") from None
    return record["from"], nonce


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate_json_key")
        value[key] = item
    return value


def _reject_constant(value):
    raise ValueError("nonfinite_json_number")


def _metadata_issues(record: dict) -> list[str]:
    issues = []
    if type(record.get("seq")) is not int or not 1 <= record["seq"] <= 2**63 - 1:
        issues.append("invalid_seq")
    ts = record.get("ts")
    try:
        if not isinstance(ts, str) or not TIMESTAMP.fullmatch(ts):
            raise ValueError
        datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        issues.append("invalid_timestamp")
    sender = record.get("from")
    if not isinstance(sender, str) or not sender:
        issues.append("invalid_sender")
    text = record.get("text")
    if not isinstance(text, str) or not 1 <= len(text) <= 4096:
        issues.append("invalid_text")
    elif text != text.strip() or any(unicodedata.category(char) in FORBIDDEN_TEXT_CATEGORIES for char in text):
        issues.append("noncanonical_stored_text")
    return issues


def audit_stream(
    stream: BinaryIO,
    *,
    room: str,
    expected_did: str | None = None,
    expected_sha256: str | None = None,
    allow_unsigned: bool = False,
) -> dict:
    """Audit one room's JSONL export. All timestamps and seqs are file claims.

    Raw bytes are hashed before JSON parsing. Text is verified exactly as stored,
    without Unicode normalization. No message contents are copied to the report.
    """
    if not isinstance(room, str) or not ROOM.fullmatch(room):
        raise InputError("invalid_room")
    if expected_did is not None:
        try:
            public_key(expected_did)
        except RecordError:
            raise InputError("invalid_expected_did") from None
        if allow_unsigned:
            raise InputError("allow_unsigned_conflicts_with_expected_did")
    if expected_sha256 is not None:
        if not isinstance(expected_sha256, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", expected_sha256):
            raise InputError("invalid_expected_sha256")
        expected_sha256 = expected_sha256.lower()

    digest = hashlib.sha256()
    byte_count = 0
    physical_lines = 0
    entries = []
    counts = {"valid": 0, "invalid": 0, "missing": 0, "uncheckable": 0}
    highest_nonce = {}
    previous_seq = None
    first_seq = None
    last_seq = None
    contiguous = True
    fatal_issues = False

    while True:
        raw = stream.readline(MAX_LINE_BYTES + 1)
        if not raw:
            break
        if not isinstance(raw, bytes):
            raise InputError("binary_input_required")
        byte_count += len(raw)
        if byte_count > MAX_INPUT_BYTES:
            raise InputError("input_exceeds_64_mib")
        if len(raw) > MAX_LINE_BYTES:
            raise InputError("line_exceeds_256_kib")
        physical_lines += 1
        digest.update(raw)
        if not raw.strip():
            continue
        if len(entries) >= MAX_RECORDS:
            raise InputError("input_exceeds_100000_records")

        entry = {
            "line": physical_lines,
            "line_sha256": hashlib.sha256(raw).hexdigest(),
            "signature": "uncheckable",
            "issues": [],
        }
        try:
            record = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant)
            if not isinstance(record, dict):
                raise ValueError
        except (UnicodeDecodeError, ValueError, RecursionError):
            entry["issues"].append("malformed_json_record")
            counts["uncheckable"] += 1
            entries.append(entry)
            fatal_issues = True
            contiguous = False
            continue

        entry["issues"].extend(_metadata_issues(record))
        seq = record.get("seq")
        if "invalid_seq" not in entry["issues"]:
            entry["seq"] = seq
            if first_seq is None:
                first_seq = seq
            last_seq = seq
            if previous_seq is not None:
                if seq <= previous_seq:
                    entry["issues"].append("seq_not_increasing")
                    contiguous = False
                elif seq != previous_seq + 1:
                    entry["issues"].append("seq_gap")
                    contiguous = False
                    entry["missing_seq_range"] = [previous_seq + 1, seq - 1]
            previous_seq = seq
        else:
            contiguous = False

        if "sig" not in record:
            entry["signature"] = "missing"
            entry["issues"].append("missing_signature")
        else:
            try:
                signer, nonce = verify_record(room, record)
                entry.update(signature="valid", signer=signer, nonce=nonce)
                if expected_did is not None and signer != expected_did:
                    entry["issues"].append("unexpected_signer")
                prior = highest_nonce.get(signer)
                numeric_nonce = int(nonce)
                if prior is not None and numeric_nonce <= prior:
                    entry["issues"].append("nonce_not_increasing")
                highest_nonce[signer] = max(numeric_nonce, prior if prior is not None else -1)
            except RecordError as exc:
                entry["signature"] = "invalid"
                entry["issues"].append(str(exc))
        entry["issues"] = list(dict.fromkeys(entry["issues"]))
        if any(issue != "missing_signature" for issue in entry["issues"]):
            fatal_issues = True
        counts[entry["signature"]] += 1
        entries.append(entry)

    file_sha256 = digest.hexdigest()
    hash_matches = file_sha256 == expected_sha256 if expected_sha256 is not None else None
    input_issues = []
    if hash_matches is False:
        input_issues.append("file_hash_mismatch")
        fatal_issues = True
    if not entries:
        input_issues.append("empty_input")
    if fatal_issues:
        status = "failed"
    elif not entries or (counts["missing"] and not allow_unsigned):
        status = "incomplete"
    else:
        status = "passed"

    return {
        "schema_version": 1,
        "tool_version": __version__,
        "status": status,
        "room": room,
        "expected_did": expected_did,
        "allow_unsigned": allow_unsigned,
        "evidence": {
            "sha256": file_sha256,
            "bytes": byte_count,
            "physical_lines": physical_lines,
            "expected_sha256": expected_sha256,
            "hash_matches": hash_matches,
        },
        "summary": {"records": len(entries), "signatures": counts, "input_issues": input_issues},
        "coverage": {
            "first_observed_seq": first_seq,
            "last_observed_seq": last_seq,
            "contiguous_in_file": contiguous if entries else None,
            "starts_at_seq_one": first_seq == 1 if first_seq is not None else None,
            "whole_room_history_verified": False,
        },
        "scope": {
            "authenticated_fields": ["room", "from (public key)", "nonce", "text"],
            "server_metadata_authenticated": False,
            "source_or_room_owner_verified": False,
            "settlement_verified": False,
            "airdrop_eligibility_verified": False,
        },
        "records": entries,
    }
