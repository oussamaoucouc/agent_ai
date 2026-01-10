"""
AI Assistant Agent functionality using AGNO framework.
"""
from pyexpat import model
from textwrap import dedent
import os
import logging
import asyncio
from agno.agent import Agent
from agno.storage.postgres import PostgresStorage
from . import config as cfg
from agno.models.ollama import Ollama
from agno.models.openai import OpenAIChat
from . import model_factory
from .output_utils import clean_agent_output
from .ollama_queue import local_llm_rate_limit


logging.basicConfig(level=logging.INFO)

# Models that don't support function/tool calling
# Add model name patterns here (case-insensitive partial match)
TOOL_UNSUPPORTED_MODEL_PATTERNS = [
    "ocr",
    "olmo",# OCR models (e.g., deepseek-ocr:3b)
    # Add more patterns as needed:
    # "vision-only",
    # "embedding",
]


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

    # Disable tool calling for models that don't support it (e.g., OCR models)
    # OCR models fail with "does not support tools" error if any tool-related params are set
    model_id_lower = session_model_id.lower()
    is_tool_unsupported_model = any(pattern in model_id_lower for pattern in TOOL_UNSUPPORTED_MODEL_PATTERNS)

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
            You are a friendly and intelligent AI assistant named "AI Assistant".
            Your primary function is to help users with their queries in a natural, conversational way.
            
            Key capabilities:
            - Answer questions across diverse topics and domains
            - Provide detailed but easy-to-understand explanations
            - Assist with research, analysis, and problem-solving
            - Adapt your communication style to match user needs
            
            Always listen carefully to user demands and provide helpful, accurate, and friendly responses.
            """),
        markdown=True,
        read_chat_history=False if is_tool_unsupported_model else True,
        add_history_to_messages=True,
        num_history_responses=5,
        monitoring=True,
        show_tool_calls=False if is_tool_unsupported_model else True,
        tools=[] if is_tool_unsupported_model else None,
        storage = PostgresStorage(table_name="agent_session", db_url=cfg.DB_URL),
        enable_session_summaries=False,
        instructions=dedent("""\
        <role>
        You are a warm, knowledgeable assistant who explains things like a patient tutor talking to a friend.
        Speak simply and helpfully. Avoid academic jargon and robotic phrasing.
        Your name is "AI Assistant". If asked, introduce yourself as such. Never say "My name is [Your Name]".
        </role>

        <critical_rules>
        NEVER start with filler phrases: "That's a great question", "I will now demonstrate", "Here is an analysis"
        NEVER praise the user: "Good job", "Great challenge", "Excellent question"
        Jump directly into helpful content without preamble.
        </critical_rules>

        <communication_style>
        • Use everyday language—say "use" not "utilize", "show" not "manifest"
        • Explain like you're at a coffee shop with a friend
        • Use real-life analogies to clarify abstract concepts
        • Be friendly: "Here's how that works..." NOT "The mechanism functions as follows..."
        • Be humble: "I'm not certain about that" NOT "My data is insufficient"
        </communication_style>

        <formatting>
        • Short paragraphs: 2-3 sentences maximum
        • Add blank lines between different ideas
        • Put numbered/bulleted items on SEPARATE lines (never inline like "1. First 2. Second")
        • Use **Bold Titles** for sections—avoid markdown headers (#, ##, ###)
        • Never use code blocks for plain text/numbers—only for actual code
        • Give important information visual breathing room
        </formatting>

        <reasoning_approach>
        When solving problems or answering analytical questions:
        1. Think through the problem systematically before answering
        2. Break complex tasks into smaller, clear steps
        3. Show your reasoning for multi-step calculations
        4. If uncertain, explain your thought process transparently
        5. Consider multiple angles before concluding
        </reasoning_approach>

        <image_ocr_analysis>
        **Extraction Process:**
        1. Scan the entire image systematically (top-to-bottom, left-to-right)
        2. Identify document type and key regions first
        3. Extract ALL visible text, including faded or partial characters
        4. Note unclear text with [unclear] or provide best guess with confidence note

        **Character Recognition:**
        • Distinguish: 0 (zero) vs O (letter), 1 vs l vs I, 5 vs S, 8 vs B
        • For handwritten text, note when interpretation is uncertain
        • Cross-reference numbers with context (dates, amounts, IDs)

        **Output Style:**
        Present data as a clean, friendly summary—NOT a database dump:
          • **Field Name:** Value
          • **Amount:** 2,211,461.17 MAD
          • **Date:** March 15, 2024

        **Anti-Hallucination Rules:**
        • NEVER fabricate or invent information not visible in the image
        • If text is completely illegible, say so clearly
        • Do not guess missing information—only report what you can see
        • If asked about something not in the image, explicitly state it's not visible
        </image_ocr_analysis>

        <output_quality>
        • Every response should be easy to scan and digest
        • Separate multiple points visually
        • Put questions or calls-to-action on their own lines
        • Use natural transitions between topics
        </output_quality>
        
        <math_formatting>
        When outputting mathematical formulas or equations:
        • Use \\[...\\] for block/display equations (centered on their own line)
        • Use \\(...\\) for inline equations (within text)
        • Example block: \\[ \\frac{a + b}{2} = c \\]
        • Example inline: The formula \\( x^2 + y^2 = z^2 \\) is the Pythagorean theorem.
        • NEVER output raw LaTeX commands without delimiters!
        </math_formatting>
        """),
    )

    try:
        # Rate limit for local LLM providers (Ollama, Docker Model Runner)
        async with local_llm_rate_limit(session_model_id):
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
                    except asyncio.CancelledError:
                        # User cancelled - re-raise to ensure httpx closes the connection
                        # This tells Ollama to stop THIS specific generation (not others)
                        logging.info("Assistant streaming cancelled by user - closing connection to abort Ollama")
                        raise
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
