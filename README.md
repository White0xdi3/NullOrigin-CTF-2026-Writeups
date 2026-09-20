# NullOrigin CTF 2026 — Writeups

Official author writeups for **NullOrigin CTF 2026**, a self-hosted CTF with 34 challenges across five categories. Every challenge below is chained: each stage's flag is required to unlock (or, in Steganography's case, literally decrypt) the next one, and every category ends in a meta challenge keyed off the previous stages rather than their raw flags.

The challenge files themselves (binaries, VM images, disk/memory images, capture files) aren't in this repo — they're published separately as GitHub Releases in **[NullOrigin-CTF-2026](https://github.com/White0xdi3/NullOrigin-CTF-2026)**, which also has download and verification instructions. This repo is writeups only.

## Categories

| Category | Stages | Format | Index |
|---|---|---|---|
| [Boot2Root](boot2root/) | 00, 28–30 | Full VM boxes, network-facing, user + root flags | [boot2root/README.md](boot2root/README.md) |
| [Cryptography](crypto/) | 06–13 | 8-stage chain + meta | [crypto/README.md](crypto/README.md) |
| [Forensics](forensics/) | 14–20 | 7-stage chain + meta | [forensics/README.md](forensics/README.md) |
| [Reverse Engineering](rev/) | 21–27 | 7-stage chain + meta | [rev/README.md](rev/README.md) |
| [Steganography](stego/) | 31–38 | 8-stage hard chain (no verify binary — the flag *is* the key) | [stego/README.md](stego/README.md) |

Each category README explains that category's shared mechanics (key schedules, container formats, credential-cracking conventions, etc.) once, up front, so the individual stage pages can stay focused on what's actually new in that stage.

## What these writeups cover

Every stage page includes:

- The flag (and any decoys, clearly marked as such)
- What ships with the challenge
- The intended mechanism and why naive/obvious approaches fail
- The actual break — the technique that recovers the flag
- Design notes: why a shortcut doesn't exist, what a solve script proves, and any interesting build trivia

Two of the eight cryptography stages are of note:

- **13-lantern** (the crypto meta) is keyed by seven non-flag internal secrets recovered from stages 06–12, combined via secret sharing over `Z/2^64` — holding all seven flags is not enough to open it.
- **08-errata**'s original writeup notes did not survive; its page states only what's independently verifiable (the flag, its position in the chain, and one technical detail cross-referenced from 13-lantern's own secret table).

The Reverse Engineering category is a from-the-ground-up "keygen-me" design: no binary ever computes and compares a flag, so there's no secret to extract from memory or a static binary at any point — see [rev/README.md](rev/README.md) for the full design philosophy, including why the board was rebuilt after earlier iterations turned out to leak flags directly.

## Difficulty spread

Roughly entry → insane per chain, with each category's meta challenge sitting at the top. If you're picking a starting point: 00-smoke (boot2root), 06-bindery (crypto), 14-slackwater (forensics), 21-cinder (rev), and 31-driftwood (stego) are each their chain's entry point and ship in the clear.
