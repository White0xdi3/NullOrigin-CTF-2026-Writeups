#!/usr/bin/env python3
"""34-undertone -- standalone solve.

Keyed by stage 33's flag. The real channel is direct-sequence spread
spectrum on undertone.wav's LEFT channel: each payload bit is spread over
a chunk of samples by a +-1 chip sequence taken from the key-schedule
stream, recovered by correlating and taking the sign. The chip length
isn't published anywhere -- linetest.wav is a calibration file with a
PUBLISHED key (SHA-256("LINE TEST")) and PUBLISHED plaintext, so the chip
length is found by sweeping candidates against it and checking which one
decodes to a valid container. That's a derivation, not a shortcut: it only
uses public information from the calibration file.

Run:  python3 solve.py <path-to-34-undertone-dir> <flag_33>
"""
from __future__ import annotations

import hashlib
import os
import struct
import sys
import wave
import zlib

import numpy as np

PLATE_MAGIC = b"PL8"


def K(flag: str) -> bytes:
    return hashlib.sha256(flag.encode()).digest()


def stream(k: bytes, n: int) -> bytes:
    out, c = b"", 0
    while len(out) < n:
        out += hashlib.sha256(k + struct.pack(">I", c)).digest()
        c += 1
    return out[:n]


def unplate(buf: bytes):
    if len(buf) < 10 or buf[:3] != PLATE_MAGIC:
        return None
    ln = struct.unpack("<H", buf[4:6])[0]
    crc = struct.unpack("<I", buf[6:10])[0]
    pay = buf[10:10 + ln]
    if len(pay) != ln or (zlib.crc32(pay) & 0xFFFFFFFF) != crc:
        return None
    return pay


def read_wav_left(path):
    with wave.open(path, "rb") as w:
        nch, sw, sr, nfr = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(nfr)
    a = np.frombuffer(raw, dtype="<i2").reshape(-1, nch)
    return sr, a[:, 0].astype(np.float64), a


def pn_chips(key: bytes, nchips: int):
    ks = stream(key, (nchips + 7) // 8)
    bits = np.unpackbits(np.frombuffer(ks, dtype=np.uint8))[:nchips]
    return bits.astype(np.float64) * 2.0 - 1.0


def correlate(left, key, nbits, chunk, pn=None):
    nchips = nbits * chunk
    if pn is None or len(pn) < nchips:
        pn = pn_chips(key, nchips)
    return (left[:nchips] * pn[:nchips]).reshape(nbits, chunk).sum(axis=1)


def bits_to_bytes(corr):
    return np.packbits((corr > 0).astype(np.uint8)).tobytes()


def recover(left, key, chunk, cap_bits=None):
    """Header-first: 80 bits give PL8 + version + length, which gives the rest."""
    cap = cap_bits if cap_bits else (len(left) // chunk)
    if cap < 80:
        return None
    pn = pn_chips(key, cap * chunk)
    head = bits_to_bytes(correlate(left, key, 80, chunk, pn))
    if head[:3] != PLATE_MAGIC:
        return None
    total = 10 + struct.unpack("<H", head[4:6])[0]
    if total * 8 > cap:
        return None
    return bits_to_bytes(correlate(left, key, total * 8, chunk, pn))


def sweep_chunk(left, key, candidates=(256, 512, 1024, 2048, 4096, 8192)):
    for c in candidates:
        p = recover(left, key, c)
        got = unplate(p) if p else None
        if got is not None:
            return c, got
    return None, None


def lsb_read(ch, nbytes=96):
    bits = (ch[:nbytes * 8].astype(np.uint16) & 1).astype(np.uint8)
    raw = np.packbits(bits).tobytes()
    return raw.split(b"\x00")[0]


def main() -> int:
    if len(sys.argv) < 3:
        raise SystemExit(f"usage: {sys.argv[0]} <ship_dir> <flag_33>")
    ship, prev_seal = sys.argv[1], sys.argv[2]
    undertone_path = os.path.join(ship, "undertone.wav")
    linetest_path = os.path.join(ship, "linetest.wav")

    sr, LL, a_l = read_wav_left(linetest_path)
    print(f"linetest.wav: {sr} Hz, {a_l.shape[1]} ch")

    # --- A: calibration -- sweep the chip length against the published
    # key and plaintext, since neither the encoder nor the chip length
    # is published anywhere else on the chain
    kcal = K("LINE TEST")
    chunk, cal_payload = sweep_chunk(LL, kcal)
    if chunk is None:
        raise SystemExit("could not recover the calibration payload by sweeping chip lengths")
    print(f"chip length recovered by sweep: {chunk}  (calibration payload: {cal_payload!r})")

    # --- B: the real payload, keyed by the previous stage's flag -----------
    sr2, UL, a_w = read_wav_left(undertone_path)
    key = K(prev_seal)
    p_real = recover(UL, key, chunk)
    if p_real is None:
        raise SystemExit("no PLATE header recovered from undertone.wav -- wrong previous flag?")
    payload = unplate(p_real)
    if payload is None:
        raise SystemExit("PLATE header found but CRC/container did not verify")
    flag, share = payload.split(b"\x1f")
    print("flag  :", flag.decode())
    print("share :", share.hex(), "(share 4 of 6)")

    # --- decoys on the RIGHT channel, printed as found ----------------------
    UR = a_w[:, 1]
    lsb = lsb_read(UR)
    print("decoy (right-channel sample LSB):", repr(lsb.decode("ascii", "replace")))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
