# Boot2Root

The Boot2Root category is a linked series of full VM boxes: import an OVA,
find it on your network, and go from anonymous access to root. Every box in
the chain shares one method — the target's own documents are the wordlist,
its posted password policy is a hashcat rule, and one number lifted from a
personnel record is worth a hundred times the GPU time. Learn that lesson on
the first box and every later stage rewards it.

| Stage | Name | Difficulty | Hook | Writeup |
|---|---|---|---|---|
| 00 | Smoke | Warm-up | The wordlist was the target all along — a gentle intro to the board's whole method. | [00-smoke.md](00-smoke.md) |
| 28 | Blackdamp | Hard | Eighteen gated steps, four cracks, and a firmware blob that's lying about its checksum. | [28-blackdamp.md](28-blackdamp.md) |
| 29 | Stillwater | Hard | The sump empties on its own schedule, not yours — a box you have to watch, not just read. | [29-stillwater.md](29-stillwater.md) |
| 30 | Deadlight | Hard | A lamp that only tells the truth the moment it goes out — every wrong answer names the gas that killed it. | [30-deadlight.md](30-deadlight.md) |

## A note on solve scripts

Unlike the other categories, this one doesn't ship reference solve scripts. 00-smoke never had one — the writeup itself (crack the hash with the right hashcat mask) is the whole solve. The other three boxes have since been rebuilt on the author's end as work toward a future revision, so their current reference solvers describe a different exploit chain and different flags than the ones documented here — the writeups above reflect the board as it actually ran, and a solver against the current in-progress rebuild would contradict them. If a frozen copy of the original build turns up, standalone solvers can be added the same way the other categories' were.