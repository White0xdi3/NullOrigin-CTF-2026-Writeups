# 19-revenant

**Category:** Forensics · **Difficulty:** Hard

**Flag:**
```
Null0rigin{the_clone_never_reseeded_the_rng}
```

## What ships

`suspend-A.raw` and `suspend-B.raw` — 10,641 bytes each, deliberately small: this stage's difficulty is in the crypto reasoning, not in wading through volume (that's 18-carrier's job). `template.txt` — 256 bytes, byte-for-byte identical to clone A's note before either clone ever ran.

This stage is unlocked by 18-carrier and unlocks the meta, 20-nullwatch.

## The mechanism

Both snapshots are clones of one suspended golden image, and the clone process never reseeded the guest's CSPRNG — so both clones produce the identical "random" keystream the first time they encrypt something. Each holds one 256-byte key-escrow note XORed with that same keystream: clone A's note is still the pre-rotation placeholder, while clone B's holds the real key.

This is a textbook two-time pad, broken the standard way: `keystream = ciphertext_A XOR template`, where `template.txt` is clone A's plaintext exactly, because the pre-rotation note is a fixed fleet-wide convention rather than per-machine secret data. Then `plaintext_B = ciphertext_B XOR keystream`. The recovered `secret:` field is a 32-byte AES key that opens `revenant.sealed` directly.

Unlike stages 14 through 18, this box's key is *not* `SHA-256(flag)` — the point of this stage is exactly that the recovered key opens the box, and there's no perceptual step to protect here. The hardness is entirely in recognizing the reused-keystream vulnerability and doing the crib-drag correctly.

Two plain decoys — `Null0rigin{rotation_log_stale}` and an HTTP-history-shaped `Null0rigin{escrow_backup_wrong}` — sit in the surrounding filler, free to `strings`: volume, not a twist.

## Design note: why template.txt matches clone A exactly

An earlier draft made the template's secret field an explicit "unknown" placeholder, distinct from clone A's actual all-zero placeholder, meaning to force a `ciphertext_A XOR ciphertext_B` leak-based guess instead of a direct keystream recovery. That version is unsolvable as designed: the one region you actually need the keystream for (the secret field) is exactly the region the template deliberately doesn't cover, and you can't get it from the surrounding known bytes, because a keystream only decrypts where you use its bytes at the same position. This would have been a real self-inflicted "impossible stage" bug had it shipped — it was caught in testing before it went further than a draft.

## The break

1. Find the ciphertext note in each snapshot (fixed offset; nothing marks it directly, and recognizing "this looks like the same 256 bytes, differently scrambled, in both files" is part of the stage).
2. Compute `keystream = ciphertext_A XOR template.txt`.
3. Compute `plaintext_B = ciphertext_B XOR keystream` and parse the `secret:` field.
4. Use that 32-byte key to open `revenant.sealed`.

## Solve

`solve/solve.py` performs all four steps and asserts the recovered flag matches. Like 18-carrier, this stage has no perceptual gate, so the solve script produces the flag itself rather than stopping at a rendered image.
