# TLS and certificates

## Protocol versions and configuration
Prefer TLS 1.3 (RFC 8446). Keep TLS 1.2 only for compatibility, restricted to strong AEAD cipher suites with forward secrecy, and disable SSL and TLS 1.0 or 1.1. TLS 1.3 removed legacy features such as RSA key transport, static Diffie-Hellman and compression, and always provides forward secrecy. Start from maintained configuration baselines, for example Mozilla's server-side TLS recommendations or NIST SP 800-52 Rev. 2, and test the deployed configuration with scanners.

## Certificates and PKI
Obtain public certificates from a trusted certificate authority and automate issuance and renewal with ACME (RFC 8555), because expired certificates are a common cause of outages. Monitor expiry, prefer short validity periods, protect private keys in a KMS or HSM or with tightly restricted permissions, and use separate keys per service. Certificate Transparency monitoring helps detect mis-issued certificates. For internal services use a private CA with a documented lifecycle, or a service mesh that provides mutual TLS.

## HSTS and related controls
HTTP Strict Transport Security forces browsers to use HTTPS. Roll it out with a short max-age first. HSTS preloading is hard to reverse, so adopt it deliberately. Redirect HTTP to HTTPS and mark cookies as Secure.

## Operational trade-offs
Pinning certificates or public keys raises protection but risks outages and is discouraged for most web applications. Mutual TLS gives strong client authentication at the cost of certificate distribution. Session resumption and 0-RTT reduce latency, but 0-RTT data can be replayed, so restrict it to idempotent requests.

## Verification
Test configurations and certificate chains regularly. A frequent client bug is disabling certificate or hostname validation to make an error disappear; never ship that.

References: RFC 8446 (TLS 1.3); RFC 5280 (X.509); RFC 8555 (ACME); NIST SP 800-52 Rev. 2.
