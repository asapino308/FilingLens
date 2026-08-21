# Security policy

FilingLens is an educational local application. It does not accept or require paid cloud-LLM API keys.

## Reporting a vulnerability

Please use GitHub's private vulnerability-reporting or security-advisory feature for this repository. Do not place credentials, private filings, personal information, or exploit details in a public issue.

## Local security expectations

- Keep `.env` private; it is intentionally excluded from Git.
- Bind LM Studio and Ollama to loopback unless you intentionally need LAN access.
- If you enable LM Studio network access, also enable authentication and restrict the network.
- Filing text is untrusted input. FilingLens places it in an evidence block and does not execute it.
- Generated Markdown and HTML should still be reviewed before sharing.

## Supported version

Security fixes target the current `main` branch.
