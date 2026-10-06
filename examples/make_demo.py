"""Emit synthetic records; the fresh signing key stays in memory and is discarded."""

import base64
import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def main():
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    value = int.from_bytes(b"\xed\x01" + public, "big")
    encoded = ""
    while value:
        value, remainder = divmod(value, 58)
        encoded = ALPHABET[remainder] + encoded
    did = "did:key:z" + encoded
    for seq, text in enumerate(["Synthetic demonstration, no live post.", "Synthetic demonstration, no payment."], 1):
        nonce = str(9_000_000_000_000_000_000 + seq)
        payload = f"demo-room|{nonce}|{text}".encode("utf-8")
        sig = base64.urlsafe_b64encode(key.sign(payload)).decode("ascii").rstrip("=")
        print(json.dumps({"seq": seq, "ts": "2026-01-01T00:00:00Z", "from": did,
                          "nonce": nonce, "text": text, "sig": sig}, ensure_ascii=True))


if __name__ == "__main__":
    main()
