"""
Pure Python BIP-340 Schnorr signature implementation for Nostr event signing.
Reference: https://github.com/bitcoin/bips/blob/master/bip-0340.mediawiki
No external dependencies required.
"""

import hashlib
import os

# secp256k1 curve parameters
P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
G = (
    0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
    0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8,
)


def _int_from_bytes(b: bytes) -> int:
    return int.from_bytes(b, "big")


def _bytes_from_int(x: int) -> bytes:
    return x.to_bytes(32, "big")


def _tagged_hash(tag: str, msg: bytes) -> bytes:
    """BIP-340 tagged hash: SHA256(SHA256(tag) || SHA256(tag) || msg)."""
    tag_hash = hashlib.sha256(tag.encode()).digest()
    return hashlib.sha256(tag_hash + tag_hash + msg).digest()


def _point_add(p1, p2):
    """Elliptic curve point addition on secp256k1."""
    if p1 is None:
        return p2
    if p2 is None:
        return p1
    if p1[0] == p2[0] and p1[1] != p2[1]:
        return None
    if p1 == p2:
        lam = (3 * p1[0] * p1[0] * pow(2 * p1[1], P - 2, P)) % P
    else:
        lam = ((p2[1] - p1[1]) * pow(p2[0] - p1[0], P - 2, P)) % P
    x3 = (lam * lam - p1[0] - p2[0]) % P
    return (x3, (lam * (p1[0] - x3) - p1[1]) % P)


def _point_mul(point, scalar):
    """Elliptic curve scalar multiplication (double-and-add)."""
    result = None
    current = point
    for i in range(256):
        if (scalar >> i) & 1:
            result = _point_add(result, current)
        current = _point_add(current, current)
    return result


def _lift_x(x_val: int):
    """Recover a curve point from its x-coordinate (even y)."""
    if x_val >= P:
        return None
    y_sq = (pow(x_val, 3, P) + 7) % P
    y_val = pow(y_sq, (P + 1) // 4, P)
    if pow(y_val, 2, P) != y_sq:
        return None
    return (x_val, y_val if y_val % 2 == 0 else P - y_val)


def get_public_key(secret_key: bytes) -> bytes:
    """Derive the 32-byte x-only public key from a 32-byte secret key."""
    d0 = _int_from_bytes(secret_key)
    if not (1 <= d0 <= N - 1):
        raise ValueError("secret key out of range")
    point = _point_mul(G, d0)
    return _bytes_from_int(point[0])


def schnorr_sign(msg: bytes, secret_key: bytes) -> bytes:
    """
    Create a BIP-340 Schnorr signature.
    msg: 32-byte message hash (the Nostr event id).
    secret_key: 32-byte secret key.
    Returns 64-byte signature.
    """
    if len(msg) != 32:
        raise ValueError("message must be 32 bytes")
    d0 = _int_from_bytes(secret_key)
    if not (1 <= d0 <= N - 1):
        raise ValueError("secret key out of range")

    point = _point_mul(G, d0)
    d = d0 if point[1] % 2 == 0 else N - d0
    pubkey_bytes = _bytes_from_int(point[0])

    # Auxiliary randomness
    aux = os.urandom(32)
    t = _bytes_from_int(d ^ _int_from_bytes(_tagged_hash("BIP0340/aux", aux)))

    # Nonce generation
    k0 = _int_from_bytes(
        _tagged_hash("BIP0340/nonce", t + pubkey_bytes + msg)
    ) % N
    if k0 == 0:
        raise RuntimeError("nonce is zero")

    r_point = _point_mul(G, k0)
    k = k0 if r_point[1] % 2 == 0 else N - k0
    r_bytes = _bytes_from_int(r_point[0])

    # Challenge
    e = _int_from_bytes(
        _tagged_hash("BIP0340/challenge", r_bytes + pubkey_bytes + msg)
    ) % N

    sig = r_bytes + _bytes_from_int((k + e * d) % N)
    return sig


def schnorr_verify(msg: bytes, pubkey: bytes, sig: bytes) -> bool:
    """Verify a BIP-340 Schnorr signature."""
    if len(msg) != 32 or len(pubkey) != 32 or len(sig) != 64:
        return False
    point = _lift_x(_int_from_bytes(pubkey))
    if point is None:
        return False
    r = _int_from_bytes(sig[:32])
    s = _int_from_bytes(sig[32:])
    if r >= P or s >= N:
        return False
    e = _int_from_bytes(
        _tagged_hash("BIP0340/challenge", sig[:32] + pubkey + msg)
    ) % N
    r_check = _point_add(_point_mul(G, s), _point_mul(point, N - e))
    if r_check is None or r_check[1] % 2 != 0:
        return False
    return r_check[0] == r


def generate_keypair() -> tuple:
    """Generate a new secp256k1 keypair. Returns (secret_key_hex, pubkey_hex)."""
    while True:
        secret = os.urandom(32)
        d = _int_from_bytes(secret)
        if 1 <= d <= N - 1:
            pubkey = get_public_key(secret)
            return secret.hex(), pubkey.hex()
