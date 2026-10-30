PERSONAS = {
    "Cryptographer / Security Researcher": {
        "icon": "🔬",
        "goal": (
            "Evaluate cryptographic security, mathematical soundness, attack resistance, "
            "standards alignment, and suitability for the threat model."
        ),
        "style": "Analytical, precise, skeptical of unsupported security claims",
        "priorities": ["security properties", "threat model", "known attacks", "standards"],
        "keywords": ["secur", "attack", "threat", "adversar", "standard", "nist", "proof", "confidential", "integrity", "collision", "brute", "entropy", "strength", "cryptanaly", "side-channel", "forward secrecy"],
    },
    "Software Developer": {
        "icon": "💻",
        "goal": (
            "Evaluate implementation complexity, library support, performance, integration, "
            "testing, deployment, and maintainability."
        ),
        "style": "Practical, implementation-focused, clear, and delivery-aware",
        "priorities": ["maintainability", "available libraries", "performance", "testing"],
        "keywords": ["librar", "implement", "performance", "latency", "maintain", "test", "deploy", "integrat", "api", "complexity", "dependenc", "sdk", "benchmark", "ci/cd", "migration", "refactor"],
    },
    "Cloud Security Engineer": {
        "icon": "🌐",
        "goal": (
            "Evaluate cloud key management, identity and access controls, operational security, "
            "logging, recovery, and secure deployment."
        ),
        "style": "Operationally cautious and architecture-focused",
        "priorities": ["key management", "access control", "monitoring", "recovery"],
        "keywords": ["key management", "kms", "hsm", "iam", "access", "rotat", "logging", "audit", "recover", "monitor", "least privilege", "secret", "vault", "backup", "tenant"],
    },
    "Product Manager": {
        "icon": "📋",
        "goal": (
            "Evaluate user impact, delivery risk, cost, usability, compliance needs, and measurable outcomes."
        ),
        "style": "Outcome-focused, concise, and attentive to trade-offs",
        "priorities": ["user impact", "delivery", "cost", "risk"],
        "keywords": ["user", "cost", "deliver", "timeline", "usab", "risk", "roadmap", "budget", "customer", "release", "trade-off", "stakeholder", "outcome", "adoption"],
    },
    "Compliance & Risk Officer": {
        "icon": "📜",
        "goal": (
            "Evaluate regulatory obligations, standards compliance, auditability, risk acceptance, "
            "and the evidence needed to demonstrate assurance."
        ),
        "style": "Measured, evidence-driven, and focused on accountability",
        "priorities": ["standards", "auditability", "risk", "evidence"],
        "keywords": ["regulat", "audit", "evidence", "standard", "fips", "gdpr", "policy", "control", "complian", "assurance", "certif", "accountab", "documentation", "risk"],
    },
}

DEFAULT_PERSONAS = (
    "Cryptographer / Security Researcher",
    "Software Developer",
)


def get_persona(name: str) -> dict:
    """Return a stakeholder profile by its exact name."""
    try:
        return PERSONAS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown stakeholder persona: {name}") from exc
