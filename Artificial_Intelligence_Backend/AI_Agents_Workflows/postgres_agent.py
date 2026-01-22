
"""
Postgres Agent functionality using AGNO framework.
Allows users to naturally query their assigned PostgreSQL database.
"""
from textwrap import dedent
import logging
import asyncio
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url
from agno.agent import Agent
from agno.storage.postgres import PostgresStorage
from agno.tools.postgres import PostgresTools
from . import config as cfg
from . import model_factory
from .ollama_queue import local_llm_rate_limit
from .output_utils import clean_agent_output  # Added for output cleaning

logging.basicConfig(level=logging.INFO)

def get_user_postgres_url(user_id: str) -> str | None:
    """Retrieve the per-user Postgres connection string."""
    try:
        engine = create_engine(cfg.DB_URL)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT postgres_db_url FROM app_users WHERE id = :uid"), {"uid": user_id}).fetchone()
            if result and result[0]:
                return result[0]
    except Exception as e:
        logging.error(f"Error fetching postgres url for user {user_id}: {e}")
    return None

async def run_postgres_agent(query: str, user_id: str, session_id: str, stream: bool = False):
    """
    Dedicated Postgres Agent for database querying.
    """
    logging.info(f"Starting Postgres Agent for user {user_id}")
    
    # Get user's DB URL
    db_url = get_user_postgres_url(user_id)
    
    # If not configured, return a polite error
    if not db_url:
        msg = "⚠️ **Configuration Error**: No PostgreSQL database is linked to your account.\n\nPlease ask your administrator to configure the **Postgres Connection String** in your user profile."
        if stream:
            async def _gen():
                yield msg
            return _gen()
        return msg

    # Initialize Tools
    # Initialize Tools
    # Note: Using direct connection and parsing URL components to handle options correctly
    try:
        import psycopg2
        
        # Parse URL to get components using SQLAlchemy (handles dialect prefixes etc.)
        url = make_url(db_url)
        
        # Build connection kwargs
        conn_args = {
            "dbname": url.database,
            "user": url.username,
            "password": url.password,
            "host": url.host,
            "port": url.port
        }
        
        # Explicitly handle options from query params (e.g. search_path)
        if hasattr(url, 'query') and "options" in url.query:
            conn_args["options"] = url.query["options"]
        
        connection = psycopg2.connect(**conn_args)
        pg_tools = PostgresTools(connection=connection)
    except Exception as e:
        msg = f"⚠️ **Connection Error**: Could not connect to the database.\nDetails: {str(e)}"
        if stream:
            async def _gen():
                yield msg
            return _gen()
        return msg
    except Exception as e:
        msg = f"⚠️ **Connection Error**: Could not connect to the database.\nDetails: {str(e)}"
        if stream:
            async def _gen():
                yield msg
            return _gen()
        return msg

    # Resolve per-session model preference (FIXED: Respect user choice)
    storage_session_id = f"{user_id}_{session_id}"
    try:
        import sessions as session_mod
        with session_mod.SessionLocal() as db:
            session_model_id = session_mod.get_session_model_id(db, user_id, session_id)
        logging.info(f"Postgres agent model selected: user={user_id}, session={session_id}, model_id={session_model_id}")
        
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
        logging.warning(f"Falling back to current model for Postgres agent due to error: {e}")
        session_model = cfg.get_current_model()
        session_model_id = cfg.get_default_model_id() # Fallback ID for rate limiter

    # Define Agent
    pg_agent = Agent(
        model=session_model,
        name="postgres_analyst",
        debug_mode=True,
        session_id=session_id,
        user_id=user_id,
        session_state={
            "user_id": user_id, 
            "session_id": session_id
        },
        tools=[pg_tools],
        show_tool_calls=False,
        markdown=True,
        monitoring=True,
        read_chat_history=True,
        add_history_to_messages=True,
        num_history_responses=3,
        storage=PostgresStorage(table_name="agent_session", db_url=cfg.DB_URL),
        description="You are an expert Database Administrator and SQL Analyst.",
        instructions=dedent("""\
        You are an expert SQL Analyst. Your goal is to answer questions about the database by writing and executing SQL queries.

        ## Capabilities
        - You have access to a PostgreSQL database via `PostgresTools`.
        - You can inspect tables, run queries, and analyze results.

        ## Process
        1. **Explore First**: ALWAYS start by checking what tables exist using `list_tables()` or `describe_table()`. 
           - **CRITICAL**: Do NOT assume tables are in the `public` schema.
           - If querying `information_schema`, do NOT filter by `table_schema = 'public'`. Check ALL schemas (e.g., `crm`, `ai`, etc.).
           - Don't guess table names!
        2. **Plan**: Think locally about the best SQL query to answer the user request.
        3. **Execute**: Run the query.
        4. **Analyze**: Interpret the results and answer the user's question in natural language.

        ## Important Rules
        - **ReadOnly**: Do NOT perform keys/updates/deletes unless explicitly asked and you are sure (though the tools might restrict this).
        - **Privacy**: Do not display sensitive user credentials.
        - **Formatting**: Format SQL blocks with ```sql``` and results as Markdown tables.
        
        If the user asks "what tables are there?", list them.
        If the query fails, correct your SQL and retry.
        """),
    )

    # Execute with Rate Limiting and Cleaning
    try:
        # Rate limit for local LLM providers (ADDED: Fixes concurrency slowness)
        async with local_llm_rate_limit(session_model_id):
            if stream:
                async def stream_generator():
                    try:
                        # Use arun for async execution
                        run_response = await pg_agent.arun(query, stream=True, stream_intermediate_steps=False)
                        async for chunk in run_response:
                            if hasattr(chunk, "content") and chunk.content:
                                # Clean output (ADDED: Fixes artifacts)
                                cleaned_chunk = clean_agent_output(chunk.content, agent_type="postgres")
                                if cleaned_chunk:
                                    yield cleaned_chunk
                            elif isinstance(chunk, str):
                                yield chunk
                    except asyncio.CancelledError:
                        # User cancelled - re-raise to ensure proper cleanup (ADDED: Fixes hanging connections)
                        logging.info("Postgres streaming cancelled by user")
                        raise
                    except Exception as e:
                        logging.error(f"Error in Postgres agent streaming: {e}")
                        yield f"Error: {str(e)}"

                return stream_generator()
            else:
                response = await pg_agent.arun(query, stream=False)
                # Clean final output
                if hasattr(response, 'content'):
                    return clean_agent_output(response.content, agent_type="postgres")
                return response.content
    except Exception as e:
        logging.error(f"Error executing Postgres agent: {e}")
        return f"Error: {str(e)}"
