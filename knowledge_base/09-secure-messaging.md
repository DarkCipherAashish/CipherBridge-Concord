# Secure messaging

## Goals
End-to-end encryption (E2EE) means only the communicating endpoints can read messages while servers relay ciphertext. Typical goals are confidentiality, integrity, authentication, forward secrecy (compromise of long-term keys does not expose past messages) and post-compromise security (the conversation recovers after a key compromise).

## Established protocols
The Signal protocol combines an asynchronous key agreement using prekeys (X3DH, or PQXDH with post-quantum protection) with the Double Ratchet for per-message keys. Messaging Layer Security (MLS, RFC 9420) supports scalable group messaging. Reuse a vetted protocol and library, such as libsignal or OpenMLS, instead of designing key agreement yourself.

## Key and identity verification
Users need a way to verify each other's identity, such as safety numbers or QR codes, to detect a malicious server acting as a man in the middle. Key transparency improves auditability. Multi-device support, device revocation and key backup all involve trade-offs, and server-side key backups can weaken the E2EE guarantee.

## Metadata and operational limits
E2EE does not hide metadata such as who communicates, when, and message sizes unless extra measures like sealed sender and minimal logging are designed in. Message search, spam and abuse reporting, and legal or compliance requirements can conflict with E2EE, so document those trade-offs early.

## Transport and storage
Use TLS between client and server in addition to E2EE. Encrypt local message stores with keys protected by the operating system keystore. Encrypt attachments with a random key and send that key inside the end-to-end encrypted message.

## Post-quantum
Some protocols have added post-quantum key agreement, for example Signal's PQXDH. Plan for algorithm agility in any new messaging design.

References: Signal protocol specifications (X3DH, PQXDH, Double Ratchet); RFC 9420 (MLS).
