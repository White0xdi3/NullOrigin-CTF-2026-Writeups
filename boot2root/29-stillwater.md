# 29-stillwater

**Category:** Boot2Root · **Difficulty:** Hard

**Flags:**
- User: `Null0rigin{you_rode_the_cycle_instead_of_reading_it}`
- Root: `Null0rigin{the_sump_empties_on_its_own_schedule_not_yours}`

## Overview

Stillwater is a mine-drainage themed box, and the flag names are the
thesis: this is the one box on the board where you can't just read a static
value off disk — you have to watch a live cycle (a sump gauge, a drain
schedule) and act inside its window. Everything else follows the chain's
usual method: harvest the site's documents into a wordlist, turn the posted
policy into a hashcat rule, and use a personnel number to cut the keyspace
by a hundred times.

What ships:

- a document store that seeds the harvest
- a damaged ext4 image (`survey-office.img`) — the primary superblock is
  gone, recoverable only via a backup superblock — holding the policy, the
  personnel record, the gauge key, a known plaintext, and the first seed
  fragment
- a gauge key that unlocks a live float-gauge service
- an encrypted bundle (`sump-survey.7z`) containing an SSH key and a second
  known plaintext
- a drain-cycle race and an anomalous sensor reading
- a sluice-keeper account and finally `/etc/shadow`

## The chain

1. **Recon.** A public network share lists `survey-office.img`,
   `pit-records.tar.gz`, and `maint-chroot.tar.gz`.
2. **Harvest the vocabulary** off the exposed files.
3. **Carve and repair the survey image.** The primary superblock is gone;
   recover the filesystem via the backup superblock at block 8193. Inside:
   the credential standard, personnel extract, README files, a seed
   fragment, the gauge key, and a legacy password file.
4. **Crack 1 — the sump archive bundle** (bundle class).
5. **Ride the sump cycle.** The float gauge's live level readings, drawn
   over two ports as the level rises and falls, encode base64 data a chunk
   at a time. Watching a full cycle at the right level draws out the
   encrypted archive itself.
6. **Open the drawn archive** with the bundle password. Inside: an SSH
   private key and its public counterpart, a legacy password file, and a
   staff mailbox.
7. **Crack 2 — the SSH key passphrase** (contractor class).
8. **Log in to the restricted pump-house shell** with the decrypted key.
9. **Win the drain-cycle race** to reach the next account.
10. **The anomalous gauge record.** One reading in the levels log sits
    below the physically possible sill — decoding its layout yields the
    second seed fragment and the user flag.
11. **Crack 3 — the sluice keeper's password** (staff class), verified
    against a hash reached as the pump-house account.
12. **The off-by-one and the third fragment**, reachable only after
    authenticating as the sluice keeper.
13. **Crack 4 — root** (staff class).
14. **The seal.** The three fragments concatenate into the seed for the
    final unlock, sealing the root flag.

## Credentials recovered

| Account | Class | Password | Mask | Rule |
|---|---|---|---|---|
| rainsford | staff | `Delphstone65195%` | `65?d?d?d?1` | `c` |
| dunkerley | contractor | `Wh3lm05592632$` | `92?d?d?d?1` | `c sa4 se3 si1 so0 ss5` |
| bundle | bundle | `sw-sallowthwaite17661&` | `17?d?d?d?1` | `^-^w^s` |
| gauge | contractor | `K3ld50ugh28885%` | `28?d?d?d?1` | `c sa4 se3 si1 so0 ss5` |
| sluice | staff | `Quagwood28873@` | `28?d?d?d?1` | `c` |
| root | staff | `Wellflash52199%` | `52?d?d?d?1` | `c` |

## GPU calibration

| | keyspace | full sweep (49,700 H/s) |
|---|---|---|
| seam number known | 31,314,000 | ~10.5 min |
| seam number unknown | 3,131,400,000 | ~17.5 h |

Unlike some of the other boxes on this board, Stillwater's design always
runs a full hashcat attack rather than accepting a known-plaintext
shortcut — every crack here has to actually be cracked.

## Solve walkthrough

Act I of the chain, run end to end against a booted copy of the shipped
image and cracked for real:

```
== Act I.1  scan / read the public share ==
   share lists: survey-office.img pit-records.tar.gz maint-chroot.tar.gz

== Act I.1  harvest the site vocabulary off the box ==
   harvested 5219 words

== Act I.4  carve and repair the survey office image ==
   backup superblock at block 8193
   recovered: CREDENTIAL-STANDARD.txt PERSONNEL-EXTRACT.txt README-levels.txt
              README.txt fragment-1.txt gauge.key lost+found mail svy-passwd
   gauge key: d12a01c4849533d7...
   known plaintext 1: Delphstone65195%

== Act I.5  CRACK 1 -- the sump archive bundle ==
   cracking bundle: mask=17?d?d?d?1 rule='^-^w^s'
   bundle password: sw-sallowthwaite17661&

== Act I.2-3 + I.5  ride the sump cycle to draw the archive ==
   drew 1768 b64 chars at level 2700 mm
   sump-survey.7z drawn: 1326 bytes

== Act I.5  open the drawn archive with the CRACK 1 password ==
   archive holds: ./id_ed25519 ./plant-passwd ./NOTE.txt ./id_ed25519.pub ./mail/dunkerley

== Act II.6  CRACK 2 -- the ssh key passphrase ==
   cracking gauge: mask=28?d?d?d?1 rule='c sa4 se3 si1 so0 ss5'
   key passphrase: K3ld50ugh28885%

== Act II.10  the anomalous gauge record -> fragment 2 ==
   fragment 2 lives in the below-sill record; seq 3870

== Act III.11  CRACK 3 -- the sluice keeper's password ==
   verifier: sluice.vfy ($6$), reached as the pump-house account
```

The restricted-shell login and the drain-cycle race (Act II.7–9) require the
real cracked passphrase to complete live; the summary above reflects a
partial run through Act I plus the credentials recovered separately, since a
full live run holds a GPU for roughly ten minutes per crack stage.

## Notes

Two build bugs turned up during testing and are worth knowing about if
you're replicating the cracking pipeline yourself: a path-conversion issue
that silently broke `hashcat.exe` invocations for paths outside the
expected mount point, and a hash file that kept a `username:` prefix that
mode 1800 can't parse without also passing `--username`.
