"""
MCP Agent functionality using the AGNO framework.
Configurable MCP transport (streamable-http or stdio) with clean lifecycle.
"""
from textwrap import dedent
import os
import logging

from agno.agent import Agent
from agno.storage.postgres import PostgresStorage
from agno.memory.v2.db.sqlite import SqliteMemoryDb
from agno.memory.v2.memory import Memory
from .config import (
    DB_URL, get_current_model, OLLAMA_BASE_URL,
    MCP_TRANSPORT, MCP_SERVER_URL, MCP_STDIO_COMMAND, MCP_STDIO_ARGS,
)
from agno.tools.mcp import MCPTools
from mcp.shared.exceptions import McpError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
    logger.info(f"Starting MCP agent with Ollama at: {OLLAMA_BASE_URL}")
    
    # Get cached knowledge base and memory DBs
    memory_mcp = await initialize_memory_dbs(user_id, session_id)
    storage_session_id = f"{user_id}_{session_id}"  # For PostgresStorage isolation

    # Memory DBs already initialized via the cached function
    # Common Agent configuration to avoid duplication across transports
    agent_common_kwargs = dict(
        model=get_current_model(),
        name="mcp_llm_agent",
        instructions=dedent("""\
            You are an AI assistant that MUST use MCP tools to answer.
            Presentation requirements:
            - Always choose and invoke the most relevant MCP tool(s).
            - Do not speculate; rely only on tool outputs.
            - If tools are insufficient, reply exactly:
              "Unable to answer with available MCP tools."
            - When tools provide sources, include concise citations or identifiers.

            Format every response using Markdown with these sections:
            - **Title**: one line summarizing the request.
            - **Key Findings**: numbered list of 2–6 high-impact points.
            - **Details**: short bullets grouped logically; avoid redundancy.
            - **Conclusion**: crisp takeaway or recommended next step.
            - **Notes**: caveats, data gaps, or limitations.
            - **Summary**: one-paragraph recap in plain language.

            Style guidelines:
            - Use bold section headers and short sentences.
            - Prefer facts, numbers, and clear attributions.
            - Keep answers concise and factual based on tool results.
        """),
        markdown=True,
        show_tool_calls=True,
        reasoning=True,
        session_id=storage_session_id,
        user_id=user_id,
        session_state={"user_id": user_id, "session_id": session_id},
        add_state_in_messages=True,
        read_chat_history=True,
        add_history_to_messages=False,
        num_history_responses=3,
        monitoring=True,
        storage=PostgresStorage(table_name="agent_session", db_url=DB_URL),
        memory=memory_mcp,
        enable_user_memories=True,
        enable_session_summaries=True,
    )
    
    # Connect to MCP server via configured transport
    try:
        if MCP_TRANSPORT == "streamable-http":
            if not MCP_SERVER_URL:
                raise RuntimeError("MCP_SERVER_URL is required when MCP_TRANSPORT='streamable-http'")
            logger.info(f"Connecting to MCP server at {MCP_SERVER_URL} via streamable-http...")
            async with MCPTools(url=MCP_SERVER_URL, transport="streamable-http") as mcp_tools:
                logger.info("Connected to MCP server")

                MCP_agent = Agent(tools=[mcp_tools], **agent_common_kwargs)

                # Run the agent while MCP connection is open
                response = await MCP_agent.arun(query)
        elif MCP_TRANSPORT == "stdio":
            if not MCP_STDIO_COMMAND:
                raise RuntimeError("MCP_STDIO_COMMAND is required when MCP_TRANSPORT='stdio'")
            # Build a single command string, which is the recommended pattern in Agno docs
            cmd = MCP_STDIO_COMMAND
            if MCP_STDIO_ARGS:
                cmd = " ".join([MCP_STDIO_COMMAND] + MCP_STDIO_ARGS)
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

        return result_content

    except McpError as e:
        logger.error(f"MCP Error: {e}")
        logger.error("This usually means the MCP server failed to start or is not responding.")
        raise
    except Exception as e:
        logger.error(f"Error in mcp agent: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise RuntimeError(f"An error occurred while generating a response: {e}")
