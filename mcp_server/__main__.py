"""Run with:  python -m mcp_server   (from the project folder)
or:          python /full/path/to/mcp_server/__main__.py"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:  # make GROQ_API_KEY / GROQ_MODEL from the project's .env available to the server
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from mcp_server.server import main  # noqa: E402

if __name__ == "__main__":
    main()
