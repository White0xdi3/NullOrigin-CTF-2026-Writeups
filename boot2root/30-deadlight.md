# 30-deadlight

**Category:** Boot2Root · **Difficulty:** Hard

**Flags:**
- User: `Null0rigin{the_lamp_told_you_by_going_out}`
- Root: `Null0rigin{a_deadlight_is_a_reading_not_a_failure}`

## Overview

A deadlight is a safety lamp that has gone out. It goes out because the air
will no longer support a flame — and the moment it goes out is the moment
the deputy learns the air will no longer support him either. The lamp isn't
a light; it's an instrument, and its readings are all negative: the cap
that doesn't stand, the flame that doesn't hold, the light that isn't there.

This box is built to be most informative at the exact moment it denies you
something. Every gate that refuses tells you why, precisely, and the final
gate is nothing but refusals — it never prints the flag for a wrong sample;
it names the gas that put the lamp out, and the gas tells you which of your
three hard-won components is wrong. If you can't get a straight answer out
of this box, you haven't been paying attention to the crooked ones.

What ships: a document store that seeds the wordlist harvest, a personnel
extract with seam assignments, a firmware blob to carve and de-XOR, an
assay bundle, a key escrow, a checkpoint race, a readings database with one
impossible row, a keeper escrow, root's shadow line, and a sealed root flag
that needs a live TOTP-style seed assembled from three fragments collected
along the way.

## The chain — eighteen gates

**Act I — the wire**

1. Scan: ssh, plus `lampd` (7009), `deadlightd` (8088), and `gasnetd` (9110).
2. `GET /` — the public index, the lamp-room register.
3. `lampd` — a stateful five-verb handshake; get the verb order wrong
   (gauze before open, for instance) and the lamp goes out. Get it right
   and it hands back a live gas reading.
4. `CRC32(reading)` unlocks `/records.tar` — harvest the site vocabulary.
5. `/firmware.bin` — carve it out, de-XOR it, repair the gzip magic bytes,
   and unpack it for the credential policy, the personnel extract (seam
   numbers), two known plaintexts, and the first seed fragment.

**Act II — the foothold**

6. Crack 1 (bundle class) opens `lamp-assay.7z`.
7. Crack 2 (contractor class) decrypts the `apiuser` SSH key passphrase.
8. SSH in as `apiuser`, land in `lampsh`, a restricted shell.
9. Escape `lampsh` — exactly one permitted binary allows it.
10. The race: `checkpoint.sh` is group-writable for four seconds in every
    sixty.
11. `readings.db` holds one physically impossible row — decode it for the
    second seed fragment.

**Act III — lateral movement**

12. Crack 3 (staff class) recovers the keeper's password.
13. Reuse that password against the keeper's control port — not against
    ssh, which has password auth disabled entirely.
14. An off-by-one in the control port's `FETCH idx <= n` handler lets you
    read one record past the end — arbitrary read, landing root's shadow
    line and the third seed fragment.
15. Crack 4 (staff class) recovers root's password.

**Act IV — root and the seal**

16. `doas` plus a TOTP-style check: the seed is fragment A || B || C, and
    it only validates while the box's current boot is the one that sealed
    it — root's password alone is not enough.
17. Crack 5 (contractor class) recovers the seal phrase from `/root/.seal`.
18. The relight: `SHA256(chain || seal || seed)`. A wrong sample doesn't
    just fail — it names the gas, and the gas tells you which of the three
    components (chain key, seal phrase, seed) is wrong.

## Credentials recovered

| Account | Class | Password | Mask | Rule |
|---|---|---|---|---|
| daybook | staff | `Shawbottom53461%` | `53?d?d?d?1` | `c` |
| stores | bundle | `dl-dringcroft83074%` | `83?d?d?d?1` | `^-^l^d` |
| bundle | bundle | `dl-holwick46917#` | `46?d?d?d?1` | `^-^l^d` |
| apikey | contractor | `R0wb0td4l371234$` | `71?d?d?d?1` | `c sa4 se3 si1 so0 ss5` |
| keeper | staff | `Thistlerake24287@` | `24?d?d?d?1` | `c` |
| root | staff | `Chimneystem54449&` | `54?d?d?d?1` | `c` |
| seal | contractor | `F0rdb0th0m94280#` | `94?d?d?d?1` | `c sa4 se3 si1 so0 ss5` |

## GPU calibration

| | keyspace | full sweep (49,700 H/s) |
|---|---|---|
| seam number known | 42,882,000 | ~14.4 min |
| seam number unknown | 4,288,200,000 | ~24.0 h |

Five real crack stages at roughly fourteen minutes of full sweep each —
budget about seventy minutes of GPU time for a from-scratch solve.

## Decoys

- **`gasnetd`'s traversal.** Reachable, and it does hand back something
  flag-shaped — `Null0rigin{uid_zero_inside_is_uid_nobody_outside}` — but
  it's wrong. It's a lesson about container/namespace UID mapping, not a
  step on the real chain.
- **The rockyou backup shadow.** A one-line backup shadow file is
  reachable and does crack instantly against rockyou, yielding
  `Null0rigin{fourteen_million_words_and_none_of_them_this}` — also wrong,
  and the speed is the tell. Nothing on the real chain cracks that fast.
- **The bench on a disk that isn't running.** Mounting the disk image
  offline and trying to run the final check against it fails by design —
  the seal is bound to a live, running boot, not to the disk contents
  alone.

## Solve walkthrough

A full run against a booted copy of the shipped image, in a mode that takes
each password from the verified answer key and confirms it against the
shipped `$6$` hash with an independent implementation rather than
re-running hashcat — every other gate, including the boot-bound unseal at
the end, is exercised for real.

```
== 1  scan: four services, and only one of them is the way in ==
   ok   ssh
   ok   lampd on 7009
   ok   deadlightd on 8088
   ok   gasnetd on 9110

== 2  the plant server's public pages ==
   ok   lamp no.1, bench at 779 fathoms

== 3  the lamp station: five verbs, in order, or it goes out ==
   ok   GAUZE before OPEN puts the lamp out, as posted
   ok   reading=4790

== 4  the lamp token unlocks the record store; harvest the vocabulary ==
   ok   token=5774fee9
   ok   no token, no store
   ok   7147 words, matching the reference harvest

== 5  the firmware blob: carve, de-XOR, repair, unpack ==
   ok   carved 2771 bytes at offset 1168 -> ['CREDENTIAL-STANDARD.txt', 'ESCROW-BUNDLE.txt',
        'PERSONNEL-EXTRACT.txt', 'SEED-FRAGMENT-A.txt', 'STORES-NOTE.txt']
   ok   seed fragment A = C4WSWU
   ok   every seam figure is two digits

== 6  CRACK 1 -- the assay bundle, bundle class ==
   bundle: class=bundle seam=46 mask=46?d?d?d?1 rule='^-^l^d'
   ok   bundle password: dl-holwick46917#
   ok   bundle opened: BENCH-NOTE.txt ESCROW-APIKEY.txt KNOWN-PLAINTEXT.txt id_ed25519

== 7  CRACK 2 -- the key passphrase, contractor class ==
   apikey: class=contractor seam=71 mask=71?d?d?d?1 rule='c sa4 se3 si1 so0 ss5'
   ok   key passphrase: R0wb0td4l371234$
   ok   key decrypted

== 8  ssh apiuser -- and land in a restricted shell ==
   ok   uid=1002(apiuser) gid=1002(apiuser) groups=1001(ops),1002(apiuser),1010(lamp)
   ok   lampsh refuses find, and says so

== 9  escape lampsh with the one permitted binary that allows it ==
   ok   awk 'BEGIN{system("/bin/sh")}' -> a real shell

== 10 the four-second race on the checkpoint ==
   ok   window won, checkpoint ran as assay
   ok   user flag: Null0rigin{the_lamp_told_you_by_going_out}

== 11 the readings store: the one row that cannot be a real reading ==
   ok   row 408, cap 21.0
   ok   seed fragment B = HX6IP, and the keeper's escrow

== 12 CRACK 3 -- the keeper account, staff class ==
   keeper: class=staff seam=24 mask=24?d?d?d?1 rule='c'
   ok   keeper password: Thistlerake24287@

== 13 the reuse is onto an internal service, not onto sshd ==
   ok   sshd will not take it (password auth is off entirely)
   ok   keeperd on the internal control port accepted it

== 14 the off-by-one: FETCH the record the keeper does not have ==
   ok   leaked the root shadow line and seed fragment C = RF4SZ
   ok   bench seed = C4WSWUHX6IPRF4SZ  (A|B|C)

== 15 CRACK 4 -- root, staff class ==
   root: class=staff seam=54 mask=54?d?d?d?1 rule='c'
   ok   root password: Chimneystem54449&

== 16 doas the bench -- root's password alone is not enough ==
   ok   wrong seed -> whitedamp, which is the bench saying which one is wrong
   ok   root shell, on this boot only

== 17 CRACK 5 -- the seal phrase, contractor class ==
   seal: class=contractor seam=94 mask=94?d?d?d?1 rule='c sa4 se3 si1 so0 ss5'
   ok   seal phrase: F0rdb0th0m94280#

== 18 the relight ==
   ok   wrong chain key -> firedamp
   ok   wrong seal phrase -> afterdamp

== decoy 1  gasnetd's traversal lands in a jail ==
   ok   reachable, and wrong: Null0rigin{uid_zero_inside_is_uid_nobody_outside}

== decoy 2  the rockyou backup shadow ==
   ok   reachable, and wrong: Null0rigin{fourteen_million_words_and_none_of_them_this}

== result ==
   root flag: Null0rigin{a_deadlight_is_a_reading_not_a_failure}

OK -- eighteen gates, five cracks, root flag earned by the intended path.
```

## Notes

- The final gate never just fails. A wrong chain key surfaces as
  "firedamp," a wrong seal phrase as "afterdamp," and a wrong seed as
  "whitedamp" — each name tells you exactly which of the three components
  to go re-check, in keeping with the box's whole design philosophy: every
  refusal is itself a reading.
- The root seal is bound to the live boot. Mounting the disk offline and
  trying the same check against it is tested separately and fails by
  design — that's decoy 3, not a bug.
