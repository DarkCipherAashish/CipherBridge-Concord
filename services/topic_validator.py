"""Local, dependency-free scope checks for the cryptography workspace.

The workspace is dedicated to cryptography. A topic is:
  * accepted  - it names a cryptographic concept or decision;
  * clarify   - it is security-related (or a greeting / too short) but does not
                yet name a cryptographic decision;
  * rejected  - it is outside cryptography, or asks for offensive help.

This is a lightweight heuristic, not an AI classifier. Ambiguous wording may
need rephrasing, which the returned message explains.
"""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class TopicCheck:
    status: str  # accepted, rejected, clarify
    message: str
    title: str = ""


SCOPE_SUMMARY = (
    "encryption, key management, password hashing, digital signatures, "
    "TLS and certificates, or post-quantum migration"
)

OUT_OF_SCOPE_MESSAGE = (
    "This workspace is dedicated to **cryptography**, so I can only run stakeholder "
    "discussions on cryptographic decisions. Your request does not appear to involve one.\n\n"
    f"Please enter a topic about areas such as {SCOPE_SUMMARY}."
)

CLARIFY_MESSAGE = (
    "Your topic touches on security, but I could not identify a **cryptographic** decision in it. "
    "This workspace focuses specifically on cryptography.\n\n"
    f"Please name the cryptographic element involved (for example {SCOPE_SUMMARY}) "
    "and what needs to be decided."
)

OFFENSIVE_MESSAGE = (
    "This workspace supports **defensive, authorized** cryptographic decision-making. "
    "It cannot assist with attacking, bypassing, or stealing from other people's systems or data.\n\n"
    "Please rephrase the request around protecting a system, for example hardening "
    "password storage or key management."
)

GREETING_MESSAGE = (
    "Hello! I am ready when you are. Describe a **cryptography decision** you need to make, "
    "and two expert stakeholders will discuss it and agree on one final conclusion."
)

_CRYPTO_PATTERNS = [
    r"cryptograph\w*", r"cryptosystems?", r"crypto[- ]?agility", r"encrypt\w*", r"decrypt\w*",
    r"cipher\w*", r"aes(?:[- ]?\d{3})?(?:[- ]?(?:gcm|cbc|ctr|ccm))?", r"rsa", r"ecc", r"ecdsa",
    r"ecdh", r"eddsa", r"ed25519", r"x25519", r"curve25519", r"chacha20", r"poly1305",
    r"sha[- ]?(?:1|2|3|224|256|384|512)", r"hmac", r"hash(?:es|ed|ing)?", r"argon2\w*",
    r"bcrypt", r"scrypt", r"pbkdf2", r"tls", r"ssl", r"https", r"ssh", r"pki", r"x\.?509",
    r"certificates?", r"digital signatures?", r"code signing", r"software signing",
    r"token signing", r"jwts?", r"key management", r"key rotation", r"key exchange",
    r"key derivation", r"key storage", r"key escrow", r"kms", r"hsm", r"public[- ]key",
    r"private[- ]key", r"secret[- ]key", r"symmetric[- ](?:key|crypto\w*|encryption)",
    r"asymmetric", r"nonces?", r"initiali[sz]ation vectors?", r"post[- ]quantum",
    r"quantum[- ](?:safe|resistant)", r"pqc", r"kyber", r"dilithium", r"zero[- ]knowledge",
    r"homomorphic", r"e2ee", r"secure messaging", r"secure communications?", r"passwords?",
    r"passphrases?", r"random number generat\w*", r"csprng",
]
_CRYPTO_TERMS = re.compile(r"\b(?:" + "|".join(_CRYPTO_PATTERNS) + r")\b", re.I)

# Security-related, but not by itself a cryptographic decision.
_ADJACENT = re.compile(
    r"\b(?:secur\w*|protect\w*|privacy|confidential\w*|authenticat\w*|authori[sz]ation|"
    r"access control|vulnerabilit\w*|malware|ransomware|breach\w*|cyber\w*|threat\w*|"
    r"firewall\w*|data protection|information security|infosec|compliance|gdpr|hipaa)\b",
    re.I,
)

_GREETING = re.compile(
    r"^\s*(?:hi+|hello+|hey+|good (?:morning|afternoon|evening)|namaste|thanks|thank you|ok|okay)\W*$",
    re.I,
)

# Requests to attack or harm others. Defensive discussion of attacks is allowed.
_VICTIM = (
    r"someone|somebody|other people|neighbou?r|stolen|victims?|"
    r"without (?:their )?(?:permission|consent|authori[sz]ation)|"
    r"my (?:ex|boss|wife|husband|girlfriend|boyfriend)"
)
_OFFENSIVE = re.compile(
    r"\b(?:write|build|create|make|develop|code|generate)\b[^.?!]{0,30}\b"
    r"(?:ransomware|malware|keylogger|virus|botnet|backdoor)\b"
    r"|\b(?:crack|brute[- ]?force|bypass|break into|decrypt|hack)\w*\b[^.?!]{0,50}?\b(?:" + _VICTIM + r")"
    r"|\bhack(?:ing)?\s+(?:into|someone|somebody|a\s+(?:bank|account|wifi|wi-fi|server))\b"
    r"|\b(?:steal|exfiltrate)\s+(?:passwords?|keys?|credentials|data|cards?)\b",
    re.I,
)


def validate_topic(topic: str) -> TopicCheck:
    """Classify topic relevance with safe, predictable local heuristics."""
    text = re.sub(r"\s+", " ", (topic or "")).strip()

    if _GREETING.match(text):
        return TopicCheck("clarify", GREETING_MESSAGE, "Welcome")
    if len(text) < 4:
        return TopicCheck(
            "clarify",
            "Please describe the cryptography decision you need to make in a sentence or two.",
            "More detail needed",
        )
    if _OFFENSIVE.search(text):
        return TopicCheck("rejected", OFFENSIVE_MESSAGE, "Defensive guidance only")
    if _CRYPTO_TERMS.search(text):
        return TopicCheck("accepted", "The topic is within the cryptography scope.", "Topic accepted")
    if _ADJACENT.search(text):
        return TopicCheck("clarify", CLARIFY_MESSAGE, "Please name the cryptographic decision")
    return TopicCheck("rejected", OUT_OF_SCOPE_MESSAGE, "Outside the workspace scope")
