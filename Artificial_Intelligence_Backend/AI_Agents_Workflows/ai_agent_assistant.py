"""
AI Assistant Agent functionality using AGNO framework.
"""
from pyexpat import model
from textwrap import dedent
import os
import logging
from agno.agent import Agent
from agno.storage.postgres import PostgresStorage
from . import config as cfg
from agno.models.ollama import Ollama
from agno.models.openai import OpenAIChat
from . import model_factory


logging.basicConfig(level=logging.INFO)


async def run_assistant_agent_async(query, user_id, session_id, images=None, audio=None, videos=None):
    """
    AGNO Assistant agent with multimodal support.
    Using cached knowledge base and memory DBs for better performance.
    
    Args:
        query: Text query
        user_id: User ID
        session_id: Session ID
        images: Optional list of Agno Image objects
        audio: Optional list of Agno Audio objects
        videos: Optional list of Agno Video objects
    """
    logging.info(f"Starting AI Assistant agent with Ollama at: {cfg.OLLAMA_BASE_URL}")
    logging.info(f"OpenAI-compatible base URL: {cfg.get_openai_base_url()}")
    
    # Get per-user/session memory DB
    #memory_assistant = await initialize_memory_dbs(user_id, session_id)
    storage_session_id = f"{user_id}_{session_id}"  # For PostgresStorage isolation

    # Resolve per-session model preference
    try:
        import sessions as session_mod
        with session_mod.SessionLocal() as db:
            session_model_id = session_mod.get_session_model_id(db, user_id, session_id)
        logging.info(f"Assistant agent model selected: user={user_id}, session={session_id}, model_id={session_model_id}")
        session_model = model_factory.create_model(
            model_id=session_model_id,
            openai_api_key=cfg.OPENAI_API_KEY,
            google_api_key=cfg.GOOGLE_API_KEY,
            openrouter_api_key=cfg.OPENROUTER_API_KEY,
            ollama_base_url=cfg.OLLAMA_BASE_URL,
            openai_base_url=cfg.OPENAI_BASE_URL,
            gemini_search_enabled=cfg.GEMINI_SEARCH_ENABLED
        )
    except Exception as e:
        logging.warning(f"Falling back to current model for assistant due to error resolving session model: {e}")
        session_model = cfg.get_current_model()

    assistant_agent = Agent(
        model=session_model,
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
        storage = PostgresStorage(table_name="agent_session", db_url=cfg.DB_URL),
        enable_session_summaries=False,
        instructions=dedent("""\
        ### ROLE & PERSONA
        You are a warm, knowledgeable, and clear communicator. Your goal is to explain things simply and helpfully, like a smart friend or a patient tutor. You avoid academic jargon and robotic phrasing.

        ### CORE CONVERSATION RULES

        1. **THE "NO-FLUFF" START**
        - **Do NOT** start with: "That is an excellent question," "I will now demonstrate," or "Here is an analysis."
        - **Do NOT** praise the user ("Good job," "Great challenge").
        - **Action:** Jump straight into the helpful content.
            - *Bad:* "That is a complex topic. I will explain it using logic..."
            - *Good:* "Gödel's Incompleteness Theorem is a fascinating concept that basically says..."

        2. **SIMPLICITY & CLARITY (The "Coffee Shop" Test)**
        - Explain complex topics as if you are talking to a friend at a coffee shop.
        - Avoid words like "manifest," "utilize," "elucidate," or "meta-logic" unless absolutely necessary (and then define them).
        - Use analogies from real life to explain abstract concepts.

        3. **FORMATTING FOR READABILITY**
        - Use **Bold Titles** for sections (Do NOT use Markdown headers like # or ##).
        - Use bullet points to break up walls of text.
        - Keep paragraphs short (2-3 sentences max).

        4. **WHEN USING TOOLS (If applicable)**
        - If you use internal tools to get an answer, do not show the technical details (JSON/API calls).
        - Simply weave the facts into your friendly response.

        ### TONE CHECK
        - **Friendly:** "Here's how that works..." NOT "The mechanism functions as follows..."
        - **Humble:** "I'm not sure about that part," NOT "My data is insufficient."
        - **Human:** Use natural transitions. Avoid stiff structure.
 """),
    )

    try:
        # Pass multimodal inputs to agent if provided
        response = await assistant_agent.arun(
            query,
            images=images if images else None,
            audio=audio if audio else None,
            videos=videos if videos else None
        )
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


def run_assistant_agent(query, user_id, session_id, images=None, audio=None, videos=None):
    """
    Entry point for Assistant agent that works in both synchronous and asynchronous contexts.
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
        # Return coroutine that caller can await
        logging.info("Running assistant in existing event loop")
        return run_assistant_agent_async(query, user_id, session_id, images, audio, videos)
    else:
        # No event loop running, so create a new one
        logging.info("Creating new event loop for assistant agent")
        return asyncio.run(run_assistant_agent_async(query, user_id, session_id, images, audio, videos))