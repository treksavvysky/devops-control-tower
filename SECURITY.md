# Security Policy

## Supported Versions

We release patches for security vulnerabilities in the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

The DevOps Control Tower team takes security bugs seriously. We appreciate your efforts to responsibly disclose your findings, and will make every effort to acknowledge your contributions.

To report a security issue, please use the GitHub Security Advisory ["Report a Vulnerability"](https://github.com/georgeloudon/devops-control-tower/security/advisories/new) tab.

The team will send a response indicating the next steps in handling your report. After the initial reply to your report, the security team will keep you informed of the progress towards a fix and full announcement, and may ask for additional information or guidance.

## Security Considerations

### AI and LLM Integration

- **API Keys**: Never commit LLM API keys to the repository. Use environment variables or secure secret management.
- **Prompt Injection**: Be aware that AI agents may be vulnerable to prompt injection attacks through event data.
- **Data Privacy**: Ensure sensitive infrastructure data is not sent to external LLM providers.

### Infrastructure Access

- **Credentials**: Store all cloud provider credentials securely using proper secret management.
- **Least Privilege**: Configure agents with minimal required permissions.
- **Network Security**: Ensure proper network isolation for the Control Tower components.

### Event Processing

- **Input Validation**: All event data should be validated before processing.
- **Rate Limiting**: Implement rate limiting to prevent event flooding attacks.
- **Authentication**: Secure all event sources with proper authentication.

### Workflow Execution

- **Code Injection**: Validate all workflow steps to prevent code injection.
- **Resource Limits**: Implement timeouts and resource limits for workflow execution.
- **Audit Logging**: Maintain comprehensive logs of all workflow executions.

## Security Features

- Event validation and sanitization
- Configurable allowed directories for file operations
- Blocked command lists for terminal operations
- Comprehensive audit logging
- JWT-based authentication (planned)
- Role-based access control (planned)

## Best Practices for Users

1. **Environment Isolation**: Run in isolated environments with minimal network access
2. **Regular Updates**: Keep dependencies and the platform updated
3. **Monitoring**: Monitor all agent activities and workflow executions
4. **Backup**: Maintain secure backups of configuration and data
5. **Access Control**: Implement proper access controls for the dashboard and API

## Disclosure Policy

When we receive a security bug report, we will:

1. Confirm the problem and determine the affected versions.
2. Audit code to find any potential similar problems.
3. Prepare fixes for all releases still under support.
4. Release new versions as soon as possible.

## Comments on this Policy

If you have suggestions on how this process could be improved please submit a pull request.
