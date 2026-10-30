# Password storage

## Use a dedicated password-hashing function
Passwords must never be stored in plaintext or encrypted in a reversible way. Store the output of a slow, salted, cost-adjustable password-hashing function. The recommended families are Argon2id (preferred, memory-hard, specified in RFC 9106), scrypt, bcrypt, and PBKDF2 (the usual choice when FIPS-validated primitives are required). General-purpose fast hashes such as SHA-256, SHA-512 and MD5 are unsuitable on their own because attackers can test enormous numbers of guesses per second against a stolen database.

## Salts, parameters and tuning
Every password gets its own unique random salt, stored alongside the hash. Salts defeat precomputed tables and stop identical passwords from producing identical hashes. Work-factor parameters (memory, iterations and parallelism for Argon2id; cost for bcrypt; iteration count for PBKDF2) should be benchmarked on the production hardware and raised over time. Check the current OWASP Password Storage Cheat Sheet for minimum values instead of copying numbers from older articles. Store the parameters with each hash so they can be upgraded later.

## Pepper
A pepper is an additional secret value mixed into the hash, for example with HMAC, and kept outside the database in a secrets manager or HSM. It is optional defense in depth against theft of the database alone. It does not replace salts or a strong hashing function. Rotating a pepper requires a version identifier and a plan to rehash passwords at login.

## Migration and operations
Upgrade legacy hashes gradually: verify with the old scheme at login, then rehash with the new one. Alternatively wrap the old hash inside the new function so every record migrates offline. Rate-limit and monitor login attempts. Hashing cost is a deliberate CPU and memory budget, so capacity-plan for login spikes to avoid an expensive-hash denial of service.

## Related guidance
NIST SP 800-63B recommends favouring password length over composition rules, screening against lists of breached or commonly used passwords, and not forcing periodic changes without evidence of compromise. Passkeys (WebAuthn) are a phishing-resistant alternative worth offering.

References: RFC 9106 (Argon2); OWASP Password Storage Cheat Sheet; NIST SP 800-63B.
