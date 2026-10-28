"""
Langfuse Observability — tracing & cost tracking for the ReAct agent.

Configure via .env:
    LANGFUSE_PUBLIC_KEY=pk-lf-...
    LANGFUSE_SECRET_KEY=sk-lf-...
    LANGFUSE_HOST=https://cloud.langfuse.com   (or self-hosted)

Without keys, tracing is silently disabled.
"""
import logging
import os

from src.config import settings

logger = logging.getLogger(__name__)

_client = None
_handler = None


def _is_configured() -> bool:
    return bool(settings.langfuse_public_key and settings.langfuse_secret_key)


def init_langfuse():
    """Call once at app startup — initializes client & LangChain callback handler."""
    global _client, _handler
    if _client is not None or not _is_configured():
        if not _is_configured():
            logger.info("Langfuse not configured — tracing disabled.")
        return

    # Langfuse reads its credentials from the environment
    os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
    os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
    os.environ["LANGFUSE_HOST"] = settings.langfuse_host

    try:
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler
    except ImportError:
        logger.warning("langfuse package not installed — tracing disabled.")
        return

    _client = Langfuse()
    _handler = CallbackHandler()
    logger.info("Langfuse tracing enabled → %s", settings.langfuse_host)


def get_langfuse_handler():
    return _handler


def get_langfuse_client():
    return _client
