# Security Policy

## Reporting a vulnerability

Please **do not** open a public issue. Report privately via GitHub Security Advisories
("Report a vulnerability") once the repository is public; until then email the maintainers.
We aim to acknowledge within 3 days and to ship a fix or mitigation within 30 days.

## Scope / threat model (summary)

- **Memory poisoning / prompt injection** – agents can only *propose* memories; proposals are
  scanned for injection markers and secrets and wait in `inbox/` for human review.
- **Data exfiltration through the gateway** – only whitelisted read tools are exposed; inbox and
  rejected items are never returned by `recall`; `secret`-sensitivity notes are never returned.
- **Config tampering** – `memrelay connect` backs up every client config before editing and can
  roll back; it only touches the `mcpServers.memrelay` key.
- **Local capture** – capture sources are read-only and opt-in; raw transcripts are not copied
  into the vault.

Supported versions: only the latest pre-release receives fixes during 0.x.
