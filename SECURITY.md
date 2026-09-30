# Security Policy

## Supported versions

Only the latest released version of VideoTranscriber is supported with security fixes.

## Reporting a vulnerability

Please report security issues using **[GitHub's private vulnerability reporting](https://github.com/awesomo913/VideoTranscriber/security/advisories/new)** (Security tab → "Report a vulnerability") rather than a public issue. This lets the report be triaged before details are public.

If private reporting isn't available for you, open a regular GitHub issue with as much detail as you're comfortable sharing publicly, and note that it's a security concern in the title.

Please include:

- A description of the issue and its potential impact
- Steps to reproduce, if possible
- The VideoTranscriber version and OS you're running

## Scope notes

- VideoTranscriber runs entirely locally — it does not transmit audio, video, or transcripts anywhere. There is no network activity besides the one-time Whisper model download from Hugging Face on first use.
- No account, API key, or telemetry is involved.
- The release `.exe` is unsigned. Reports about SmartScreen or antivirus false positives are welcome context but are not themselves security vulnerabilities — see the README FAQ for the current recommended workaround (verify checksums, or build from source).
