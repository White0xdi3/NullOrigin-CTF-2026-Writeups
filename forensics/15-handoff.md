# 15-handoff

**Category:** Forensics · **Difficulty:** Easy

**Flag:**
```
Null0rigin{the_right_feed_never_lied}
```

## What ships

`handoff.pcap` — 81 packets, 84.8 KB, a classic pcap. It contains one HTTP exchange, one DNS query, a six-line FTP session, and 72 UDP packets on port 5004 forming two interleaved RTP streams of 36 packets each. There's no SDP or RTSP signalling anywhere in the capture, so `tshark`'s default dissection shows the RTP packets as plain `UDP`/`data` — getting to RTP fields at all needs `-d udp.port==5004,rtp` or the equivalent in Wireshark's Decode As.

This stage is unlocked by 14-slackwater and unlocks 16-nightshift.

## The mechanism

Each RTP packet's payload is one halftoned scanline (Floyd-Steinberg dithered, the same renderer as 14-slackwater) — 1092 raw pixel bytes, each 0 or 255. Stack a stream's 36 packets in sequence order and you get a 1092×36 image. Two SSRCs share the port: `0x7e11a0c1` (the real device) and `0x7e115ca0` (a second kiosk still replaying its own splash screen during the handoff window). Every packet from the real device sets the RTP marker bit; the impostor never does — that's the disambiguator, not the SSRC value itself, since SSRCs are arbitrary 32-bit numbers with nothing in the byte pattern to favor one over the other.

**The trap:** interleaving the two streams in capture order — what a naive "just grab every RTP payload in order" script does — and averaging pixel by pixel drops the measured pixel standard deviation from a clean signal's 120+ down to 54.4. The two streams' letterforms partially cancel and partially collide, producing a smear with no read either way. You have to split by SSRC before either image resolves.

**The decoy payoff:** the other SSRC, once correctly demuxed on its own, isn't garbage — it decodes just as cleanly as the real one, into a complete, plausible, wrong flag: `Null0rigin{the_ghost_signal_answered}`. `verify` rejects it. Getting this far — finding the two streams and realizing you need to pick one — and then picking the wrong one costs strikes for nothing.

Standard protocol decoys round out the volume: an HTTP response body, a `User-Agent` header, an FTP `flag.txt`, and a DNS query whose labels are base32 for yet another wrong flag — a "tunnel" that only looks like one.

## The break

1. Read every UDP/5004 packet and keep the RTP fields (sequence number, marker bit, SSRC, payload) — a 12-byte header, no libraries needed to parse it.
2. Group by SSRC and sort by sequence number — two groups of 36.
3. The marker bit is set on every packet in exactly one group. That's the real stream, per the in-universe protocol's own framing rule.
4. Stack that group's payloads into a 1092×36 grid, render it, and look.

## Solve

`solve/solve.py` performs steps 1–4 mechanically, additionally computing the naive-mix statistic to demonstrate the trap is real, and cross-checks the extracted grid against an independently rendered halftone of the known flag (0 pixel diffs). As in 14-slackwater, it stops at the rendered PNG and hardcodes the intended answer to confirm `verify` and the sealed box — reading the halftone itself is not scripted.
