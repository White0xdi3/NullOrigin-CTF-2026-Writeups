# 16-nightshift

**Category:** Forensics · **Difficulty:** Medium

**Flag:**
```
Null0rigin{the_boot_that_never_was}
```

## What ships

`triage.journal.export` — 1,500 entries in systemd's journal EXPORT format (the documented text interchange format `journalctl -o export` produces, not a native binary `.journal` file — there is no reliable pure-Python writer for that on-disk hash-table format, so this stage doesn't fake a format it can't independently verify). Two `_BOOT_ID` groups of 750 entries each carry the real fields: `__REALTIME_TIMESTAMP`, `__MONOTONIC_TIMESTAMP`, `__SEQNUM`, `__SEQNUM_ID`.

`capture.wav` — 902 KB, 22050 Hz mono, one continuous responder audio capture spanning both boots' incident window.

This stage is unlocked by 15-handoff and unlocks 17-greylist.

## The mechanism

Between the two boots, the wall clock was stepped backward: boot A runs with a normal clock (2024-06-01), while boot B's clock reads 2024-05-20 — eleven days *earlier* — despite boot B chronologically happening second. `__SEQNUM` is assigned at write time and never resets on this host's journal, so it's immune to the step. `journalctl`'s own default view sorts by `__REALTIME_TIMESTAMP`, so trusting it interleaves the two boots backward.

Two `relay: slice.a=<offset>` / `slice.b=<length>` beacon pairs live in the log, one per boot — each pair is a byte offset and length into `capture.wav`. Sorted by realtime timestamp (boot B first, because its clock lies), the first pair you hit is boot B's. Sorted by `__SEQNUM` (boot A first, correctly), the first pair is boot A's. These are genuinely different beacons: naive realtime order finds the pair at `__SEQNUM=1126`, while true seqnum order finds `__SEQNUM=376`.

**The trap:** boot B's beacon (the naive answer) points at a DTMF tone sequence — hex-encoded ASCII over the standard 16-button grid, including the rare A/B/C/D column. Any real DTMF decoder reads it cleanly: `Null0rigin{the_first_call_back}`. `verify` rejects it. This isn't a parsing failure disguised as success — it *is* a correct decode, of the wrong slice.

**The real content:** boot A's beacon (true order) points at a segment whose waveform is meaningless to a tone decoder — it's a cluster of directly-specified STFT magnitude bins (random phase, overlap-added back to a waveform), which sounds like a buzz and carries no discrete tones to lock onto. Its spectrogram, rendered as an image, is the flag text.

Plain-text volume decoys round it out: a fake `bash_history` COMMAND line, an auditd-shaped `EXECVE` record, and a coredump-recovery note, each carrying its own wrong `Null0rigin{...}`.

## Why the spectrogram is built the way it is

An early draft summed a handful of discrete sine tones per font row to approximate a frequency band. At real FFT bin resolution, the gaps between those discrete tones showed up as visible horizontal comb-striping in the rendered spectrogram — legible with a squint, but sloppy. This was fixed by constructing the STFT magnitude directly (every bin in a font row's range set to full magnitude, random phase per frame) and inverting via overlap-add, producing solid bars with no comb artifact. This is the kind of issue that only shows up when you actually render the output and look — which is the standard this whole board holds itself to.

A second issue: the first draft ran the DTMF and ambient segments at 8000 Hz and resampled the 22050 Hz spectrogram segment down via plain linear interpolation. All tones involved were under the new Nyquist frequency, so it looked like it should have been fine — it wasn't. Linear interpolation isn't a real resampler, and the rendered spectrogram came out badly smeared. It was fixed by using one sample rate (22050 Hz) for the whole file, with no resampling anywhere.

## The break

1. Parse the export format (blank-line-delimited `KEY=VALUE` blocks).
2. Sort by `__REALTIME_TIMESTAMP` (what `journalctl` shows by default) and separately by `__SEQNUM` (write order, immune to the clock step).
3. Find the first `slice.a`/`slice.b` pair under each ordering — they disagree.
4. The realtime-first pair's slice DTMF-decodes cleanly to a wrong flag — a correct decode of the wrong data, not an error to notice and discard.
5. The seqnum-first pair's slice has no discrete tones; render its spectrogram and look.

## Solve

`solve/solve.py` performs steps 1–5 mechanically, including actually running the DTMF decoder on the naive slice (to prove it really does decode clean, not just asserting it) and cross-checking the true slice's byte length against an independently resynthesized reference. As in the earlier stages, it stops at the rendered PNG and confirms `verify`/the sealed box with the intended answer — reading the spectrogram itself is not scripted.
