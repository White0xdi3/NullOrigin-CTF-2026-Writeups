# Forensics

A seven-stage chain, each stage unlocking the next, ending in a meta challenge sealed by a hash-based share of every prior flag. Every stage ships genuine, tool-recoverable decoy data alongside the real artifact — deleted files, wrong-but-plausible tone decodes, framebuffers that XOR into noise — so the standard "run the obvious tool and take its first answer" approach reliably produces a confident, wrong flag. The actual technique in each stage is what standard forensic tooling doesn't surface by default: allocated-but-unreferenced FAT clusters, RTP streams split by marker bit instead of SSRC, write-order versus wall-clock order in a journal, an unmapped page table entry, deleted-but-intact ext4 extents disambiguated by creation time, a two-time-pad key reuse across VM clones, and a forged pcap timestamp caught against an independent clock source.

The finale, 20-nullwatch, cannot be opened with any of the six prior stages' recoverable byte offsets, SSRCs, or physical addresses — its seal is built from `SHA-256(flag)[:8]` of each of the six real flags, so it can only be assembled by a player who actually solved every stage.

| Stage | Name | Difficulty | Hook | Writeup |
|---|---|---|---|---|
| 14 | slackwater | Easy | A FAT32 card's real flag isn't in any file — it's a halftoned image encoded one bit per unreferenced-but-allocated cluster. | [14-slackwater.md](14-slackwater.md) |
| 15 | handoff | Easy | Two RTP streams share one port; naively averaging their payloads smears both images into noise, and the wrong stream decodes to a clean, wrong flag. | [15-handoff.md](15-handoff.md) |
| 16 | nightshift | Medium | A stepped-back wall clock makes `journalctl`'s default sort pick the wrong boot's beacon — which decodes perfectly, to the wrong answer. | [16-nightshift.md](16-nightshift.md) |
| 17 | greylist | Medium | A synthetic physical memory image hides a third page mapping the process never self-reports, holding a 2-share XOR visual-crypto reveal. | [17-greylist.md](17-greylist.md) |
| 18 | carrier | Hard | Two inode-adjacent groups of deleted single-byte files recover perfectly with `fls`/`icat`; only `crtime` separates the real group from the decoy. | [18-carrier.md](18-carrier.md) |
| 19 | revenant | Hard | Two VM clones from one golden image never reseeded their CSPRNG, producing a classic two-time-pad break via a known-plaintext template. | [19-revenant.md](19-revenant.md) |
| 20 | nullwatch | Insane (meta) | A pcap's own frame timestamps lie by 2x; the TCP Timestamp option (and the badge log) tell the truth. Sealed by a hash of all six prior flags. | [20-nullwatch.md](20-nullwatch.md) |
