"""Groq API wrapper with controlled, non-secret error messages."""
import os
from typing import Dict, Iterator, List, Optional

class LLMConfigurationError(RuntimeError):
    """Raised when the LLM client is not configured."""
class LLMRequestError(RuntimeError):
    """Raised when an LLM request fails."""

def _groq_symbols():
    try:
        from groq import Groq, APIConnectionError, APIStatusError, RateLimitError
        return Groq, APIConnectionError, APIStatusError, RateLimitError
    except ImportError as exc:
        raise LLMConfigurationError("Groq SDK is not installed. Install dependencies with: pip install -r requirements.txt") from exc

def _get_client():
    api_key=os.getenv("GROQ_API_KEY","").strip()
    if not api_key or api_key == "replace_with_your_own_api_key":
        raise LLMConfigurationError("Groq API key not found. Check your local .env configuration.")
    Groq, *_ = _groq_symbols()
    return Groq(api_key=api_key)

def _request_options(messages: List[Dict[str,str]], model: Optional[str], temperature: float, max_tokens: int) -> dict:
    model_name=(model or os.getenv("GROQ_MODEL","openai/gpt-oss-20b")).strip()
    options={"model":model_name,"messages":messages,"temperature":temperature,"max_completion_tokens":max_tokens}
    if model_name.startswith("openai/gpt-oss-"):
        options["reasoning_effort"]="low"
        options["include_reasoning"]=False
    return options

def _handle_api_error(exc: Exception) -> LLMRequestError:
    _, APIConnectionError, APIStatusError, RateLimitError = _groq_symbols()
    if isinstance(exc,RateLimitError):
        return LLMRequestError("Groq rate limit or quota reached. Wait and retry.")
    if isinstance(exc,APIConnectionError):
        return LLMRequestError("Could not connect to Groq. Check your internet connection.")
    if isinstance(exc,APIStatusError):
        return LLMRequestError(f"Groq API error (HTTP {exc.status_code}). Check the model name and API account.")
    return LLMRequestError("Groq request failed unexpectedly. Check configuration and try again.")

def chat_completion(messages: List[Dict[str,str]], model: Optional[str]=None, temperature: float=0.6, max_tokens: int=2048) -> str:
    client=_get_client()
    _, APIConnectionError, APIStatusError, RateLimitError = _groq_symbols()
    try:
        response=client.chat.completions.create(**_request_options(messages,model,temperature,max_tokens))
        if not response.choices: raise LLMRequestError("Groq returned no response choices.")
        choice=response.choices[0]; content=choice.message.content
        if not content or not content.strip(): raise LLMRequestError("Groq returned empty text. Please try again.")
        return content.strip()
    except (RateLimitError,APIConnectionError,APIStatusError) as exc:
        raise _handle_api_error(exc) from exc

def stream_chat_completion(messages: List[Dict[str,str]], model: Optional[str]=None, temperature: float=0.6, max_tokens: int=2048) -> Iterator[str]:
    client=_get_client()
    _, APIConnectionError, APIStatusError, RateLimitError = _groq_symbols()
    received=False
    try:
        options=_request_options(messages,model,temperature,max_tokens); options["stream"]=True
        for chunk in client.chat.completions.create(**options):
            if not chunk.choices: continue
            content=chunk.choices[0].delta.content
            if content:
                received=True
                yield content
        if not received: raise LLMRequestError("Groq returned no text. Please try again.")
    except (RateLimitError,APIConnectionError,APIStatusError) as exc:
        raise _handle_api_error(exc) from exc
