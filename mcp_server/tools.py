"""Tools, resources and prompts exposed by the MCP server.

This module has no transport code: `server.py` speaks the protocol, and the
Streamlit "MCP Server" page calls the same handlers in-process for demos."""
import json
import re
from typing import Any, Callable, Dict, List, Optional

from config.personas import PERSONAS
from services.consensus import agreement_status, get_consensus_report
from services.evaluation import agreement_evaluation, persona_consistency
from services.rag import get_knowledge_base
from services.topic_validator import validate_topic
from utils.export_utils import transcript_to_markdown, transcript_to_text
from utils.history_store import get_result, list_history, save_result

PERSONA_NAMES = list(PERSONAS)
MIN_TURNS, MAX_TURNS = 4, 16
MAX_EVALUATED_TURNS = 40


class ToolError(Exception):
    """A problem the caller can fix (bad arguments, out-of-scope topic, missing API key)."""


class ResourceNotFound(Exception):
    pass


# --------------------------------------------------------------------------- #
# Argument validation (a small subset of JSON Schema)
# --------------------------------------------------------------------------- #
_TYPES = {"string": str, "integer": int, "boolean": bool, "array": list, "object": dict}


def _validate(arguments: Any, schema: Dict) -> Dict:
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise ToolError("Tool arguments must be a JSON object.")
    cleaned = {}
    properties = schema.get("properties", {})
    for key in schema.get("required", []):
        if key not in arguments:
            raise ToolError(f"Missing required argument: {key}")
    for key, spec in properties.items():
        if key not in arguments:
            if "default" in spec:
                cleaned[key] = spec["default"]
            continue
        value, expected = arguments[key], spec.get("type")
        if expected and (not isinstance(value, _TYPES[expected]) or (expected == "integer" and isinstance(value, bool))):
            raise ToolError(f"Argument '{key}' must be of type {expected}.")
        if "enum" in spec and value not in spec["enum"]:
            raise ToolError(f"Argument '{key}' must be one of: {', '.join(map(str, spec['enum']))}.")
        if expected == "integer":
            if "minimum" in spec and value < spec["minimum"] or "maximum" in spec and value > spec["maximum"]:
                raise ToolError(f"Argument '{key}' must be between {spec.get('minimum')} and {spec.get('maximum')}.")
        if expected == "string" and spec.get("minLength") and len(value.strip()) < spec["minLength"]:
            raise ToolError(f"Argument '{key}' must not be empty.")
        cleaned[key] = value
    return cleaned


# --------------------------------------------------------------------------- #
# Tool handlers
# --------------------------------------------------------------------------- #
def _check_scope(args: Dict) -> Dict:
    check = validate_topic(args["topic"])
    return {"in_scope": check.status == "accepted", "status": check.status,
            "title": check.title, "message": check.message}


def _search_knowledge_base(args: Dict) -> Dict:
    kb = get_knowledge_base()
    hits = kb.search(args["query"], top_k=args["top_k"])
    return {
        "query": args["query"],
        "count": len(hits),
        "results": [{"rank": i, "id": h["chunk_id"], "title": h["title"], "heading": h["heading"],
                     "source": h["source"], "origin": h["origin"], "score": h["score"], "text": h["text"]}
                    for i, h in enumerate(hits, 1)],
        "knowledge_base": kb.stats(),
        "note": None if hits else "No relevant passages found. Try different or more specific cryptography terms.",
    }


def _list_personas(_args: Dict) -> Dict:
    return {"personas": [{"name": n, "goal": p["goal"], "style": p["style"], "priorities": p["priorities"]}
                         for n, p in PERSONAS.items()]}


def _normalize_turns(raw: List) -> List[Dict]:
    if len(raw) < 4:
        raise ToolError("At least 4 turns are needed; the last two are treated as the closing turns.")
    if len(raw) > MAX_EVALUATED_TURNS:
        raise ToolError(f"At most {MAX_EVALUATED_TURNS} turns can be evaluated at once.")
    turns = []
    for i, item in enumerate(raw, 1):
        if not (isinstance(item, dict) and isinstance(item.get("speaker"), str) and item["speaker"].strip()
                and isinstance(item.get("content"), str) and item["content"].strip()):
            raise ToolError(f"Turn {i} needs non-empty 'speaker' and 'content' strings.")
        turns.append({"turn": i, "speaker": item["speaker"], "content": item["content"],
                      "type": "consensus" if i > len(raw) - 2 else "discussion"})
    return turns


def _evaluate_transcript(args: Dict) -> Dict:
    if args["persona_a"] == args["persona_b"]:
        raise ToolError("persona_a and persona_b must be different.")
    turns = _normalize_turns(args["turns"])
    return {
        "agreement_status": agreement_status(turns),
        "structural_validation": get_consensus_report(turns),
        "agreement": agreement_evaluation(turns, args["persona_a"], args["persona_b"]),
        "persona_consistency": persona_consistency(turns, args["persona_a"], args["persona_b"]),
        "note": "Rule-based structural and keyword checks; not proof of agreement or technical correctness.",
    }


def _summarise_result(result: Dict, history_id: Optional[str]) -> Dict:
    sections = result.get("conclusion") or {}
    return {
        "topic": result["topic"],
        "stakeholders": {"A": result["persona_a"], "B": result["persona_b"]},
        "agreement_status": result["agreement_status"],
        "decision": sections.get("decision") or result.get("final_decision", ""),
        "action_plan": sections.get("action_plan", ""),
        "unresolved_risks": sections.get("risks", ""),
        "evaluation": result.get("evaluation", {}),
        "sources": [{k: s.get(k) for k in ("id", "title", "heading", "source", "score")}
                    for s in result.get("sources", [])],
        "turns": [{"turn": t["turn"], "speaker": t["speaker"], "phase": t.get("phase"), "content": t["content"]}
                  for t in result["turns"]],
        "metadata": result.get("metadata", {}),
        "history_id": history_id,
        "note": "AI-generated; review security-critical recommendations before implementation.",
    }


def _run_dialogue(args: Dict) -> Dict:
    from services.dialogue_manager import generate_dialogue  # imported lazily: it needs the LLM client
    from services.llm_client import LLMConfigurationError, LLMRequestError

    check = validate_topic(args["topic"])
    if check.status != "accepted":
        raise ToolError(f"{check.title}: {check.message}")
    if args["persona_a"] == args["persona_b"]:
        raise ToolError("persona_a and persona_b must be different.")
    try:
        result = generate_dialogue(args["topic"], args["persona_a"], args["persona_b"], args["turns"],
                                   args["context"], use_knowledge_base=args["use_knowledge_base"])
    except (LLMConfigurationError, LLMRequestError, ValueError, RuntimeError) as exc:
        raise ToolError(str(exc))
    history_id = None
    if args["save_to_history"] and result["agreement_status"] in ("agreed", "partial"):
        history_id = save_result(result)
    return _summarise_result(result, history_id)


def _list_history(args: Dict) -> Dict:
    items = []
    for rec in list_history(limit=args["limit"]):
        agreement = (rec.get("evaluation") or {}).get("agreement") or {}
        items.append({"id": rec["id"], "saved_at": rec.get("saved_at"), "topic": rec.get("topic"),
                      "stakeholders": [rec.get("persona_a"), rec.get("persona_b")],
                      "agreement_status": rec.get("agreement_status"),
                      "agreement_score": agreement.get("score")})
    return {"count": len(items), "decisions": items}


def _get_decision(args: Dict) -> Dict:
    record = get_result(args["id"])
    if record is None:
        raise ToolError(f"No saved decision with id '{args['id']}'.")
    if args["format"] == "json":
        return record
    text = transcript_to_markdown(record) if args["format"] == "markdown" else transcript_to_text(record)
    return {"id": args["id"], "format": args["format"], "content": text}


_ANY_PERSONA = {"type": "string", "enum": PERSONA_NAMES}

TOOLS: List[Dict] = [
    {
        "name": "check_cryptography_scope",
        "description": "Check whether a topic is within the cryptography scope of CipherBridge Concord. "
                       "Returns accepted, clarify, or rejected with an explanation.",
        "inputSchema": {"type": "object", "properties": {
            "topic": {"type": "string", "description": "The topic or question to check.", "minLength": 1}},
            "required": ["topic"]},
        "annotations": {"title": "Check cryptography scope", "readOnlyHint": True},
        "handler": _check_scope,
    },
    {
        "name": "search_knowledge_base",
        "description": "Search the cryptography knowledge base (RAG retrieval, BM25 keyword ranking) and return "
                       "the best matching passages with their sources.",
        "inputSchema": {"type": "object", "properties": {
            "query": {"type": "string", "description": "What to look up, e.g. 'AES-GCM nonce reuse'.", "minLength": 1},
            "top_k": {"type": "integer", "description": "Maximum passages to return.", "default": 5,
                      "minimum": 1, "maximum": 10}},
            "required": ["query"]},
        "annotations": {"title": "Search knowledge base", "readOnlyHint": True},
        "handler": _search_knowledge_base,
    },
    {
        "name": "list_stakeholder_personas",
        "description": "List the available stakeholder roles with their goals, style, and priorities.",
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": {"title": "List stakeholder personas", "readOnlyHint": True},
        "handler": _list_personas,
    },
    {
        "name": "evaluate_transcript",
        "description": "Evaluate a two-stakeholder discussion transcript: structural validation, a 0-100 agreement "
                       "score from seven visible checks, and a role-consistency measure. The last two turns are "
                       "treated as the closing turns. Needs no API key.",
        "inputSchema": {"type": "object", "properties": {
            "turns": {"type": "array", "description": "Ordered turns, each {speaker, content}. At least 4.",
                      "items": {"type": "object", "properties": {"speaker": {"type": "string"},
                                                                   "content": {"type": "string"}},
                                "required": ["speaker", "content"]}},
            "persona_a": {**_ANY_PERSONA, "description": "Stakeholder A's role."},
            "persona_b": {**_ANY_PERSONA, "description": "Stakeholder B's role."}},
            "required": ["turns", "persona_a", "persona_b"]},
        "annotations": {"title": "Evaluate transcript", "readOnlyHint": True},
        "handler": _evaluate_transcript,
    },
    {
        "name": "run_stakeholder_dialogue",
        "description": "Run a full multi-turn dialogue between two stakeholder personas on a cryptography decision, "
                       "optionally grounded in the knowledge base (RAG), and return the joint conclusion, action "
                       "plan, risks, sources, and quality checks. Calls the configured Groq model, so it needs "
                       "GROQ_API_KEY and can take tens of seconds.",
        "inputSchema": {"type": "object", "properties": {
            "topic": {"type": "string", "description": "The cryptography decision to discuss.", "minLength": 1},
            "persona_a": {**_ANY_PERSONA, "default": "Cryptographer / Security Researcher"},
            "persona_b": {**_ANY_PERSONA, "default": "Software Developer"},
            "turns": {"type": "integer", "default": 8, "minimum": MIN_TURNS, "maximum": MAX_TURNS},
            "context": {"type": "string", "description": "Optional constraints and success criteria.", "default": ""},
            "use_knowledge_base": {"type": "boolean", "default": True},
            "save_to_history": {"type": "boolean", "description": "Save the decision to local history.",
                                "default": False}},
            "required": ["topic"]},
        "annotations": {"title": "Run stakeholder dialogue", "readOnlyHint": False, "openWorldHint": True},
        "handler": _run_dialogue,
    },
    {
        "name": "list_decision_history",
        "description": "List decisions saved in the local Decision History, newest first.",
        "inputSchema": {"type": "object", "properties": {
            "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 100}}},
        "annotations": {"title": "List decision history", "readOnlyHint": True},
        "handler": _list_history,
    },
    {
        "name": "get_decision",
        "description": "Fetch one saved decision by id as JSON, Markdown, or plain text.",
        "inputSchema": {"type": "object", "properties": {
            "id": {"type": "string", "minLength": 1},
            "format": {"type": "string", "enum": ["json", "markdown", "text"], "default": "json"}},
            "required": ["id"]},
        "annotations": {"title": "Get decision", "readOnlyHint": True},
        "handler": _get_decision,
    },
]
_BY_NAME = {t["name"]: t for t in TOOLS}


def list_tools() -> List[Dict]:
    """Public tool descriptions (without the Python handlers)."""
    return [{k: v for k, v in t.items() if k != "handler"} for t in TOOLS]


def find_tool(name: str) -> Optional[Dict]:
    return _BY_NAME.get(name)


def call_tool(name: str, arguments: Any = None) -> Dict:
    tool = find_tool(name)
    if tool is None:
        raise ToolError(f"Unknown tool: {name}")
    return tool["handler"](_validate(arguments, tool["inputSchema"]))


# --------------------------------------------------------------------------- #
# Resources
# --------------------------------------------------------------------------- #
_KNOWLEDGE_URI = re.compile(r"cipherbridge://knowledge/([\w-]+)")


def list_resources() -> List[Dict]:
    resources = [{"uri": "cipherbridge://personas", "name": "Stakeholder personas",
                  "description": "Roles, goals and priorities used by the dialogue engine.",
                  "mimeType": "application/json"}]
    for doc in get_knowledge_base().documents:
        resources.append({"uri": f"cipherbridge://knowledge/{doc['doc_id']}", "name": doc["title"],
                          "description": f"Knowledge-base note ({doc['origin']}) from {doc['source']}.",
                          "mimeType": "text/markdown"})
    return resources


def read_resource(uri: str) -> Dict:
    if uri == "cipherbridge://personas":
        return {"uri": uri, "mimeType": "application/json",
                "text": json.dumps(_list_personas({}), ensure_ascii=False, indent=2)}
    match = _KNOWLEDGE_URI.fullmatch(uri or "")
    if match:
        for doc in get_knowledge_base().documents:
            if doc["doc_id"] == match.group(1):
                return {"uri": uri, "mimeType": "text/markdown", "text": doc["text"]}
    raise ResourceNotFound(uri)


# --------------------------------------------------------------------------- #
# Prompts
# --------------------------------------------------------------------------- #
PROMPTS: List[Dict] = [{
    "name": "cryptography_decision_brief",
    "description": "Guide an assistant to scope-check a topic, gather evidence, run the two-stakeholder "
                   "dialogue, and summarise the joint conclusion.",
    "arguments": [{"name": "topic", "description": "The cryptography decision to analyse.", "required": True}],
}]


def list_prompts() -> List[Dict]:
    return PROMPTS


def get_prompt(name: str, arguments: Optional[Dict]) -> Dict:
    if name != "cryptography_decision_brief":
        raise ToolError(f"Unknown prompt: {name}")
    topic = ((arguments or {}).get("topic") or "").strip()
    if not topic:
        raise ToolError("The 'topic' argument is required.")
    text = (
        f"Help me reach a well-reasoned decision on this cryptography topic: {topic}\n\n"
        "1. Call check_cryptography_scope with the topic. If it is not in scope, explain why and stop.\n"
        "2. Call search_knowledge_base to gather relevant evidence.\n"
        "3. Call run_stakeholder_dialogue so a cryptographer and a developer discuss it and agree on a conclusion.\n"
        "4. Summarise the joint decision, action plan, and unresolved risks, cite the knowledge-base sources "
        "that were used, and remind me that security-critical recommendations need human review."
    )
    return {"description": "Cryptography decision brief",
            "messages": [{"role": "user", "content": {"type": "text", "text": text}}]}
