# Hashing and message integrity

## Cryptographic hash functions
SHA-256, SHA-384 and SHA-512 (the SHA-2 family, FIPS 180-4) and SHA-3 (FIPS 202) are suitable general-purpose hash functions. BLAKE2 and BLAKE3 are fast alternatives that are not NIST-approved. MD5 and SHA-1 are broken for collision resistance and must not be used for signatures, certificates, or integrity checks against an adversary.

## Integrity versus authenticity
A plain hash detects accidental corruption, but anyone can recompute it after tampering. To authenticate data use a MAC with a secret key, such as HMAC-SHA-256 (RFC 2104), or a digital signature. Compare MACs and tags in constant time. Naive secret-prefix constructions on SHA-2 are open to length-extension attacks, so use HMAC.

## Key derivation
Derive keys from high-entropy secrets with HKDF (RFC 5869). Derive keys from passwords only with password-hashing functions such as Argon2id, scrypt or PBKDF2, never with a plain hash.

## File and artifact integrity
Publish checksums through a trusted channel or sign them, and verify checksums and signatures of downloaded packages in your build pipeline. For large-scale integrity, Merkle trees and transparency logs let many parties verify a shared history.

## Common mistakes
Hashing passwords with SHA-256, treating a hash as encryption, truncating authentication tags too short, and comparing digests with a normal equality operator that leaks timing information.

References: FIPS 180-4; FIPS 202; RFC 2104 (HMAC); RFC 5869 (HKDF).
