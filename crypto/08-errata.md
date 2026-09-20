# 08-errata

**Category:** Cryptography · **Difficulty:** Not recorded

**Flag:**
```
Null0rigin{you_took_the_plaintext_out_of_the_checksum}
```

Unlocked by **07-daybook**; solving it unlocks **09-catalogue**.

## Editorial note

The detailed writeup source for this stage was empty in the archive used to prepare this repository — only the flag file survived intact. Rather than invent a mechanism, what follows is limited strictly to what can be confirmed from the flag string itself and from the handful of cross-references to this stage found inside the 07-daybook and 13-lantern writeups. This page should be replaced with the full writeup if the original notes can be recovered.

## What ships

Not recoverable from the surviving material.

## The mechanism

Not recoverable in detail. The one concrete technical fact that survives is embedded in 13-lantern's accounting of what it consumes from every prior stage: the internal secret this stage contributes is described as "SHA-256 over a 512-column linear map's columns in walking-ones order" (32 bytes). That implies some linear map — call it `G` — with 512 columns, recovered one at a time via walking-ones probing (toggling a single input bit at a time to isolate each column of a linear transform), then canonicalized by hashing all 512 columns in that fixed probing order. The flag text ("you took the plaintext out of the checksum") is consistent with a checksum or MAC construction built on a linear map, broken by recovering plaintext that construction was meant to protect. Beyond this, the underlying cipher/checksum construction and the attack against it are not documented in what remains.

## The break

Not documented in the surviving material.

## Why it's hard / why there's no shortcut

Not documented in the surviving material.

## Solve

Not documented in the surviving material; no solve-script details survived either.

**Feeds the finale:** the internal secret this stage contributes to 13-lantern is SHA-256 over the 512 columns of the stage's linear map, taken in walking-ones order (32 bytes).
