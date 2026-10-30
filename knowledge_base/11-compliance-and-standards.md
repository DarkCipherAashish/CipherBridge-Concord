# Compliance and standards

## Standards landscape
NIST FIPS 140-3 defines security requirements for cryptographic modules, validated through the CMVP. NIST SP 800-57 covers key management and SP 800-131A covers transitions of algorithms and key lengths. Sector rules also matter: PCI DSS requires strong cryptography and key management for cardholder data, the HIPAA Security Rule treats encryption as an addressable safeguard, GDPR Article 32 names encryption and pseudonymisation among appropriate technical measures, and ISO/IEC 27001 includes controls on cryptography.

## Practical implications
Choose FIPS-validated modules when contracts or regulators require them. Document algorithm choices, the key lifecycle and any exceptions. Auditors typically ask for evidence: configuration baselines, a key inventory, rotation logs, access reviews and test reports. Compliance is not the same as security, because meeting a standard does not prove resilience against your actual threat model.

## Risk acceptance
Record residual risks with an owner and a review date. Re-test important decisions against an audit scenario and map each control to the requirement it satisfies.

## Data residency and export
Cryptography import and export rules and data residency requirements can affect which cloud regions and key management services you may use. Check these with legal advice for your jurisdiction.

References: FIPS 140-3; NIST SP 800-131A Rev. 2; PCI DSS; GDPR Article 32; ISO/IEC 27001.
