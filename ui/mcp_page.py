"""MCP Server page: how to connect a client, what the server offers, and a tool tester."""
import json
import sys

import streamlit as st

from mcp_server import tools
from utils.paths import project_root

_SAMPLE_TURNS = [
    {"speaker": "Cryptographer / Security Researcher", "content": "Attackers with a leaked database are the threat; follow NIST standards."},
    {"speaker": "Software Developer", "content": "We need a maintained library with good performance and tests."},
    {"speaker": "Cryptographer / Security Researcher",
     "content": "Closing position\nI agree with the shared direction: adopt Argon2id.\nConditions\nBenchmark parameters."},
    {"speaker": "Software Developer",
     "content": "Shared decision\nI agree with the shared direction: adopt Argon2id with benchmarked parameters.\n\n"
                "Action plan\n1. Software Developer: benchmark and test parameters.\n"
                "2. Cryptographer / Security Researcher: review the configuration.\n\n"
                "Unresolved risks\n- Parameter tuning depends on production hardware."},
]
EXAMPLES = {
    "check_cryptography_scope": {"topic": "Which password hashing algorithm should we use?"},
    "search_knowledge_base": {"query": "AES-GCM nonce reuse", "top_k": 3},
    "list_stakeholder_personas": {},
    "evaluate_transcript": {"turns": _SAMPLE_TURNS, "persona_a": "Cryptographer / Security Researcher",
                            "persona_b": "Software Developer"},
    "run_stakeholder_dialogue": {"topic": "Choosing a password hashing approach for a web application", "turns": 4},
    "list_decision_history": {"limit": 5},
    "get_decision": {"id": "<id from list_decision_history>", "format": "markdown"},
}


def _client_config() -> dict:
    script = str(project_root() / "mcp_server" / "__main__.py")
    return {"mcpServers": {"cipherbridge-concord": {"command": sys.executable, "args": [script]}}}


def render_mcp(api_configured: bool) -> None:
    st.markdown(
        '<div class="eyebrow">CIPHERBRIDGE CONCORD</div><p class="ws-title">MCP Server</p>'
        '<p class="ws-sub">Expose this project’s tools to any Model Context Protocol client, such as Claude Desktop '
        'or the MCP Inspector.</p>',
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("Tools", len(tools.list_tools()))
    c2.metric("Resources", len(tools.list_resources()))
    c3.metric("Prompts", len(tools.list_prompts()))
    st.markdown(
        '<div class="section-card"><div class="step-label">What this is</div>'
        '<p class="helper">MCP is an open protocol that lets AI applications call external tools and read '
        'resources. This server runs as a separate process and talks to the client over standard input/output. '
        'Clients can scope-check topics, search the knowledge base (RAG), evaluate transcripts, and run the '
        'two-stakeholder dialogue. The server is independent of this web app: you do not need Streamlit running.'
        '</p></div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="step-label">Connect a client</div>', unsafe_allow_html=True)
    st.markdown("**1. Run the server directly** (from the project folder). It waits for a client on standard input:")
    st.code("python -m mcp_server", language="bash")
    st.markdown("**2. Try it in the MCP Inspector** (needs Node.js):")
    st.code(f'npx @modelcontextprotocol/inspector "{sys.executable}" "{project_root() / "mcp_server" / "__main__.py"}"',
            language="bash")
    st.markdown("**3. Add it to Claude Desktop** (Settings → Developer → Edit Config), then restart the app:")
    st.code(json.dumps(_client_config(), indent=2), language="json")
    st.caption("The server reads GROQ_API_KEY and GROQ_MODEL from this project's .env file, so no keys go in the "
               "client config. It uses the Python that is running this page; make sure that environment has the "
               "project requirements installed.")

    st.markdown('<div class="step-label">Tools</div>', unsafe_allow_html=True)
    for tool in tools.list_tools():
        with st.expander(f"🛠 {tool['name']}"):
            st.markdown(tool["description"])
            st.code(json.dumps(tool["inputSchema"], indent=2), language="json")

    st.markdown('<div class="step-label">Resources and prompts</div>', unsafe_allow_html=True)
    with st.expander(f"📚 Resources ({len(tools.list_resources())})"):
        for res in tools.list_resources():
            st.markdown(f"- `{res['uri']}` — {res['name']}")
    with st.expander("💬 Prompts"):
        for prompt in tools.list_prompts():
            st.markdown(f"**{prompt['name']}** — {prompt['description']}")

    st.markdown('<div class="step-label">Try a tool</div>', unsafe_allow_html=True)
    st.caption("Runs the same tool handler in this app. External clients reach it through the stdio server above.")
    names = [t["name"] for t in tools.list_tools()]
    name = st.selectbox("Tool", names, key="mcp_tool")
    raw = st.text_area("Arguments (JSON)", value=json.dumps(EXAMPLES.get(name, {}), indent=2), height=180,
                       key=f"mcp_args_{name}")
    if name == "run_stakeholder_dialogue" and not api_configured:
        st.warning("This tool calls the AI model and needs GROQ_API_KEY in .env.")
    if st.button("▶ Run tool", key="mcp_run"):
        try:
            arguments = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError as exc:
            st.error(f"The arguments are not valid JSON: {exc}")
            return
        try:
            with st.spinner("Running…"):
                output = tools.call_tool(name, arguments)
            st.success("Tool returned a result.")
            st.code(json.dumps(output, indent=2, ensure_ascii=False), language="json")
        except tools.ToolError as exc:
            st.error(str(exc))
