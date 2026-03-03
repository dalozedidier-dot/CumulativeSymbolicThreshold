# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.3.x   | Yes       |
| 1.0.x   | No        |
| < 1.0   | No        |

## Reporting a Vulnerability

This project is a **scientific framework** without network-facing services, authentication, or
user-generated input in a deployment sense. However, we take supply-chain and dependency security
seriously.

**To report a security vulnerability:**

1. **Do NOT open a public GitHub issue** for security concerns.
2. Send a private report via [GitHub Security Advisories](https://github.com/dalozedidier-dot/CumulativeSymbolicThreshold/security/advisories/new)
   or email the maintainer directly (see `CITATION.cff` for contact information).
3. Describe the vulnerability, the affected version(s), and steps to reproduce.

We aim to acknowledge reports within **5 business days** and to publish a fix or mitigation
within **30 days** of confirmation.

## Scope

Items in scope:

- Dependency vulnerabilities in `requirements.txt` / `pyproject.toml`
- Code execution vulnerabilities in `src/oric/` (e.g., unsafe `eval`, path traversal in file I/O)
- Integrity of SHA-256 audit manifests in `03_Data/`

Out of scope:

- Results produced by the ORI-C statistical framework (scientific disputes, not security issues)
- Synthetic data generation outputs

## Dependency Updates

We use [Dependabot](https://docs.github.com/en/code-security/dependabot) for automated dependency
updates. See `.github/dependabot.yml` for configuration.

## Known Security Considerations

- **No secrets should ever be committed.** The `.gitignore` excludes `.env` files.
  If you discover a committed secret, report it immediately so it can be rotated and purged from history.
- **Serialization**: some scripts write `manifest.json` and JSONL logs. These files should only be
  consumed from trusted run outputs.
