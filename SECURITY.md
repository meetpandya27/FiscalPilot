# Security Policy

## Supported Versions

We release patches for security vulnerabilities. Which versions are eligible for
receiving such patches depends on the CVSS v3.0 Rating:

| Version | Supported          |
| ------- | ------------------ |
| 0.6.x   | :white_check_mark: |
| 0.5.x   | :white_check_mark: |
| < 0.5   | :x:                |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via email to **security@fiscalpilot.dev** (or if this
email is not yet set up, create a private security advisory on GitHub).

Please include the following information:

- Type of issue (e.g., buffer overflow, SQL injection, cross-site scripting, etc.)
- Full paths of source file(s) related to the manifestation of the issue
- The location of the affected source code (tag/branch/commit or direct URL)
- Any special configuration required to reproduce the issue
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue, including how an attacker might exploit it

This information will help us triage your report more quickly.

## Response Timeline

- **Initial Response**: Within 48 hours
- **Status Update**: Within 7 days
- **Fix Timeline**: Depends on severity
  - Critical: 24-48 hours
  - High: 7 days
  - Medium: 30 days
  - Low: 90 days

## Security Best Practices for Users

### Credential Management

FiscalPilot connects to sensitive financial systems. Follow these best practices:

1. **Never commit credentials** to version control
2. Use environment variables or `.env` files (which are gitignored)
3. Store OAuth tokens securely (FiscalPilot encrypts them by default)
4. Rotate API keys regularly
5. Use sandbox/development environments for testing

### Token Storage

FiscalPilot stores OAuth tokens in `~/.fiscalpilot/tokens/` with:
- File permissions set to 0600 (owner read/write only)
- AES-128 encryption using Fernet
- Machine-specific encryption keys

### Network Security

When deploying FiscalPilot:
- Use HTTPS for all API communications
- Run behind a reverse proxy in production
- Enable firewall rules to restrict access
- Use VPN for sensitive financial data access

### Audit Logging

Enable audit logging for sensitive operations:

```yaml
# fiscalpilot.yaml
audit:
  enabled: true
  log_file: /var/log/fiscalpilot/audit.log
  sensitive_operations:
    - connector.pull
    - execution.approve
    - execution.execute
```

## Known Security Considerations

### Third-Party Integrations

FiscalPilot integrates with external services that have their own security models:

| Service | Auth Method | Token Rotation |
|---------|-------------|----------------|
| QuickBooks | OAuth2 + PKCE | Auto-refresh |
| Xero | OAuth2 + PKCE | Auto-refresh |
| Plaid | API Keys + Link | Manual |
| Square | Access Tokens | Manual |

### Data Privacy

- FiscalPilot processes financial data locally by default
- No data is sent to external AI services unless explicitly configured
- Generated reports may contain sensitive information — handle accordingly

## Security Acknowledgments

We would like to thank the following security researchers:

- *This section will be updated as we receive and resolve security reports*

## Contact

For security-related inquiries: **security@fiscalpilot.dev**

For general questions: GitHub Issues or Discord community
