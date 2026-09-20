# 28-blackdamp

**Category:** Boot2Root · **Difficulty:** Hard

**Flags:**
- User: `Null0rigin{the_seam_number_was_two_of_the_four}`
- Root: `Null0rigin{you_paid_for_every_candidate}`

## Overview

Blackdamp is a colliery-themed hardened box built around the same core
method as the rest of the chain — harvest the site's own documents into a
wordlist, turn the posted password policy into a hashcat rule, and use one
number lifted from a personnel record to cut the keyspace by a hundred times
— but stretched across eighteen gated steps and four separate cracks.

What ships:

- a document store (`pit-records`) that seeds the wordlist harvest
- a personnel record with seam assignments — the number that collapses the
  keyspace
- a posted credential standard that doubles as the hashcat rule spec
- a firmware blob to carve and repair
- an assay bundle, an SSH key, a KeePass-style vault, and finally
  `/etc/shadow` — four cracks, each unlocking the next stage

## The chain

1. **Recon.** Enumerate the open services; five ports answer, including
   plain HTTP and an SSH daemon.
2. **The firmware blob.** Carve the payload out of the served firmware
   image, verify its repaired checksum against the header, and pull the
   plant key plus a batch of documents out of the unpacked filesystem
   (credential standard, staff mailbox, personnel extract, a bench note).
3. **The live handshake.** A small protocol service (`lampd`) requires a
   stateful exchange before it will hand back a live gas reading and a
   fragment of the eventual TOTP seed.
4. **Harvest the vocabulary.** Every document pulled off the box so far —
   mail, personnel records, bench notes — feeds the wordlist. One staff
   mailbox contains a known plaintext password, which is enough to confirm
   the mask and rule before spending any real GPU time.
5. **Crack 1 — the assay bundle** (bundle class). Opens a `.7z` archive
   containing a second known plaintext and a fragment of the eventual seed.
6. **Crack 2 — the contractor key** (contractor class). Decrypts an SSH
   private key belonging to the `www` service account.
7. **Land in a restricted shell.** The `www` account drops into a locked-down
   menu shell exposing only a handful of read-only plant tools. Exactly one
   of the permitted binaries is enough to escape it.
8. **Win the race.** A supervisor process runs a script as the `assay`
   account on a fixed schedule; the script is group-writable for roughly
   four seconds in every sixty. Land a write in that window to pivot to
   `assay`.
9. **The readings store.** The `assay` account can read a small database of
   sensor readings. One row is physically impossible — that's the tell,
   and decoding it hands over the user flag plus the key-store hash for the
   next crack.
10. **Crack 3 — the vault** (staff class). Recovers the password on a
    KeePass-style vault.
11. **The internal service and the off-by-one.** A control service reachable
    only from inside the box has an off-by-one in its record fetch that
    leaks an out-of-bounds record — in this case, root's shadow line and a
    third seed fragment.
12. **Crack 4 — root** (staff class).
13. **The seal.** The three seed fragments recovered along the way
    concatenate into a TOTP seed. Generate the code for the current
    half-minute window to unlock the sealed root flag.

## Credentials recovered

| Account | Class | Password | Mask | Rule |
|---|---|---|---|---|
| mchugh | staff | `Elmmere91163#` | `91?d?d?d?1` | `c` |
| bundle | bundle | `bd-bridgebottom54322@` | `54?d?d?d?1` | `^-^d^b` |
| wwwkey | contractor | `H34thl0w00698$` | `00?d?d?d?1` | `c sa4 se3 si1 so0 ss5` |
| sitekdb | staff | `Drinksopp70477%` | `70?d?d?d?1` | `c` |
| root | staff | `Drinkmere11257#` | `11?d?d?d?1` | `c` |

## GPU calibration

| | keyspace | full sweep (49,700 H/s) |
|---|---|---|
| seam number known | 31,050,000 | ~10.4 min |
| seam number unknown | 3,105,000,000 | ~17.4 h |

Knowing the seam number is a 100x lever on every crack on this box.

## Solve walkthrough

A full run against a booted copy of the shipped image, with the four
passwords substituted from the verified answer key rather than cracked live
(to keep the run short) — every other gate below, including the firmware
carve, the live handshake, the restricted-shell escape, the checkpoint race,
and the off-by-one leak, is exercised for real.

```
== Act I.1  what is on the wire ==
   ssh, http, and three service ports open

== Act I.4  the firmware blob -- carve, repair, read ==
   payload at +4096, 3663 bytes, kind squashfs
   repaired md5 864ff7bd83b071a2784343d933b149be  header says 864ff7bd83b071a2784343d933b149be
   plant key ad407faa2a73c210...
   also inside: ./usr/include/assay-proto.h ./etc/assay/CREDENTIAL-STANDARD.txt
                ./etc/assay/OFFICE-MAIL.txt ./etc/assay/SHIFT-KEY.txt
                ./etc/assay/plant.shadow ./etc/assay/PERSONNEL-EXTRACT.txt
                ./etc/assay/BENCH-NOTE-41.txt

== Act I.3  the shift code, and the record store ==
   gas reading 5.98

== Act I.4  harvest the site vocabulary ==
   harvested 5175 words
   known plaintext: Elmmere91163#

== Act I.5  CRACK 1 -- the assay bundle ==
   bundle password: bd-bridgebottom54322@

== Act I.2  lampd -- the handshake is the live reading ==
   fetched lamp-assay.7z, 1231 bytes
   fragment A: ea3f9e5b
   second known plaintext: M1d5t0n353328#

== Act II.6  CRACK 2 -- the www key passphrase ==
   key passphrase: H34thl0w00698$

== Act II.7-8  the plant console, and the one way out of it ==
   uid=1001(www) gid=1001(www) groups=1001(www)
   permitted: cat date grep head id ls pitlog pitview tail uptime wc
   pitsh: sh: not a plant tool. `help' lists them.
   escaped: uid=1001(www)

== Act II.9  the race -- four seconds a minute ==
   wrote inside the window; the supervisor runs it as assay at :05
   assay: uid=1003(assay) gid=1003(assay) groups=1003(assay)

== Act II.10  the readings store, and fragment B ==
   fragment B: bda5c910
   user flag: Null0rigin{the_seam_number_was_two_of_the_four}
   key-store hash from the impossible reading: $6$bdkeystore00000x$YpMQ4L6okXaxw1BRB9Kt...
   key-store password: Drinksopp70477%

== Act III.12-13  the internal service, and the off-by-one ==
   leaked: root:$6$bdrootsalt00000x$5mQ6YvJijfZ.3pFDs2UYD...
   fragment C: f4c01df2

== Act III.14  CRACK 4 -- root ==
   root password: Drinkmere11257#

== Act IV.15-18  the seed, the code, the chain key, the seal ==
   seed: ea3f9e5bbda5c910f4c01df2
   seal code for this half-minute: 242348

== result ==
   user: Null0rigin{the_seam_number_was_two_of_the_four}
   root: Null0rigin{you_paid_for_every_candidate}
```

## Notes

A base64-decode bug turned up in step 11's handling of the anomalous sqlite
row during testing: it broke when that row's content was corrected from a
plaintext string to a proper `$6$` hash. Fixed by routing it through the
same crack path as every other credential on the box, rather than treating
it as a special case.
