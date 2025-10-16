"""
RAG Agent functionality using AGNO framework.
"""
from pathlib import Path
from textwrap import dedent
import functools
import hashlib
import json
import os
import logging
import pickle

from agno.agent import Agent, AgentMemory
from agno.team.team import Team
from agno.embedder.ollama import OllamaEmbedder
from agno.knowledge.pdf import PDFKnowledgeBase, PDFReader
from agno.vectordb.chroma import ChromaDb
from agno.models.groq import Groq
from agno.models.ollama import Ollama
from agno.storage.postgres import PostgresStorage
from agno.memory.v2.db.sqlite import SqliteMemoryDb
from agno.memory.v2.memory import Memory
from agno.document.chunking.document import DocumentChunking
from agno.tools.reasoning import ReasoningTools
from agno.tools.thinking import ThinkingTools
from agno.tools.knowledge import KnowledgeTools
from agno.storage.sqlite import SqliteStorage
from .config import DB_URL, DATA_DIR, MODEL, OLLAMA_BASE_URL

import logging
logging.basicConfig(level=logging.INFO)

# Set up cache directory
CACHE_DIR = os.path.abspath("./cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def run_rag_agent(query, user_id, session_id):
    """
    Entry point for RAG agent that works in both synchronous and asynchronous contexts.
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
        return run_rag_agent_async(query, user_id, session_id)
    else:
        # No event loop running, so create a new one
        logging.info("Creating new event loop")
        return asyncio.run(run_rag_agent_async(query, user_id, session_id))

async def initialize_knowledge_base():
    """
    Initialize the knowledge base with vector database.
    This function is cached to avoid recreating it on every query.
    """
    logging.info("Initializing knowledge base (first call or after cache clear)")
    logging.info(f"Using Ollama URL for embedder: {OLLAMA_BASE_URL}")
    
    # Create OllamaEmbedder with the correct host parameter
    embedder = OllamaEmbedder(
        id="nomic-embed-text",
        dimensions=768,
        host=OLLAMA_BASE_URL  # FIXED: Add host parameter
    )
    
    vector_db = ChromaDb(
        collection="teacher_test_nomicembedtext",
        path="./tmp/chromadb_nomicembedtext",
        persistent_client=True,
        embedder=embedder
    )
    knowledge_base = PDFKnowledgeBase(
        path=DATA_DIR,
        vector_db=vector_db,
        chunking_strategy=DocumentChunking()
    )
    #new run
    #await knowledge_base.aload(recreate=True, upsert=False)
    await knowledge_base.aload(recreate=False, upsert=True)
    
    
    logging.info("Knowledge base initialization completed")
    return knowledge_base

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
    memory_db_rag = SqliteMemoryDb(
        table_name="agent_memories_rag",  # Table name can be the same as DB file is unique
        db_file=db_file_path,
    )
    memory_rag = Memory(db=memory_db_rag)

    memory_db_llm = SqliteMemoryDb(
        table_name="agent_memories_llm",
        db_file=db_file_path,
    )
    memory_llm = Memory(db=memory_db_llm)

    memory_db_team = SqliteMemoryDb(
        table_name="agent_memories_team",
        db_file=db_file_path,
    )
    memory_team = Memory(db=memory_db_team)
    
    return memory_rag, memory_llm, memory_team

async def run_rag_agent_async(query, user_id, session_id):
    """
    AGNO RAG agent using ChromaDB and openhermes embedder.
    Using cached knowledge base and memory DBs for better performance.
    """
    logging.info(f"Starting RAG agent with Ollama at: {OLLAMA_BASE_URL}")
    
    # Get cached knowledge base and memory DBs
    knowledge_base = await initialize_knowledge_base()
    memory_rag, memory_llm, memory_team = await initialize_memory_dbs(user_id, session_id)
    storage_session_id = f"{user_id}_{session_id}"  # For PostgresStorage isolation

    # Memory DBs already initialized via the cached function
    
    #knowledge tools reasoning, search, analyze, few shot, instructions
    knowledge_tools = KnowledgeTools(
    knowledge=knowledge_base,
    think=True,
    search=True,
    analyze=True,
    add_few_shot=True,
    add_instructions=True,
    )

    teacher_agent = Agent(
        model=MODEL,
        reasoning=True,
        name="teacher_agent_rag",
        session_id=session_id,
        session_state={"user_id":user_id, "session_id":session_id},
        add_state_in_messages=True,
        role="Teacher Agent that uses RAG to answer questions and provide insights for teaching strategies, curriculum design, classroom management, or subject-specific pedagogy",
        user_id=user_id,
        description=dedent(f"""\
            You are an AI teacher named teacher, optimized for low latency, high accuracy, RAG-enabled assistant,and an empathetic teacher-tutor style. 
            Your job is to help elementary school students learn new things in a fun and easy way.
            """),
        tools=[knowledge_tools],
        knowledge=knowledge_base,
        search_knowledge=True,
        markdown=True,
        read_chat_history=True,
        add_history_to_messages=True,
        num_history_responses=5,
        monitoring=True,
        show_tool_calls=True,
        storage = PostgresStorage(table_name="agent_session", db_url=DB_URL),
        memory=memory_rag,  # Add memory instance here
        enable_user_memories=True,
        enable_session_summaries=True,
        instructions=dedent("""\
        Follow these rules for every user interaction:

        1. ▶ Greeting & Simple Query Handling  
        - If the user's message is a greeting or pleasantry (e.g., "hi", "hello", "good evening"), reply immediately with a warm, human greeting such as:  
            "Hello! How can I assist you today?"  
            *Skip any retrieval.*  
        - If the user asks a straightforward, one-step factual question (e.g., "What's 2 + 2?", "When was Python first released?") that you can answer confidently from built‑in knowledge, respond directly in a clear, complete sentence.  
            *Skip retrieval.*  

        2. ▶ Retrieval for Complex or Specialized Queries  
        - If the query involves multi‑step reasoning, in‑depth explanations, domain‑specific terminology, comparisons, how‑to guides, or any information that likely requires consulting external sources or a knowledge base, *invoke retrieval*.  
        - Let the LLM autonomously decide how and when to fetch relevant documents from the retrieval backend (e.g., ChromaDB).  

        3. ▶ Building the Answer  
        - Use retrieved passages to construct your response—but never just spit back a summary.  
        - Write in **detailed, flowing paragraphs**, as if you're explaining the concept face‑to‑face.  
        - Incorporate analogies, real‑world examples, and step‑by‑step reasoning to ensure clarity.  

        4. ▶ Fallback When Retrieval Fails  
        - If no retrieved passage meets relevance criteria, say:  
            "I couldn't find a specific document in the knowledge base, so here's what I know from general understanding."  
        - Then provide a full, paragraph‑based explanation derived from your built‑in knowledge.  

        5. ▶ Tone & Persona  
        - Always adopt a **friendly, supportive tutor** persona.  
        - Use natural, encouraging language:  
            - "Let's break that down step by step…"  
            - "Imagine it like this…"  
            - "Don't worry if it feels tricky at first…"  
        - Avoid robot‑like or overly terse phrasing; speak like a real mentor.  

        6. ▶ Inference & Quality Settings  
        - Use **zero‑shot** direct answers only for greetings or trivial queries.  
        - Maintain a **low temperature (≤ 0.2)** and **deterministic decoding** for consistency.  
        - Disable summarization heuristics that truncate insights.  
        - Never hallucinate—ground responses in retrieved content or clearly flagged general knowledge.  
        
 """),
    )

    LLM_agent = Agent(
        name="general_knowledge_llm_agent",
        role="Answer general knowledge questions using only your pre-trained knowledge",
        model=MODEL,
        reasoning=True,
        session_id=storage_session_id,
        user_id=user_id,
        #add state
        session_state={"user_id":user_id, "session_id":session_id},
        add_state_in_messages=True,
        markdown=True,
        read_chat_history=True,
        add_history_to_messages=True,
        num_history_responses=5,
        monitoring=True,
        show_tool_calls=True,
        storage = PostgresStorage(table_name="agent_session", db_url=DB_URL),
        memory=memory_llm,  # Add memory instance here
        enable_user_memories=True,
        enable_session_summaries=True,
         instructions=[
        "You answer general knowledge questions (e.g., science, history, culture) using only your internalized training data .",
        "Avoid external tools, databases, or real-time data retrieval; rely exclusively on your LLM's pre-existing knowledge .",
        "For ambiguous or uncertain queries, explicitly state limitations and avoid speculative answers .",
        "Structure responses with clear reasoning steps to demonstrate agentic thinking .",
        "Defer education-specific questions (e.g., pedagogy, curriculum) to the Teacher Agent ."
        ],
    )

    multi_agent_team = Team(
        name="Multi Language Team",
        mode="route",
        model=MODEL,
        share_member_interactions=True, # Share interactions
        user_id=user_id,
        session_id=storage_session_id,
        enable_session_summaries=True,
        #add state
        session_state={"user_id":user_id, "session_id":session_id},
        add_state_in_messages=True,
        memory=memory_team,
        enable_team_history=True,
        num_of_interactions_from_history=5,
        members=[
            LLM_agent,
            teacher_agent
        ],
        show_tool_calls=True,
        markdown=True,
        storage = PostgresStorage(table_name="agent_session", db_url=DB_URL),
        instructions=[
           "You are an education-general knowledge router that directs queries to the appropriate agent.",
        "Always memorize and recall important user facts (such as names, preferences, and previous answers) using your memory system.",
        "If the user shares personal information (e.g., their name), store it and use it to personalize future responses.",
        "When routing, pass relevant user context and memories to the appropriate agent.",
        "If the user's query relates to teaching strategies, curriculum design, classroom management, or subject-specific pedagogy, route to teacher-agent-rag.",
        "If the query is unrelated to education (e.g., science facts, historical events, general advice), route to general-knowledge-llm-agent.",
        "For ambiguous or hybrid queries, prioritize teacher-agent-rag if education relevance is possible, then fall back to general-knowledge-llm-agent.",
        "For unsupported topics outside both agents' scope, respond in English with: 'I can assist with education-related questions or general knowledge topics. Please clarify or rephrase your query!'",
        "Always analyze the intent and context before routing, leveraging Agno's multimodal reasoning capabilities for accurate task delegation.",
        "Always use chat history and user memory to provide contextually relevant and personalized responses.",
        ],
        show_members_responses=True,
    )

    try:
        response = await multi_agent_team.arun(query)

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

    except Exception as e:
        logging.error(f"Error in RAG agent: {type(e).__name__}: {str(e)}")
        import traceback
        logging.error(f"Full traceback: {traceback.format_exc()}")
        raise RuntimeError(f"An error occurred while generating a response: {e}")
