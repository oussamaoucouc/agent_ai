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
from .output_utils import clean_agent_output


logging.basicConfig(level=logging.INFO)


async def run_assistant_agent_async(query, user_id, session_id, images=None, audio=None, videos=None, stream=False):
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
        stream: If True, returns an async generator yielding content chunks
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
            You are a friendly and intelligent AI assistant.
            Your primary function is to help users with their queries in a natural, conversational way.
            
            Key capabilities:
            - Answer questions across diverse topics and domains
            - Provide detailed but easy-to-understand explanations
            - Assist with research, analysis, and problem-solving
            - Adapt your communication style to match user needs
            
            Always listen carefully to user demands and provide helpful, accurate, and friendly responses.
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

        2. **SIMPLICITY & CLARITY (The "Coffee Shop" Test)**
        - Explain complex topics as if you are talking to a friend at a coffee shop.
        - Avoid words like "manifest," "utilize," "elucidate," or "meta-logic" unless absolutely necessary.
        - Use analogies from real life to explain abstract concepts.

        3. **FORMATTING FOR SCANNABLE READABILITY** (CRITICAL for UX)
        - **Short Paragraphs**: Keep paragraphs to 2-3 sentences maximum
        - **Blank Lines**: Add blank lines between different ideas or topics
        - **Numbered Lists**: ALWAYS put numbered items on SEPARATE lines
          - ✅ GOOD:
            ```
            Here's how to do it:
            
            1. First step explanation
            2. Second step explanation
            3. Third step explanation
            ```
          - ❌ BAD: "Here's how:1. First2. Second3. Third"
        - **Visual Breathing Room**: Give important info space to stand out
        - **Use Bold Titles** for sections (Do NOT use Markdown headers like #, ##, ###, or ####)
        - Use bullet points to break up walls of text
        - **Do NOT** use code blocks (backticks) for simple text or numbers. Only use them for actual code snippets.

        4. **IMAGE & DOCUMENT ANALYSIS**
        - When analyzing images (cheques, receipts, etc.), **do NOT** produce a stiff, robotic report.
        - **Avoid** headers like "#### 1. Cheque Explanation" or "Visible Information".
        - **Instead**, say something like: "Here are the details from the cheque:" followed by a clean list.
        - **Example:**
            - **Cheque Number:** 1800028
            - **Bank:** Banque Populaire
            - **Amount:** 2,211,461.17 MAD
        - Make it look like a helpful summary, not a database dump.

        5. **TONE CHECK**
        - **Friendly:** "Here's how that works..." NOT "The mechanism functions as follows..."
        - **Humble:** "I'm not sure about that part," NOT "My data is insufficient."
        - **Human:** Use natural transitions. Avoid stiff structure.
        
        6. **READABILITY PRIORITY**
        - Every response should be easy to scan and digest
        - If you have multiple points, separate them visually
        - Put questions or calls-to-action on new lines with spacing
 """),
    )

    try:
        if stream:
            # Streaming mode: return an async generator that yields content chunks
            async def stream_generator():
                try:
                    # AGNO v1.8: arun with stream=True returns Iterator[RunResponse]
                    # stream_intermediate_steps=False prevents tool execution logs from appearing
                    run_response = await assistant_agent.arun(
                        query,
                        stream=True,
                        stream_intermediate_steps=False,
                        images=images if images else None,
                        audio=audio if audio else None,
                        videos=videos if videos else None
                    )
                    # In v1.8, just access chunk.content directly
                    async for chunk in run_response:
                        if hasattr(chunk, 'content') and chunk.content:
                            # Clean each chunk for consistency
                            cleaned_chunk = clean_agent_output(chunk.content, agent_type="assistant")
                            if cleaned_chunk:  # Only yield non-empty chunks
                                yield cleaned_chunk
                except Exception as e:
                    logging.error(f"Error in streaming: {type(e).__name__}: {str(e)}")
                    raise
            
            logging.info("INFO Starting streaming assistant response for query.")
            return stream_generator()
        else:
            # Non-streaming mode: return complete response
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

            # Apply output cleaning for consistency
            cleaned_content = clean_agent_output(result_content, agent_type="assistant")
            return cleaned_content

    except Exception as e:
        logging.error(f"Error in assistant agent: {type(e).__name__}: {str(e)}")
        import traceback
        logging.error(f"Full traceback: {traceback.format_exc()}")
        raise RuntimeError(f"An error occurred while generating a response: {e}")



def run_assistant_agent(query, user_id, session_id, images=None, audio=None, videos=None, stream=False):
    """
    Entry point for Assistant agent that works in both synchronous and asynchronous contexts.
    Supports multimodal inputs (images, audio, videos) and streaming.
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
        return run_assistant_agent_async(query, user_id, session_id, images, audio, videos, stream)
    else:
        # No event loop running, so create a new one
        logging.info("Creating new event loop for assistant agent")
        return asyncio.run(run_assistant_agent_async(query, user_id, session_id, images, audio, videos, stream))
