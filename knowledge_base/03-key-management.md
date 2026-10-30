# Key management

## Principles
The security of encrypted data depends on how the keys are protected. Generate keys with a cryptographically secure random generator, separate keys by purpose and data domain, never hard-code keys or commit them to source control, restrict access with least privilege, and log every use.

## Envelope encryption
Data is encrypted with data encryption keys (DEKs), and the DEKs are wrapped by a key encryption key (KEK) held in a key management service (KMS) or hardware security module (HSM). This lets you rotate the KEK without re-encrypting all data, limits exposure of any single key, and centralizes auditing. Cloud KMS products such as AWS KMS, Google Cloud KMS and Azure Key Vault implement this pattern. HSMs provide tamper-resistant key storage, and FIPS 140-3 validated modules may be required by regulation or contract.

## Rotation and lifecycle
Define a cryptoperiod for each key type; NIST SP 800-57 Part 1 gives guidance. Rotate on a schedule and immediately after suspected compromise. Keep old key versions available to decrypt old data until it has been re-encrypted, and plan revocation, destruction, backup and recovery for every key.

## Recovery and availability
Losing a key means losing the data. Back keys up securely, for example with split knowledge or multi-person control, test restore procedures regularly, avoid single points of failure, and document break-glass access with audit.

## Access control and monitoring
Use IAM roles and service identities instead of long-lived static credentials. Separate the duties of key administrators and key users, alert on unusual key usage, and consider per-tenant keys for isolation between customers.

## Trade-offs
A managed KMS reduces operational burden but adds a dependency on its availability, latency, per-call cost and vendor. Self-managed HSMs give more control but require specialist expertise and operational discipline.

References: NIST SP 800-57 Part 1; NIST SP 800-130; OWASP Key Management Cheat Sheet.
