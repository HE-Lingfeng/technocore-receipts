import base64
import copy
import hashlib
import io
import json
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from technocore_receipts.audit import ALPHABET, InputError, audit_stream


def did_for(key):
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    raw = b"\xed\x01" + public
    value = int.from_bytes(raw, "big")
    encoded = ""
    while value:
        value, remainder = divmod(value, 58)
        encoded = ALPHABET[remainder] + encoded
    return "did:key:z" + encoded


class AuditTests(unittest.TestCase):
    def setUp(self):
        # Keys are synthetic, generated in memory, and never serialized.
        self.key = Ed25519PrivateKey.generate()
        self.did = did_for(self.key)

    def record(self, seq=1, nonce="9000000000000000001", text="Synthetic record.", *, key=None, room="demo-room"):
        key = key or self.key
        nonce_wire = str(nonce)
        sig = base64.urlsafe_b64encode(key.sign(f"{room}|{nonce_wire}|{text}".encode())).decode().rstrip("=")
        return {"seq": seq, "ts": "2026-01-01T00:00:00Z", "from": did_for(key), "nonce": nonce,
                "text": text, "sig": sig}

    def encode(self, records):
        return b"".join((json.dumps(item, ensure_ascii=True) + "\n").encode() for item in records)

    def audit(self, records, **options):
        return audit_stream(io.BytesIO(self.encode(records)), room="demo-room", **options)

    def test_valid_export_and_exact_hash(self):
        records = [self.record(), self.record(2, "9000000000000000002")]
        raw = self.encode(records)
        report = audit_stream(io.BytesIO(raw), room="demo-room", expected_did=self.did,
                              expected_sha256=hashlib.sha256(raw).hexdigest().upper())
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["summary"]["signatures"]["valid"], 2)
        self.assertTrue(report["evidence"]["hash_matches"])
        self.assertEqual(report["evidence"]["bytes"], len(raw))
        self.assertEqual(report["records"][0]["line_sha256"], hashlib.sha256(raw.splitlines(keepends=True)[0]).hexdigest())
        self.assertFalse(report["coverage"]["whole_room_history_verified"])

    def test_changed_text_is_rejected(self):
        record = self.record()
        record["text"] = "Changed after signing."
        report = self.audit([record])
        self.assertEqual(report["status"], "failed")
        self.assertIn("signature_mismatch", report["records"][0]["issues"])

    def test_corrupted_signature_bytes_are_rejected(self):
        record = self.record()
        self.assertEqual(self.audit([record])["status"], "passed")
        signature = bytearray(base64.urlsafe_b64decode(record["sig"] + "=="))
        signature[0] ^= 1
        record["sig"] = base64.urlsafe_b64encode(signature).decode().rstrip("=")
        report = self.audit([record])
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["summary"]["signatures"]["invalid"], 1)
        self.assertIn("signature_mismatch", report["records"][0]["issues"])
        self.assertNotIn("invalid_signature_encoding", report["records"][0]["issues"])

    def test_wrong_room_is_rejected(self):
        report = audit_stream(io.BytesIO(self.encode([self.record()])), room="other-room")
        self.assertEqual(report["summary"]["signatures"]["invalid"], 1)

    def test_changed_nonce_is_rejected(self):
        record = self.record()
        record["nonce"] = "9000000000000000002"
        self.assertEqual(self.audit([record])["status"], "failed")

    def test_wrong_sender_is_rejected(self):
        record = self.record()
        record["from"] = did_for(Ed25519PrivateKey.generate())
        self.assertIn("signature_mismatch", self.audit([record])["records"][0]["issues"])

    def test_unexpected_valid_signer_is_separate_from_signature_failure(self):
        other = Ed25519PrivateKey.generate()
        report = self.audit([self.record(key=other)], expected_did=self.did)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["records"][0]["signature"], "valid")
        self.assertIn("unexpected_signer", report["records"][0]["issues"])

    def test_signature_base64_pad_bits_must_be_canonical(self):
        record = self.record()
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        signature = record["sig"]
        record["sig"] = signature[:-1] + alphabet[alphabet.index(signature[-1]) + 1]
        self.assertEqual(base64.urlsafe_b64decode(signature + "=="), base64.urlsafe_b64decode(record["sig"] + "=="))
        self.assertIn("invalid_signature_encoding", self.audit([record])["records"][0]["issues"])

    def test_bad_did_is_not_echoed(self):
        record = self.record()
        record["from"] = "malicious_sender_content"
        report = self.audit([record])
        self.assertIn("invalid_did", report["records"][0]["issues"])
        self.assertNotIn("malicious_sender_content", json.dumps(report))

    def test_integer_nonce_keeps_nineteen_digit_precision(self):
        report = self.audit([self.record(nonce=9000000000000000001)])
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["records"][0]["nonce"], "9000000000000000001")

    def test_noninteger_nonces_fail(self):
        for nonce in [True, False, 1.0, -1, "1e19", "1" * 20, None]:
            with self.subTest(nonce=nonce):
                record = self.record()
                record["nonce"] = nonce
                self.assertIn("invalid_nonce", self.audit([record])["records"][0]["issues"])

    def test_leading_zero_nonce_is_verified_exactly(self):
        self.assertEqual(self.audit([self.record(nonce="00012")])["status"], "passed")

    def test_nonce_replay_is_detected_even_with_new_server_metadata(self):
        record = self.record()
        replay = copy.deepcopy(record)
        replay["seq"] = 2
        replay["ts"] = "2026-01-02T00:00:00Z"
        report = self.audit([record, replay])
        self.assertEqual(report["summary"]["signatures"]["valid"], 2)
        self.assertEqual(report["status"], "failed")
        self.assertIn("nonce_not_increasing", report["records"][1]["issues"])

    def test_nonce_order_tracks_high_water_mark(self):
        records = [self.record(1, "10"), self.record(2, "8"), self.record(3, "9")]
        report = self.audit(records)
        self.assertIn("nonce_not_increasing", report["records"][1]["issues"])
        self.assertIn("nonce_not_increasing", report["records"][2]["issues"])

    def test_invalid_signature_cannot_poison_nonce_tracker(self):
        invalid = self.record(1, "99")
        invalid["text"] = "tampered"
        report = self.audit([invalid, self.record(2, "10")])
        self.assertNotIn("nonce_not_increasing", report["records"][1]["issues"])

    def test_nonce_counters_are_per_signer(self):
        other = Ed25519PrivateKey.generate()
        self.assertEqual(self.audit([self.record(1, "10"), self.record(2, "1", key=other)])["status"], "passed")

    def test_sequence_gap_is_reported_without_inventing_records(self):
        report = self.audit([self.record(50, "1"), self.record(53, "2")])
        self.assertEqual(report["records"][1]["missing_seq_range"], [51, 52])
        self.assertFalse(report["coverage"]["contiguous_in_file"])
        self.assertFalse(report["coverage"]["starts_at_seq_one"])

    def test_partial_retained_export_is_not_claimed_as_complete_history(self):
        report = self.audit([self.record(50)])
        self.assertEqual(report["status"], "passed")
        self.assertTrue(report["coverage"]["contiguous_in_file"])
        self.assertFalse(report["coverage"]["whole_room_history_verified"])

    def test_duplicate_and_decreasing_sequence(self):
        for seq in [1, 2]:
            with self.subTest(seq=seq):
                report = self.audit([self.record(2, "1"), self.record(seq, "2")])
                self.assertIn("seq_not_increasing", report["records"][1]["issues"])

    def test_server_metadata_is_not_authenticated_by_sender(self):
        record = self.record()
        record.update(seq=700, ts="2026-08-01T12:00:00Z")
        report = self.audit([record])
        self.assertEqual(report["records"][0]["signature"], "valid")
        self.assertFalse(report["scope"]["server_metadata_authenticated"])
        self.assertFalse(report["scope"]["settlement_verified"])

    def test_invalid_metadata_does_not_disguise_valid_signature(self):
        for field, value, issue in [("seq", True, "invalid_seq"), ("seq", "1", "invalid_seq"),
                                     ("ts", "2026-02-30T00:00:00Z", "invalid_timestamp"),
                                     ("ts", "2026-01-01T00:00:00", "invalid_timestamp")]:
            with self.subTest(field=field, value=value):
                record = self.record()
                record[field] = value
                report = self.audit([record])
                self.assertEqual(report["records"][0]["signature"], "valid")
                self.assertIn(issue, report["records"][0]["issues"])
                self.assertEqual(report["status"], "failed")

    def test_unsigned_is_missing_not_invalid(self):
        record = self.record()
        del record["sig"]
        report = self.audit([record])
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["summary"]["signatures"]["missing"], 1)
        self.assertEqual(report["summary"]["signatures"]["invalid"], 0)
        self.assertEqual(self.audit([record], allow_unsigned=True)["status"], "passed")

    def test_null_signature_is_invalid_not_unsigned(self):
        record = self.record()
        record["sig"] = None
        self.assertEqual(self.audit([record])["summary"]["signatures"]["invalid"], 1)

    def test_unsigned_cannot_satisfy_pinned_signer(self):
        record = self.record()
        del record["sig"]
        self.assertEqual(self.audit([record], expected_did=self.did)["status"], "incomplete")
        with self.assertRaisesRegex(InputError, "allow_unsigned_conflicts"):
            self.audit([record], expected_did=self.did, allow_unsigned=True)

    def test_unicode_normalization_is_never_applied(self):
        record = self.record(text="Caf\u00e9")
        self.assertEqual(self.audit([record])["status"], "passed")
        record["text"] = "Cafe\u0301"
        self.assertIn("signature_mismatch", self.audit([record])["records"][0]["issues"])
        self.assertEqual(self.audit([self.record(text="Cafe\u0301")])["status"], "passed")

    def test_stored_text_must_already_have_single_line_sweep(self):
        for text in ["hello\nworld", "hello\u202eworld", " hello ", "hello\ue000world"]:
            with self.subTest(text=text):
                report = self.audit([self.record(text=text)])
                self.assertEqual(report["records"][0]["signature"], "valid")
                self.assertIn("noncanonical_stored_text", report["records"][0]["issues"])

    def test_message_body_is_never_in_report(self):
        report = self.audit([self.record(text="DO_NOT_EXECUTE_THIS_MESSAGE")])
        self.assertNotIn("DO_NOT_EXECUTE_THIS_MESSAGE", json.dumps(report))

    def test_malformed_json_is_isolated_and_later_record_is_checked(self):
        raw = b"not-json\n" + self.encode([self.record(2)])
        report = audit_stream(io.BytesIO(raw), room="demo-room")
        self.assertEqual(report["summary"]["signatures"]["uncheckable"], 1)
        self.assertEqual(report["summary"]["signatures"]["valid"], 1)
        self.assertFalse(report["coverage"]["contiguous_in_file"])
        self.assertEqual(report["records"][1]["line"], 2)

    def test_duplicate_json_keys_and_nonfinite_values_are_rejected(self):
        for raw in [b'{"seq":1,"seq":2}\n', b'{"seq":NaN}\n', b'[]\n', b'null\n', b'\xff\n']:
            with self.subTest(raw=raw):
                report = audit_stream(io.BytesIO(raw), room="demo-room")
                self.assertIn("malformed_json_record", report["records"][0]["issues"])

    def test_file_commitment_mismatch_is_separate_from_valid_signatures(self):
        report = self.audit([self.record()], expected_sha256="0" * 64)
        self.assertFalse(report["evidence"]["hash_matches"])
        self.assertEqual(report["summary"]["signatures"]["valid"], 1)
        self.assertEqual(report["status"], "failed")

    def test_empty_input_cannot_pass(self):
        report = self.audit([], allow_unsigned=True)
        self.assertEqual(report["status"], "incomplete")
        self.assertIn("empty_input", report["summary"]["input_issues"])
        self.assertIsNone(report["coverage"]["contiguous_in_file"])

    def test_blank_lines_and_crlf_are_in_raw_hash(self):
        raw = b"\n" + self.encode([self.record()]).replace(b"\n", b"\r\n") + b" \t\n"
        report = audit_stream(io.BytesIO(raw), room="demo-room")
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["evidence"]["physical_lines"], 3)
        self.assertEqual(report["records"][0]["line"], 2)
        self.assertEqual(report["evidence"]["sha256"], hashlib.sha256(raw).hexdigest())

    def test_input_and_line_budgets_fail_without_partial_success_report(self):
        raw = self.encode([self.record()])
        with patch("technocore_receipts.audit.MAX_INPUT_BYTES", 1):
            with self.assertRaisesRegex(InputError, "input_exceeds"):
                audit_stream(io.BytesIO(raw), room="demo-room")
        with patch("technocore_receipts.audit.MAX_LINE_BYTES", 1):
            with self.assertRaisesRegex(InputError, "line_exceeds"):
                audit_stream(io.BytesIO(raw), room="demo-room")
        with patch("technocore_receipts.audit.MAX_RECORDS", 0):
            with self.assertRaisesRegex(InputError, "records"):
                audit_stream(io.BytesIO(raw), room="demo-room")

    def test_invalid_context_arguments_are_rejected(self):
        for room in ["../../other", "demo|room", "", "A", None]:
            with self.subTest(room=room):
                with self.assertRaises(InputError):
                    audit_stream(io.BytesIO(), room=room)
        with self.assertRaisesRegex(InputError, "invalid_expected_did"):
            self.audit([], expected_did="not-a-key")
        with self.assertRaisesRegex(InputError, "invalid_expected_sha256"):
            self.audit([], expected_sha256="not-a-hash")


if __name__ == "__main__":
    unittest.main()
