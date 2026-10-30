# Digital signatures

## Purpose
A digital signature gives authenticity and integrity, and supports non-repudiation: anyone with the public key can verify who signed the data and that it was not changed. Typical uses are software and firmware signing, token signing such as JWT, document signing, and certificates.

## Algorithm choices
Ed25519 (EdDSA, RFC 8032, included in FIPS 186-5) is fast, deterministic, has small keys and signatures, and is simple to implement safely. ECDSA over curves such as P-256 is widely supported and FIPS-approved, but it needs high-quality per-signature randomness or deterministic nonces (RFC 6979), because biased or repeated nonces leak the private key. RSA signatures should use RSASSA-PSS rather than PKCS#1 v1.5 where possible, with keys of at least 2048 bits and larger for long-term use; RSA signatures are bigger and slower to create. Hash with the SHA-2 or SHA-3 family, never MD5 or SHA-1.

## Key protection and lifecycle
Keep signing keys in an HSM or KMS, restrict who can request signatures, and use separate keys for release signing and for testing. Plan rotation and revocation, and use trusted timestamps when signatures must remain valid after the key or certificate expires.

## JWT and token pitfalls
Pin the accepted algorithms on the verifier and never accept the "none" algorithm. Avoid algorithm confusion, where a public key is mistakenly used as an HMAC secret. Always validate issuer, audience and expiry. Prefer asymmetric signatures when many services need to verify tokens but only one should issue them.

## Post-quantum note
RSA, ECDSA and EdDSA are vulnerable to a sufficiently large quantum computer. NIST has standardized ML-DSA (FIPS 204) and SLH-DSA (FIPS 205). Long-lived signatures, such as firmware and root keys, need migration planning, and hybrid or composite approaches are used during the transition.

References: FIPS 186-5; RFC 8032; RFC 6979; FIPS 204; FIPS 205.
