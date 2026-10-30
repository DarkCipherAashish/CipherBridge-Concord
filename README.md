# CipherBridge Concord

**Dual-Stakeholder Chatbots for Consensus-Driven Cryptography Dialogues**

CipherBridge Concord is an academic prototype for exploring cryptography decisions through a Groq-powered AI chat assistant and a chat-style, two-stakeholder decision workspace. It is not a production-certified security system.

## Features
- Dashboard with actual API configuration, selected model, chat count, saved dialogue state, and saved-decision count.
- Sidebar navigation: Dashboard, AI Chat, Stakeholder Dialogue, Decision History, Knowledge Base, MCP Server.
- Beginner, Expert, and Code-focused AI answer styles; streamed responses.
- **Chat-style Stakeholder Decision Workspace**
  - Type any decision in a chat box, or start from one of six quick-start decisions.
  - **Cryptography-only scope check.** Off-topic requests receive a professional scope message and no AI call is made. Security topics that do not name a cryptographic decision are asked to clarify; greetings get a welcome; requests to attack or steal from others are declined.
  - **Exact number of turns** (4-16). Two stakeholders alternate, and the discussion is guided through three phases: *opening positions*, *trade-offs*, and *convergence* toward one proposal. A live phase tracker shows progress.
  - Two reserved closing turns: the first stakeholder states a closing position; the second confirms or qualifies it. The result is one **Final Conclusion card** with the joint decision, action plan, unresolved risks, and an agreement badge (Consensus reached / Partial agreement / Incomplete).
  - Honest outcomes: if the stakeholders do not genuinely agree, the card says so and labels the result a proposed next step.
  - **Agreement score (0-100)** from seven visible checks (explicit agreement from both closing turns, shared decision, verification steps, named owners, listed risks, both roles' priorities reflected).
  - **Role-consistency measure** showing how much of each stakeholder's dialogue reflects their role's priorities.
  - **Compare positions** view: where each stakeholder started and where they ended.
  - **Stress tests**: one click re-examines the conclusion under a new scenario (limited budget, external audit, stronger attacker, 100x growth) and produces advisory revised guidance.
  - Five stakeholder roles including Compliance & Risk Officer, optional context and constraints, a human review checklist, and exports as **PDF report, Markdown, TXT, or JSON**.
  - Structured JSON with schema version, metadata (time, model, turn counts), per-turn phase, a `concluding_agreement` block, and the evaluation results.
  - A partial transcript is kept, and clearly marked, if generation fails part-way.
- **Decision History**: completed decisions are saved locally, can be searched, reopened in the workspace, exported, and deleted.
- **Retrieval-augmented generation (RAG)**: a cryptography knowledge base (11 curated starter notes plus your own) is searched for every decision and AI Chat question. The best passages are placed in the prompt with labels [S1], [S2]… and the model is asked to cite them. Results show the sources used, how many turns cite a source, and flag citations that point to nothing retrieved. A Knowledge Base page lets you search the index and add your own notes.
- **MCP server**: `python -m mcp_server` exposes seven tools (scope check, knowledge-base search, persona list, transcript evaluation, full stakeholder dialogue, history list and fetch), twelve resources (personas and each knowledge note), and one prompt to any Model Context Protocol client such as Claude Desktop or the MCP Inspector. An MCP Server page shows the connection steps and lets you try each tool.
- Unit tests mock or avoid external API calls.

## Requirements
Python 3.10+ (Python 3.11 or 3.12 recommended), internet access for AI generation, and a Groq API key/model available to your account. `reportlab` (installed by `requirements.txt`) is used for PDF export; without it, the other exports still work.

## Windows PowerShell setup
Run from the extracted project root:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

In `.env`, replace the placeholder with your own key and set `GROQ_MODEL` to a model available to your account. Do not share or commit `.env`.

Start the app:

```powershell
streamlit run main.py
```

Run tests (no API key or browser required):

```powershell
python -m unittest discover -s tests -v
```

## Configuration
- `GROQ_API_KEY`: required for AI features.
- `GROQ_MODEL`: model identifier; defaults to `openai/gpt-oss-20b`.
- `.streamlit/config.toml`: dark theme and minimal toolbar.

The app loads `.env` locally with `python-dotenv`. The API key is never rendered in the interface. If a key has been exposed, revoke/rotate it at the provider before using a new key.

## Architecture
- `main.py`: Streamlit navigation, dashboard, and AI chat.
- `ui/workspace.py`: chat-style Stakeholder Decision Workspace (rendering, state, generation, stress tests).
- `ui/history.py`: Decision History page.
- `ui/knowledge.py`: Knowledge Base page (search, browse, add notes).
- `ui/mcp_page.py`: MCP Server page (connection steps, tool list, tool tester).
- `ui/styles.py`: shared CSS.
- `config/personas.py`: stakeholder roles, priorities, and role keywords.
- `services/llm_client.py`: Groq request wrapper, streaming, controlled errors.
- `services/dialogue_manager.py`: turn plan and phases, stakeholder prompts, closing turns, stress tests, result assembly.
- `services/topic_validator.py`: local cryptography-scope classification (accepted / clarify / rejected).
- `services/consensus.py`: structural validation, agreement status, conclusion-section parsing.
- `services/evaluation.py`: agreement score and role-consistency measure.
- `services/rag.py`: knowledge-base loading, chunking, BM25 index, retrieval, prompt context, citation checks, user notes.
- `knowledge_base/`: curated starter notes (Markdown). Add your own course notes on the Knowledge Base page.
- `mcp_server/`: the MCP server (`tools.py` defines tools, resources and prompts; `server.py` speaks the protocol over stdio; `__main__.py` is the launcher).
- `utils/export_utils.py`: Markdown, TXT, and JSON serialization.
- `utils/pdf_export.py`: PDF decision report.
- `utils/history_store.py`: local decision history (`data/decision_history.jsonl`, git-ignored).
- `utils/paths.py`: shared locations for local data and the knowledge base.
- `tests/`: local unit tests, including a stubbed-Streamlit smoke test of the workspace flow.

## How to use
1. Open Dashboard to confirm configuration status.
2. Open **Stakeholder Dialogue** and type a cryptography decision, for example "Which encryption approach should our messaging app use?", or pick a quick-start.
3. Optionally open **Workspace settings** to change the stakeholders, set the number of turns, or add constraints.
4. Watch the two stakeholders move from opening positions to a proposal, then read the **Final Conclusion** card, the agreement score, and the position comparison.
5. Use a **stress test** to see whether the decision holds up under a different scenario.
6. Tick the review checklist and export a PDF, Markdown, TXT, or JSON report. Use **New decision** to start over.
7. Open **Decision History** to reopen, export, or delete earlier decisions.
8. Open **Knowledge Base** to see what the stakeholders can cite, try a search, or add your own notes.
9. Open **MCP Server** to connect an external AI client or try the tools.

## RAG and MCP

### How RAG works here
1. **Index.** Every `.md` or `.txt` note is split into passages by heading (long sections are split further) and indexed with BM25, a keyword-ranking function implemented in `services/rag.py` without extra dependencies. Titles and headings are weighted more heavily, and a small synonym table links abbreviations such as KMS, PQC, and TDE to their full terms.
2. **Retrieve.** For each decision the topic and context are used as the query. Passages must share at least two query terms (or the only term) and reach a minimum score, so unrelated questions return nothing instead of weak matches.
3. **Augment.** The passages are added to every stakeholder prompt as numbered, untrusted reference notes ([S1], [S2]…) with instructions to cite them, never invent citations, and say so when the notes do not cover a point. Stress tests reuse the same notes.
4. **Check.** The result records the sources and a grounding report: how many turns cite a retrieved source, which sources were cited, and any citation that was not retrieved.

Retrieval is lexical, so it matches words rather than meaning. It works well for a small, focused knowledge base. An embedding-based retriever could replace `KnowledgeBase.search` without changing the rest of the app. The curated notes are short summaries written for this project that name their primary sources (RFCs, NIST publications, OWASP cheat sheets). Verify details against those sources, and add your own course notes to make the knowledge base match your syllabus.

### The MCP server
Run from the project folder (the same Python environment that has the requirements installed):

```powershell
python -m mcp_server
```

The server waits on standard input for an MCP client. It reads `GROQ_API_KEY` and `GROQ_MODEL` from the project's `.env`, so no keys go into client settings. Connect a client in one of these ways:

- **MCP Inspector** (needs Node.js): `npx @modelcontextprotocol/inspector python -m mcp_server`, run from the project folder.
- **Claude Desktop**: add the JSON shown on the **MCP Server** page to the Claude Desktop config (Settings, Developer, Edit Config) and restart the app. It contains the full path to your Python and to `mcp_server/__main__.py`.

| Tool | Purpose | Needs API key |
|---|---|---|
| `check_cryptography_scope` | Accepted, clarify, or rejected for a topic | No |
| `search_knowledge_base` | RAG retrieval with sources | No |
| `list_stakeholder_personas` | Roles, goals, priorities | No |
| `evaluate_transcript` | Agreement score and role consistency for any transcript | No |
| `run_stakeholder_dialogue` | Full discussion, conclusion, sources, checks | Yes |
| `list_decision_history` / `get_decision` | Read saved decisions as JSON, Markdown, or text | No |

Resources: `cipherbridge://personas` and `cipherbridge://knowledge/<note-id>` for every note. Prompt: `cryptography_decision_brief`. The server implements the MCP stdio protocol directly (JSON-RPC 2.0 messages, one per line) with no extra dependency, and it keeps standard output reserved for protocol messages.

## Security and limitations
- The topic validator is a lightweight local heuristic, not a semantic AI classifier. It can misjudge unusual wording; rephrase the topic with the cryptographic element named.
- Consensus validation checks transcript structure and selected textual markers only. It cannot prove genuine agreement, cryptographic correctness, or safe implementation.
- Model responses can be incorrect, incomplete, or inconsistent. Review security-critical recommendations against current authoritative guidance and the actual threat model.
- The agreement score and role-consistency figures are rule-based (structure and keyword checks). They make results easier to inspect but are not proof of genuine agreement, persona fidelity, or technical correctness.
- Stress-test output is advisory and is not validated as consensus.
- Decision History is stored as plain text in the local `data/` folder. Turn it off in Workspace settings, or delete entries on the Decision History page, if topics may be sensitive.
- RAG retrieval is keyword-based. Generic wording can surface loosely related passages, and a citation shows only that the model referred to a note, not that the claim is correct.
- Passages retrieved from the knowledge base, including your own notes, are sent to the AI provider inside prompts. Do not add confidential material to the knowledge base.
- Retrieved text is presented to the model as untrusted data with instructions not to follow commands inside it. This reduces, but cannot eliminate, the risk of prompt injection from a malicious note.
- The MCP server runs locally over stdio and has no authentication of its own; any program that can launch it can use its tools. `run_stakeholder_dialogue` calls the Groq model with your key, and saving to history is off unless requested.
- The MCP server was tested against this project's own protocol tests and a real subprocess client. Test it with your MCP client of choice before relying on it.
- Do not enter API keys, passwords, private keys, or sensitive production data.
- API availability, model names, quotas, and provider behavior may change.
- No live Groq API call or deployment claim is implied by the unit-test results.

## Troubleshooting
- If AI features report missing credentials, confirm `.env` exists in the project root and `GROQ_API_KEY` is set.
- If the model is unavailable, update `GROQ_MODEL` to a model enabled for your Groq account.
- If a legitimate topic is flagged as out of scope, name the cryptographic element explicitly (for example "password hashing", "TLS certificates", "key rotation").
- If an MCP client cannot start the server, run `python -m mcp_server` yourself from the project folder to see the error on screen (messages appear on the error stream). Use the full path to the Python that has the requirements installed, and restart the client after editing its config.
- If the knowledge base returns nothing for a legitimate topic, use more specific cryptography terms (for example "key rotation" rather than "keeping things safe") or add a note covering that topic.
- If PowerShell blocks virtual-environment activation, use an approved local execution policy or run `.venv\Scripts\python.exe -m pip install -r requirements.txt` and `.venv\Scripts\streamlit.exe run main.py`.

## License
Educational project. Add a license before redistribution if needed.
