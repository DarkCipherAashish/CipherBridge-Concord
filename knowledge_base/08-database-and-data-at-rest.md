# Database and data-at-rest encryption

## Layers of protection
Full-disk or volume encryption protects against lost or stolen drives. Transparent Data Encryption (TDE) encrypts database files on disk, which protects media and backups, but the database and its administrators still see plaintext. Application-level (field-level) encryption encrypts data before it reaches the database, which protects against database compromise and privileged administrators but limits searching, indexing and SQL operations.

## Choosing between them
TDE is low effort and needs few application changes, but it does not protect against SQL injection, privileged database users or a compromised application. Application-level encryption gives stronger isolation and allows per-tenant or per-field keys, which helps with compliance for highly sensitive data, but it adds complexity in key management, migrations, performance and querying. Many systems combine TDE as a baseline with application-level encryption for the most sensitive fields.

## Searchability trade-offs
Deterministic encryption allows equality lookups but reveals which records share a value. Randomized encryption is safer but cannot be searched. A blind index, which is an HMAC of the normalized value under a separate key, supports exact-match search. Order-preserving and range-searchable schemes leak ordering information and should be avoided for sensitive fields unless the risk is explicitly accepted. Some managed databases offer client-side field-level encryption built on envelope encryption.

## Backups, logs and replicas
Encrypt backups with separate keys, make sure logs, analytics exports and replicas do not expose plaintext, and test restores.

## Key placement
Keep keys out of the database. Use a KMS or HSM and separate the duties of database administrators and key administrators.

References: NIST SP 800-111 (storage encryption); OWASP Cryptographic Storage Cheat Sheet; NIST SP 800-57.
