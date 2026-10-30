# CipherBridge Concord

**AI-Powered Cryptography Dialogue and Consensus System**

CipherBridge Concord is an academic project that uses Generative AI, Retrieval-Augmented Generation (RAG), and the Model Context Protocol (MCP) to help two stakeholders discuss cryptography and cybersecurity problems and develop a shared security recommendation.

## What Does This Project Do?

The system brings two different perspectives together. For example, a cryptography researcher may focus on security, while a software developer focuses on implementation and performance.

The AI helps them discuss the problem, examine relevant cryptography knowledge, compare trade-offs, and produce a proposed joint decision.

## Key Features

- **AI Conversations:** Generate structured discussions between two stakeholder personas using Groq.
- **RAG Knowledge Base:** Retrieve relevant information from local cryptography reference notes.
- **Consensus Validation:** Check whether the final dialogue contains a shared recommendation.
- **MCP Integration:** Expose project capabilities through an MCP server for compatible clients.
- **Decision History:** Save and review previous discussions.
- **Export Options:** Export supported results in formats such as TXT, JSON, Markdown, and PDF.
- **Automated Tests:** Test important application components and behaviour.

## Technologies Used

- Python
- Streamlit
- Groq API
- Retrieval-Augmented Generation (RAG)
- Model Context Protocol (MCP)
- Pytest/unittest-compatible testing tools, as configured by the project

## Project Structure

- `main.py` — Main application entry point
- `ui/` — User interface
- `services/` — AI, retrieval, dialogue, and evaluation logic
- `knowledge_base/` — Cryptography reference documents
- `mcp_server/` — MCP server implementation
- `tests/` — Automated tests
- `utils/` — Supporting utilities
- `config/` — Application configuration

## Getting Started

1. Download or clone this repository.
2. Create and activate a Python virtual environment.
3. Install dependencies using `pip install -r requirements.txt`.
4. Configure your Groq API key using the supplied `.env.example` as a template.
5. Start the application using `streamlit run main.py`.

See the project files and configuration instructions for additional setup details. MCP server execution and client configuration are documented separately where applicable.

## Running Tests

Run the project's automated tests from the project root:

`python -m unittest discover -s tests -v`

## Project Purpose

This project explores how AI, cryptography knowledge retrieval, and stakeholder collaboration can support security decision-making. Its recommendations should be reviewed by qualified people before use in real systems.

## Security Notice

Never commit API keys, passwords, access tokens, private cryptographic keys, or confidential information. Keep local environment files and sensitive data out of the public repository.

## Author

**Aashish Bishokarma**

B.Tech Computer Science and Engineering — Cyber Security

GitHub: [DarkCipherAashish](https://github.com/DarkCipherAashish)

## Disclaimer

This project is developed for educational and research purposes. It is not a substitute for professional cryptographic review or a formal security audit.
