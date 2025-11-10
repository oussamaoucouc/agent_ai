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
from agno.memory.v2.db.sqlite import SqliteMemoryDb
from agno.memory.v2.memory import Memory
from . import config as cfg
from agno.tools.mcp import MCPTools
try:
    # Optional advanced params for streamable-http to increase timeouts
    from agno.tools.mcp import StreamableHTTPClientParams  # available in Agno >=1.8
    HAS_STREAMABLE_PARAMS = True
except Exception:
    HAS_STREAMABLE_PARAMS = False
from mcp.shared.exceptions import McpError
from contextlib import AsyncExitStack
from agno.models.ollama import Ollama

logging.basicConfig(level=logging.INFO)
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


def run_agent(query, user_id, session_id):
    """
    Entry point for MCP agent that works in both synchronous and asynchronous contexts.
    Uses ChromaDB for vector storage.
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
        return run_agent_async(query, user_id, session_id)
    else:
        # No event loop running, so create a new one
        logging.info("Creating new event loop")
        return asyncio.run(run_agent_async(query, user_id, session_id))


async def initialize_memory_dbs(user_id, session_id):
    """
    Initialize memory databases for agents.
    This function is cached to avoid recreating DBs for the same user/session.
    Each user/session pair gets its own database file.
    """
    # Define a base directory for user-specific databases
    db_base_dir = os.path.join("tmp", "user_session_dbs")
    # Ensure the directory exists
    os.makedirs(db_base_dir, exist_ok=True)
    
    # Construct a unique database file path for this user/session
    db_file_path = os.path.join(db_base_dir, f"memory_{user_id}_{session_id}.db")

    logging.info(f"Initializing memory DBs for user {user_id}, session {session_id} using db: {db_file_path}")
    
    # Create memory instances
    memory_db_mcp = SqliteMemoryDb(
        table_name="agent_memories_mcp",  # Table name can be the same as DB file is unique
        db_file=db_file_path,
    )
    memory_mcp = Memory(db=memory_db_mcp)

    
    return memory_mcp

async def run_agent_async(query, user_id, session_id):
    """
    AGNO MCP agent using MCP server tools.
    Using cached knowledge base and memory DBs for better performance.
    """
    logger.info(f"Starting MCP agent with Ollama at: {cfg.OLLAMA_BASE_URL}")
    
    # Get cached knowledge base and memory DBs
    #memory_mcp = await initialize_memory_dbs(user_id, session_id)
    storage_session_id = f"{user_id}_{session_id}"  # For PostgresStorage isolation

    # Resolve per-session model preference
    try:
        import sessions as session_mod
        with session_mod.SessionLocal() as db:
            session_model_id = session_mod.get_session_model_id(db, user_id, session_id)
        logger.info(f"MCP agent model selected: user={user_id}, session={session_id}, model_id={session_model_id}")
        session_model = Ollama(id=session_model_id, host=cfg.OLLAMA_BASE_URL)
    except Exception as e:
        logger.warning(f"Falling back to current model for MCP due to error resolving session model: {e}")
        session_model = cfg.get_current_model()

    # Memory DBs already initialized via the cached function
    # Common Agent configuration to avoid duplication across transports
    agent_common_kwargs = dict(
        model=session_model,
        name="mcp_llm_agent",
        instructions=dedent("""\
             You are an AI assistant that uses MCP tools to produce accurate, helpful answers.

            Principles:
            - Be an expert in any MCP tool you invoke: understand its capabilities, parameters,
              typical failure modes, and output formats. Configure and use tools precisely.
            - Select and invoke the most relevant MCP tool(s) for the query.
            - Always call tools yourself; never tell the user to use tools.
            - Do not invent facts; rely strictly on tool outputs.
            - Never output pseudocode or instructions for using tools; return only results from actual tool calls.
            - If tools are insufficient or unavailable, reply exactly: "Unable to answer with available tools."
            - When tools provide sources, include brief citations (title + link or identifier).

            Response style (human‑like and informative):
            - Begin with a friendly, direct answer in 1–2 sentences addressing the user.
            - Follow with 3–8 clear bullets explaining what it means, key details, and context.
            - When guiding the user, include a short numbered list of actionable steps.
            - Add a brief example when it improves clarity (code, command, or snippet if relevant).
            - Keep formatting light and readable: concise sections, bullets, and plain language.
            - Avoid heavy templates or excessive headings; prioritize clarity and usefulness.
        """),
        markdown=True,
        show_tool_calls=False,
        reasoning=False,
        session_id=storage_session_id,
        user_id=user_id,
        session_state={"user_id": user_id, "session_id": session_id},
        add_state_in_messages=True,
        read_chat_history=True,
        add_history_to_messages=False,
        num_history_responses=2,
        monitoring=True,
        storage=PostgresStorage(table_name="agent_session", db_url=cfg.DB_URL),
        #memory=memory_mcp,
        #enable_user_memories=True,
        enable_session_summaries=True,
    )
    
    # Connect to MCP server via configured transport
    try:
        if cfg.MCP_TRANSPORT == "streamable-http":
            # Build list of MCP servers from runtime config
            runtime_cfg = cfg.get_runtime_config()
            servers = runtime_cfg.get("mcp_servers", []) or []
            urls = [str(s.get("url", "")).strip() for s in servers if isinstance(s, dict) and str(s.get("url", "")).strip()]
            labels = [str(s.get("label", "Server")) for s in servers if isinstance(s, dict) and str(s.get("url", "")).strip()]

            # Override with per-user selection if present
            try:
                import sessions as session_mod
                with session_mod.SessionLocal() as db:
                    selected_urls = session_mod.get_session_mcp_tools_urls(db, user_id, session_id)
                if selected_urls and len(selected_urls) > 0:
                    urls = selected_urls
                    labels = [f"User Tool {i+1}" for i in range(len(urls))]
                    logger.info(f"Using user-selected MCP tools: {len(urls)} URLs")
            except Exception as e:
                logger.warning(f"Failed to resolve user-selected MCP tools; using runtime config. err={e}")

            # Fallback to single MCP_SERVER_URL if no list is provided
            if not urls and cfg.MCP_SERVER_URL:
                urls = [cfg.MCP_SERVER_URL]
                labels = ["Active MCP Server"]

            if not urls:
                raise RuntimeError("No MCP servers configured. Add at least one URL in the dashboard.")

            logger.info(f"Connecting to {len(urls)} MCP server(s) via streamable-http...")
            for i, u in enumerate(urls):
                logger.info(f"MCP server [{i+1}/{len(urls)}]: {labels[i] if i < len(labels) else 'Server'} -> {u}")

            # Helper: robust connect with retry and longer timeouts while keeping streamable-http
            async def _connect_streamable_http(u: str, stack: AsyncExitStack):
                last_err = None
                # Attempt simple pattern first, then advanced params with longer timeouts
                for attempt in range(2):
                    try:
                        if attempt == 0:
                            t = await stack.enter_async_context(
                                MCPTools(transport="streamable-http", url=u)
                            )
                        else:
                            if HAS_STREAMABLE_PARAMS:
                                params = StreamableHTTPClientParams(
                                    url=u,
                                    timeout=30,
                                    sse_read_timeout=30,
                                    terminate_on_close=True,
                                )
                                t = await stack.enter_async_context(
                                    MCPTools(transport="streamable-http", server_params=params)
                                )
                            else:
                                # If advanced params are unavailable, repeat simple attempt
                                t = await stack.enter_async_context(
                                    MCPTools(transport="streamable-http", url=u)
                                )
                        logger.info(f"Connected MCP server: {u} (attempt {attempt+1})")
                        return t
                    except Exception as e:
                        last_err = e
                        logger.warning(f"MCP connect attempt {attempt+1} failed for {u}: {e}")
                        await asyncio.sleep(0.5)
                logger.error(f"Failed to connect MCP server {u}: {last_err}")
                return None

            # Open all MCP tool connections and create the agent with all tools
            async with AsyncExitStack() as stack:
                tools = []
                for u in urls:
                    t = await _connect_streamable_http(u, stack)
                    if t is not None:
                        tools.append(t)
                if not tools:
                    logger.warning("No MCP servers connected. Returning fallback message.")
                    return "Unable to answer with available tools."

                MCP_agent = Agent(tools=tools, **agent_common_kwargs)
                response = await MCP_agent.arun(query)
        elif cfg.MCP_TRANSPORT == "stdio":
            if not cfg.MCP_STDIO_COMMAND:
                raise RuntimeError("MCP_STDIO_COMMAND is required when MCP_TRANSPORT='stdio'")
            # Build a single command string, which is the recommended pattern in Agno docs
            cmd = cfg.MCP_STDIO_COMMAND
            if cfg.MCP_STDIO_ARGS:
                cmd = " ".join([cfg.MCP_STDIO_COMMAND] + cfg.MCP_STDIO_ARGS)
            logger.info(f"Starting MCP server via stdio: {cmd}")
            async with MCPTools(command=cmd, transport="stdio") as mcp_tools:
                logger.info("Connected to MCP server (stdio)")

                MCP_agent = Agent(tools=[mcp_tools], **agent_common_kwargs)

                # Run the agent while MCP connection is open
                response = await MCP_agent.arun(query)
        else:
            raise RuntimeError(f"Unsupported MCP_TRANSPORT: {MCP_TRANSPORT}")

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
        raise
    except asyncio.CancelledError:
        # Propagate cancellation so API endpoints can return 499
        logger.info("MCP agent cancelled")
        raise
    except Exception as e:
        logger.error(f"Error in mcp agent: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise RuntimeError(f"An error occurred while generating a response: {e}")
