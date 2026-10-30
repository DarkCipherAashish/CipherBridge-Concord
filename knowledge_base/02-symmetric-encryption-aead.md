# Symmetric encryption and AEAD

## Use authenticated encryption
Encrypt data with an AEAD mode (authenticated encryption with associated data) so confidentiality and integrity are provided together. The common choices are AES-GCM, which is hardware-accelerated on most servers and phones, and ChaCha20-Poly1305, which is fast in software and suits devices without AES instructions. Avoid unauthenticated modes such as plain CBC or CTR without a MAC, and avoid ECB entirely because it leaks patterns in the plaintext.

## Nonce handling
AES-GCM and ChaCha20-Poly1305 need a unique nonce for every message under the same key. Reusing a nonce can destroy confidentiality and, for GCM, break authentication. Use a counter-based scheme or a carefully managed random nonce. With random 96-bit nonces, NIST SP 800-38D limits the number of invocations per key, so rotate keys before that limit. Where nonce management is hard, consider nonce-misuse-resistant constructions such as AES-GCM-SIV or XChaCha20-Poly1305.

## Key sizes and libraries
AES-128 and AES-256 are both considered strong against classical attackers. AES-256 gives a larger safety margin, including against quantum attacks, because Grover's algorithm roughly halves the effective key length. Use well-maintained libraries and their high-level APIs, such as libsodium, Tink, or the Python cryptography package, rather than assembling primitives yourself. Never invent a custom algorithm.

## Associated data and context binding
Bind each ciphertext to its context (user id, record id, format version) as associated data. This prevents an attacker from swapping valid ciphertexts between records.

## Operational notes
Version the ciphertext format by storing an algorithm identifier, a key identifier and the nonce with it. Plan key rotation and re-encryption, and test implementations with known-answer vectors.

References: FIPS 197 (AES); NIST SP 800-38D (GCM); RFC 8439 (ChaCha20-Poly1305); RFC 8452 (AES-GCM-SIV).
