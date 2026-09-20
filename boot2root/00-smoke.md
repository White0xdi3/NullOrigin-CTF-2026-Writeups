# 00-smoke

**Category:** Boot2Root · **Difficulty:** Warm-up

**Flags:**
- User: `Null0rigin{the_wordlist_was_the_target_all_along}`
- Root: `Null0rigin{two_figures_off_a_payroll_sheet}`

## Overview

Alpine Linux, 3 GB disk, 1 GB RAM, 1 vCPU, NAT. Import the OVA, boot it, find
it on your network. Three TCP ports answer — start with whichever one talks
back.

This is stage 00, the gentlest box in the Boot2Root chain, and it exists to
teach the method every later stage assumes you already know: **the target's
own documents are the wordlist, the password policy is a hashcat rule, and
one number off a payroll sheet is worth a hundred times the GPU time.**

## The mechanism

Every crack on this board is sha512crypt (`-m 1800`) run in hybrid mode
(`-a 6`): a wordlist harvested from the box, plus a mask built from its
password policy.

```
hashcat -a 6 -m 1800 hash.txt vocab.txt '<mask>' -1 '!@#$%&' -j '<rule>' \
        -w 4 --hwmon-temp-abort 95
```

**`--hwmon-temp-abort 95` is not optional on a laptop GPU.** hashcat's
default abort threshold is 90°C, and a card that sits at 86–88°C under
sustained load will trip that guard on a normal thermal spike. On the
reference card, `-w 3` died at 55 seconds and `-w 4` at 15 — both with a
temperature message that reads like the challenge is broken. At 95°C the
same card ran full tilt for the whole sweep and never came close.

Reference figures for this stage, measured rather than estimated:

| | keyspace | sustained rate | full sweep |
|---|---|---|---|
| with the seam number | 18,300,000 | 34,500 H/s | **8.8 min** |
| without it | 1,830,000,000 | 34,500 H/s | **14.7 h** |

Fourteen hours isn't a punishment — it's the box telling you that you're
missing something, rather than letting you grind through overnight and learn
nothing from it.

## Notes

**rockyou is worthless here.** The vocabulary is nineteenth-century colliery
surnames and pit jargon. Roughly a quarter of the harvest happens to overlap
the leaked corpus, but nothing you actually need does — every credential on
the box was audited against rockyou before it shipped, and against every
word common to the other stages, so a wordlist carried over from another box
won't help either.

**Something on this box does crack in seconds against rockyou.** It isn't a
shortcut — nothing else here cracks in under eight minutes, and that
contrast is the tell that it's a decoy.

## Scoring

Two flags. The user flag comes out of a sealed docket in the plant account's
home directory; the root flag out of a sealed docket in root's. Both are
ciphertext on disk, so mounting the disk image gets you two blobs. The root
docket also refuses to open unless it's running on the box it was sealed
against — carrying the disk image elsewhere doesn't work, and what it prints
instead is shaped exactly like a flag and is not one.
