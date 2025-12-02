"""
MCP Agent functionality using the AGNO framework.
Configurable MCP transport (streamable-http or stdio) with clean lifecycle.
"""
from textwrap import dedent
import re
import os
import logging
import asyncio
from agno.agent import Agent
from agno.storage.postgres import PostgresStorage
from agno.tools.mcp import MultiMCPTools
from . import config as cfg
from . import model_factory
logger = logging.getLogger(__name__)
_ARTIFACT_TOKEN_REGEX = re.compile(
    r"\s*(?:<\|im_end\|>|<\|im_start\|>|<\|eot\|>|<eot>|</s>|<end_of_role>|end_of_role|<end_of_turn>|end_of_turn)\s*",
    re.IGNORECASE,
)

def _clean_output_artifacts(text: str) -> str:
    """Robustly remove chat-template artifact tokens without harming legitimate content.

    Strategy:
    - Drop lines that are only an artifact token.
    - Remove tokens anywhere using a compiled regex with surrounding whitespace.
    - Tidy trailing unmatched angle brackets that can appear due to partial tokens.
    """
    if not isinstance(text, str):
        return text

    # 1) Remove lines that are only an artifact token
    def _is_artifact_line(line: str) -> bool:
        return bool(_ARTIFACT_TOKEN_REGEX.fullmatch(line.strip()))

    lines = [ln for ln in text.splitlines() if not _is_artifact_line(ln)]
    cleaned = "\n".join(lines)

    # 2) Remove artifact tokens appearing inline
    cleaned = _ARTIFACT_TOKEN_REGEX.sub(" ", cleaned)

    # 3) Normalize spacing and trim
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\s*\n\s*", "\n", cleaned).strip()

    # 4) Remove stray terminal angle brackets only if not part of a tag
    if cleaned.endswith(">") and not re.search(r"</?\w+>$", cleaned):
        cleaned = cleaned[:-1].rstrip()
    if cleaned.endswith("<"):
        cleaned = cleaned[:-1].rstrip()

    # 5) Strip common partial artifact tails like "<|" or a lone "|"
    cleaned = re.sub(r"\s*(?:<\|?|\|)\s*$", "", cleaned).rstrip()

    return cleaned


def run_agent(query, user_id, session_id, images=None, audio=None, videos=None):
    """
    Entry point for MCP agent that works in both synchronous and asynchronous contexts.
    Supports multimodal inputs (images, audio, videos).
    """
    import asyncio
    
    # Check if we're already in an event loop
    try:
        loop = asyncio.get_running_loop()
        is_in_loop = True
    except RuntimeError:
        is_in_loop = False
    
    if is_in_loop:
        # We're already in an event loop, so we need to return a coroutine
        # that the caller can await
        logging.info("Running in existing event loop")
        return run_agent_async(query, user_id, session_id, images, audio, videos)
    else:
        # No event loop running, so create a new one
        logging.info("Creating new event loop")
        return asyncio.run(run_agent_async(query, user_id, session_id, images, audio, videos))



async def run_agent_async(query, user_id, session_id, images=None, audio=None, videos=None):
    """
    AGNO MCP agent using MCP server tools.
    Using cached knowledge base and memory DBs for better performance.
    
    Args:
        query: Text query
        user_id: User ID
        session_id: Session ID
    """
    logger.info(f"Starting MCP agent with Ollama at: {cfg.OLLAMA_BASE_URL}")
    logger.info(f"OpenAI-compatible base URL: {cfg.get_openai_base_url()}")
    
    # Get cached knowledge base and memory DBs
    #memory_mcp = await initialize_memory_dbs(user_id, session_id)
    storage_session_id = f"{user_id}_{session_id}"  # For PostgresStorage isolation

    # Resolve per-session model preference
    try:
        import sessions as session_mod
        with session_mod.SessionLocal() as db:
            session_model_id = session_mod.get_session_model_id(db, user_id, session_id)
        logger.info(f"MCP agent model selected: user={user_id}, session={session_id}, model_id={session_model_id}")
        session_model = model_factory.create_model(
            model_id=session_model_id,
            openai_api_key=cfg.OPENAI_API_KEY,
            google_api_key=cfg.GOOGLE_API_KEY,
            openrouter_api_key=cfg.OPENROUTER_API_KEY,
            ollama_base_url=cfg.OLLAMA_BASE_URL,
            openai_base_url=cfg.OPENAI_BASE_URL,
            gemini_search_enabled=cfg.GEMINI_SEARCH_ENABLED,
        )
    except Exception as e:
        logger.warning(f"Falling back to current model for MCP due to error resolving session model: {e}")
        session_model = cfg.get_current_model()

    agent_common_kwargs = dict(
        model=session_model,
        name="mcp_llm_agent",
        instructions=dedent("""\
        ### ROLE & OBJECTIVE
        You are an expert AI assistant empowered with MCP (Model Context Protocol) tools. Your goal is to answer questions by orchestrating these tools precisely while maintaining a friendly, human conversation.

        ### CORE BEHAVIOR & ROUTING

        1. **GREETINGS & SMALL TALK**
        - If the user provides a pleasantry (e.g., "Hi", "Hello"), DO NOT call tools. Reply immediately: "Hello! How can I help you today?"

        2. **TOOL EXECUTION PROTOCOL (STRICT)**
        - **Silent Execution:** You must invoke tools to get data, but **NEVER** display the raw JSON, tool names, API parameters, or "thought process" to the user. The tool usage must be invisible.
        - **Expert Configuration:** Configure tool parameters precisely based on the user's prompt.
        - **Strict Reliance:** Do not invent facts. Answer purely based on the information returned by the tool.
        - **Privacy:** Never reveal internal function names (e.g., `get_weather_v2`) or API keys.

        3. **RESPONSE SYNTHESIS (How to Speak)**
        - **The Intro:** Start with a friendly, direct answer in 1–2 sentences.
        - **The Detail:** Follow with 3–8 clear bullet points explaining key details or context derived from the tool output.
        - **The Guide:** If instructions are needed, use a short numbered list of actionable steps.
        - **Citations:** If the tool provides sources, include brief citations (Title + Link/ID).
        - **Formatting:** Use **Bold Titles** for sections. **DO NOT** use Markdown headers (#, ##).

        ### HANDLING FAILURES
        - If a tool is unavailable, missing configuration, or fails to return data, reply exactly with this phrase:
        "Unable to answer with available tools."
        - Do not apologize excessively or explain the technical failure (e.g., "HTTP 500 error").

        ### STYLE & TONE GUIDELINES
        - **Be Conversational:** Speak like a helpful colleague, not a database.
        - **Be Direct:** No "I have retrieved the data..." or "According to the tool..." simply state the facts.
        - **No Fluff:** Avoid philosophical statements about being an AI.
        - **Visuals:** If helpful, provide a brief code snippet or command example, but only if derived from the tool.
        """),
        markdown=True,
        show_tool_calls=False,
        reasoning=False,
        session_id=storage_session_id,
        user_id=user_id,
        session_state={"user_id": user_id, "session_id": session_id},
        add_state_in_messages=True,
        read_chat_history=True,
        add_history_to_messages=True,
        num_history_responses=3,
        monitoring=True,
        storage=PostgresStorage(table_name="agent_session", db_url=cfg.DB_URL),
        #memory=memory_mcp,
        #enable_user_memories=True,
        enable_session_summaries=False,
    )
    
    try:
        runtime_cfg = cfg.get_runtime_config()
        servers = runtime_cfg.get("mcp_servers", []) or []
        runtime_urls = [str(s.get("url", "")).strip() for s in servers if isinstance(s, dict) and str(s.get("url", "")).strip()]
        selected_urls = []
        selected_cmds = []
        try:
            import sessions as session_mod
            with session_mod.SessionLocal() as db:
                selected_urls = session_mod.get_session_mcp_tools_urls(db, user_id, session_id) or []
                selected_cmds = session_mod.get_session_mcp_stdio_commands(db, user_id, session_id) or []
        except Exception as e:
            logger.warning(f"Failed to resolve user-selected MCP tools; using runtime config. err={e}")

        urls = []
        cmds = []

        if selected_urls:
            urls = [u for u in selected_urls if str(u).strip()]
            logger.info(f"Using user-selected MCP tools: {len(urls)} URLs")
        else:
            urls = runtime_urls
            if not urls and cfg.MCP_SERVER_URL:
                urls = [cfg.MCP_SERVER_URL]

        if selected_cmds:
            cmds = [c for c in selected_cmds if str(c).strip()]
            logger.info(f"Using user-selected MCP stdio commands: {len(cmds)}")
        else:
            mcp_cmds = runtime_cfg.get("mcp_stdio_commands", []) or []
            mcp_tools = runtime_cfg.get("mcp_stdio_tools", []) or []
            for t in mcp_tools:
                if isinstance(t, dict):
                    c = str(t.get("command", "")).strip()
                    if c:
                        cmds.append(c)
            for c in mcp_cmds:
                cs = str(c).strip()
                if cs:
                    cmds.append(cs)
            if not cmds and cfg.MCP_STDIO_COMMAND:
                if cfg.MCP_STDIO_ARGS:
                    cmds.append(" ".join([cfg.MCP_STDIO_COMMAND] + cfg.MCP_STDIO_ARGS))
                else:
                    cmds.append(cfg.MCP_STDIO_COMMAND)

        allowed_execs = {"npx","pnpm","node","yarn","python3","uvx","pipx","bun","npm","uv","java","deno","python","ruby"}
        if cmds:
            filtered_cmds = []
            for c in cmds:
                head = str(c).strip().split()[0] if str(c).strip() else ""
                if head in allowed_execs:
                    filtered_cmds.append(c)
            cmds = filtered_cmds

        if not urls and not cmds:
            raise RuntimeError("No MCP servers configured")

        multi_mcp_tools = MultiMCPTools(
            commands=cmds if cmds else None,
            urls=urls if urls else None,
            urls_transports=["streamable-http"] * len(urls) if urls else None,
            env={**os.environ},
            timeout_seconds=30,
        )
        await multi_mcp_tools.connect()
        MCP_agent = Agent(tools=[multi_mcp_tools], **agent_common_kwargs)
        try:
            response = await MCP_agent.arun(query)
        finally:
            await multi_mcp_tools.close()

        # --- Robust error checking for response.content ---
        # Explicit check for boolean response
        if isinstance(response, bool):
            raise RuntimeError(
                f"AGNO agent returned a boolean ({response}) instead of a response object. "
                "This usually means the agent or routing failed. Please check the agent configuration and query."
            )

        # Check for callable (function) or string content
        if hasattr(response, 'content'):
            if callable(response.content):
                try:
                    content_result = response.content()
                except Exception as e:
                    raise RuntimeError(f"Error calling response.content(): {e}")
                if not isinstance(content_result, str):
                    raise RuntimeError(f"response.content() did not return a string: got {type(content_result)}")
                result_content = content_result
            elif isinstance(response.content, str):
                result_content = response.content
            else:
                raise RuntimeError(
                    f"response.content is not a string or callable, got type: {type(response.content)} and value: {response.content}"
                )
        else:
            raise RuntimeError(
                f"Response object of type {type(response)} does not have a 'content' attribute. Value: {response}"
            )

        # --- LOGGING RETRIEVED DOCUMENTS ---
        docs = None
        if hasattr(response, "documents") and response.documents:
            docs = response.documents
        elif hasattr(response, "retrieved_docs") and response.retrieved_docs:
            docs = response.retrieved_docs
        elif hasattr(response, "sources") and response.sources:
            docs = response.sources
        if docs is not None:
            logging.info(f"INFO Retrieved {len(docs)} documents for query: {query}")
            for i, doc in enumerate(docs, 1):
                title = getattr(doc, 'title', None) or doc.get('title', 'No Title') if isinstance(doc, dict) else 'No Title'
                source = getattr(doc, 'source', None) or doc.get('source', 'Unknown') if isinstance(doc, dict) else 'Unknown'
                logging.info(f"INFO Document {i}: Title: {title} | Source: {source}")
        else:
            logging.info("INFO No document retrieval details available in response.")

        # Sanitize artifact tokens that some models/tools may emit
        return _clean_output_artifacts(result_content)

    except McpError as e:
        logger.error(f"MCP Error: {e}")
        logger.error("This usually means the MCP server failed to start or is not responding.")
        # Return a safe user-facing fallback instead of surfacing internal errors
        return "Unable to answer with available tools."
    except asyncio.CancelledError:
        # Propagate cancellation so API endpoints can return 499
        logger.info("MCP agent cancelled")
        raise
    except Exception as e:
        logger.error(f"Error in mcp agent: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise RuntimeError(f"An error occurred while generating a response: {e}")
