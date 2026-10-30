# Randomness, crypto-agility and common mistakes

## Randomness
Use the operating system's cryptographically secure random generator, for example getrandom or /dev/urandom, the secrets module in Python, or crypto.randomBytes in Node.js. Never use general-purpose generators such as Python's random module or Math.random for keys, tokens or nonces, and never seed from the clock. Do not derive keys from predictable values.

## Common mistakes
Inventing custom algorithms, using ECB mode, reusing nonces or IVs, hard-coding keys and secrets in repositories, disabling certificate validation, using unauthenticated encryption, comparing MACs with a normal equality operator, using fast hashes for passwords, ignoring key rotation and recovery, logging secrets, writing your own JWT validation, leaving insecure defaults, and low entropy early in the boot of virtual machines and containers.

## Crypto-agility
Design systems so algorithms and parameters can change. Version ciphertexts and hashes with algorithm identifiers, hide cryptography behind a small internal interface, keep an inventory of where cryptography is used, automate tests, and avoid hard-coded sizes. The trade-off is added complexity and downgrade risk, so enforce server-side allowlists of acceptable algorithms.

## Review practices
Prefer high-level libraries, threat-model before choosing primitives, get a cryptography-aware review of designs, use static analysis that flags crypto API misuse, fuzz parsers, and keep dependencies updated.

References: OWASP Cryptographic Storage Cheat Sheet; NIST SP 800-90A, 800-90B and 800-90C (random bit generation).
