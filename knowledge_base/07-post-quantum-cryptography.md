# Post-quantum cryptography

## Why it matters
A sufficiently large, fault-tolerant quantum computer running Shor's algorithm would break RSA, finite-field Diffie-Hellman and elliptic-curve cryptography. Grover's algorithm gives only a quadratic speed-up against symmetric keys and hashes, so the usual mitigation is larger symmetric keys such as AES-256. Because adversaries can record encrypted traffic today and decrypt it later ("harvest now, decrypt later"), data with a long confidentiality lifetime is at risk first.

## Standards
In August 2024 NIST published FIPS 203 (ML-KEM, derived from CRYSTALS-Kyber, for key encapsulation), FIPS 204 (ML-DSA, derived from CRYSTALS-Dilithium, for signatures) and FIPS 205 (SLH-DSA, derived from SPHINCS+, a hash-based signature). Further algorithms are still being standardized, so check NIST's current status pages.

## Migration approach
Inventory where cryptography is used, classify data by how long it must stay confidential, and prioritize key establishment before signatures because of harvest-now-decrypt-later. Build crypto-agility so algorithms can be swapped without redesign. During the transition many deployments use hybrid key exchange, combining a classical algorithm with ML-KEM. Measure the cost: post-quantum keys, ciphertexts and signatures are much larger than those of X25519 or ECDSA, which affects handshake size, latency and protocol limits.

## Timelines and guidance
NIST's transition guidance (IR 8547, initial public draft) proposes deprecating quantum-vulnerable public-key algorithms around 2030 and disallowing them by 2035; check the current version. Guidance differs between national agencies, for example on hybrid versus post-quantum-only deployments, so follow the authority that applies to you.

## Cautions
Do not implement post-quantum algorithms yourself, do not deploy schemes that are not standardized, and rely on maintained libraries. Library maturity and performance on constrained devices should be tested before rollout.

References: FIPS 203; FIPS 204; FIPS 205; NIST IR 8547 (draft); NIST SP 800-208 (stateful hash-based signatures).
