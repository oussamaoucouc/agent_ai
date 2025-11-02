"""
AI Assistant Agent functionality using AGNO framework.
"""
from textwrap import dedent
import os
import logging
from agno.agent import Agent
from agno.storage.postgres import PostgresStorage
from agno.memory.v2.db.sqlite import SqliteMemoryDb
from agno.memory.v2.memory import Memory
from .config import DB_URL, get_current_model, OLLAMA_BASE_URL

logging.basicConfig(level=logging.INFO)



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
    
    # Create memory instance for the assistant agent
    memory_db_assistant = SqliteMemoryDb(
        table_name="agent_memories_assistant",
        db_file=db_file_path,
    )
    memory_assistant = Memory(db=memory_db_assistant)
    
    return memory_assistant

async def run_assistant_agent_async(query, user_id, session_id):
    """
    AGNO Assistant agent.
    Using cached knowledge base and memory DBs for better performance.
    """
    logging.info(f"Starting AI Assistant agent with Ollama at: {OLLAMA_BASE_URL}")
    
    # Get per-user/session memory DB
    memory_assistant = await initialize_memory_dbs(user_id, session_id)
    storage_session_id = f"{user_id}_{session_id}"  # For PostgresStorage isolation

    
    assistant_agent = Agent(
        model=get_current_model(),
        reasoning=False,
        name="assistant_agent",
        session_id=session_id,
        session_state={"user_id":user_id, "session_id":session_id},
        add_state_in_messages=True,
        role="General AI Assistant that answer questions and provide insights across various domains based on available knowledge",
        user_id=user_id,
        description=dedent(f"""\
            You are an intelligent AI assistant optimized for high accuracy and comprehensive support.
            Your primary function is to help users with their queries.
            
            Key capabilities:
            - Answer questions across diverse topics and domains
            - Provide detailed explanations and insights
            - Assist with research, analysis, and problem-solving
            - Adapt your communication style to match user needs
            
            Always listen carefully to user demands and provide helpful, accurate, and well-reasoned responses based on your training knowledge.
            """),
        markdown=True,
        read_chat_history=True,
        add_history_to_messages=True,
        num_history_responses=5,
        monitoring=True,
        show_tool_calls=True,
        storage = PostgresStorage(table_name="agent_session", db_url=DB_URL),
        memory=memory_assistant,
        enable_user_memories=True,
        enable_session_summaries=True,
        instructions=dedent("""\
        Follow these rules for every user interaction:

        1. ▶ Greeting & Simple Query Handling
        - If the user's message is a greeting or pleasantry (e.g., "hi", "hello", "good evening"), reply immediately with a warm, human greeting such as:
            "Hello! How can I help you today?"
        - If the user asks a straightforward, one‑step factual question that you can answer confidently from built‑in knowledge, respond directly with a clear, complete answer.

        2. ▶ Clarify The Request
        - If the request is ambiguous, multi‑part, or has hidden assumptions, ask brief clarifying questions before answering.
        - Confirm the user's goal and any constraints (format, depth, examples, language).

        3. ▶ Build The Best Answer
        - Provide accurate, well‑structured explanations with step‑by‑step reasoning.
        - Use examples, comparisons, and short lists when they improve clarity.
        - Show calculations and assumptions explicitly when relevant.

        4. ▶ When Information Is Uncertain
        - If you are not fully confident, state limits clearly and avoid speculation.
        - Offer safe alternatives, practical next steps, or how to verify the result.

        5. ▶ Tone & Style
        - Be friendly, helpful, and professional.
        - Keep responses concise but complete; avoid overly terse or robotic phrasing.

        6. ▶ Behavior & Safety
        - Rely on your training knowledge and the current session context.
        - Do not claim access to live data or external tools unless explicitly provided.
        - Never fabricate citations, data, or sources.
        
 """),
    )

    try:

        response = await assistant_agent.arun(query)
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

        # --- MINIMAL LOGGING ---
        logging.info("INFO Generated assistant response for query.")

        return result_content

    except Exception as e:
        logging.error(f"Error in assistant agent: {type(e).__name__}: {str(e)}")
        import traceback
        logging.error(f"Full traceback: {traceback.format_exc()}")
        raise RuntimeError(f"An error occurred while generating a response: {e}")


def run_assistant_agent(query, user_id, session_id):
    """
    Entry point for Assistant agent that works in both synchronous and asynchronous contexts.
    """
    import asyncio

    # Check if we're already in an event loop
    try:
        loop = asyncio.get_running_loop()
        is_in_loop = True
    except RuntimeError:
        is_in_loop = False

    if is_in_loop:
        # Return coroutine that caller can await
        logging.info("Running assistant in existing event loop")
        return run_assistant_agent_async(query, user_id, session_id)
    else:
        # No event loop running, so create a new one
        logging.info("Creating new event loop for assistant agent")
        return asyncio.run(run_assistant_agent_async(query, user_id, session_id))