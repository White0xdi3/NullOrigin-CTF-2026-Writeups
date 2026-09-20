# 18-carrier

**Category:** Forensics · **Difficulty:** Hard

**Flag:**
```
Null0rigin{the_extents_outlived_the_name}
```

## What ships

`carrier.img` — 96 MB, a raw ext4 volume with no MBR, holding one flat root directory with 2,203 filler files and 77 marker files (all subsequently deleted). It was built entirely through `debugfs -w`, with no loop mount and no root required.

`incident-notes.txt` — states the true incident window at 1-second resolution (see below for why that resolution matters).

This stage is unlocked by 17-greylist and unlocks 19-revenant.

## The mechanism

Two groups of single-byte files exist on the volume: `Null0rigin{recovered_but_irrelevant}` (36 files, decoy) and `Null0rigin{the_extents_outlived_the_name}` (41 files, real), each internally in true creation order, both created back to back and then deleted. ext4 does not clear a deleted inode's extent pointers or data until that inode number is reused — confirmed directly with `debugfs stat` before and after `rm`, before any of this was built — so `fls`/`icat` recover every single byte of both groups perfectly. The two groups are inode-adjacent (no numbering gap, since nothing else was created in between), so sorting by inode alone does not separate them. What does separate them is a deliberate 2-second wall-clock gap between the two groups' creation, recoverable via `crtime`. Only the later group's creation window overlaps the window `incident-notes.txt` claims — the earlier group is exactly as recoverable, and exactly wrong.

## What didn't survive contact with the actual tools

The original plan for this stage was an ext4 htree-hash-order tool-lie, where `fls` would supposedly list thousands of files in hash order while true creation order lived somewhere else. Tested directly before writing any of this: `debugfs`'s own directory-entry writer never triggers htree conversion, even past 6,000 entries in one directory. `fls` and `debugfs ls` both return exact insertion order regardless of directory size. There is no hash-order tool-lie available through this tool, so this stage doesn't ship one — the mechanism above (deleted-but-intact extents, disambiguated by crtime) is what actually held up under testing.

## A build bug worth documenting

Directory-entry byte size in ext4 depends only on name length, which is constant here (`xxxxxxxx.dat`, always 12 characters) — so which entry lands first in a given 4K directory block is a structural fact of entry *count*, unrelated to the random seed. The first version of this generator hit exactly one marker landing on such a boundary on every single build: 20 straight failures retrying with a new RNG seed and the same counts, always a different marker name, always exactly one, because a fixed entry count always crosses the same block boundaries. Deleting one debugfs invocation at a time instead of one batched script made no difference either (same failures, same seeds). The fix was varying the *filler count* per attempt with a wide stride (so entry count changes shift the block boundaries), combined with a build-time check (`fls_ok_names`) that verifies every marker kept a nonzero inode before accepting the build. The second attempt succeeded. That check now runs on every build, so a broken build fails loudly instead of shipping a flag with a missing character.

A second, smaller issue in the same family: `istat` on this board's Sleuth Kit build reports `crtime` at whole-second resolution only (no sub-second fields read), while the incident notes were originally written from Python's sub-second `datetime.now()`. Comparing a whole-second value against a window with sub-second edges spuriously failed the "is this in the window" check about half the time, depending on exactly when the last marker got written. The fix was writing `incident-notes.txt`'s window at the same whole-second resolution the tools can actually see.

## The break

1. `fls` everything, `icat` every deleted entry, and keep the ones exactly 1 byte long — 77 of them.
2. `istat` each for `crtime`; sort; the largest single gap in the sorted timestamps splits the 77 into two groups of 36 and 41.
3. Compare each group's time span against `incident-notes.txt`'s window — exactly one overlaps.
4. Sort that group by inode (which equals true creation order here, since nothing was created between the two groups to cause reuse), then concatenate the bytes.

## Solve

`solve/solve.py` performs all four steps mechanically and prints the other group's (wrong) recovered text alongside the real one, so the trap is visible in the output rather than just asserted. Unlike the perceptually-gated stages, this one has no non-scripted step: the difficulty is entirely in the forensic reasoning, not in reading an image, so the solve script produces the flag itself rather than stopping at a rendered file.
