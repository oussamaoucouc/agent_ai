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
from agno.agent import Agent
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
from .config import DB_URL, DATA_DIR, get_current_model, OLLAMA_BASE_URL, get_user_pdf_dir

import logging
logging.basicConfig(level=logging.INFO)

# Set up cache directory
CACHE_DIR = os.path.abspath("./cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def _compute_dir_state(dir_path: str):
    """Return a dict of filename -> {size, mtime} for PDFs in a directory."""
    state = {}
    for p in Path(dir_path).glob("*.pdf"):
        try:
            stat = p.stat()
            state[p.name] = {"size": stat.st_size, "mtime": int(stat.st_mtime)}
        except Exception:
            # Skip unreadable files
            continue
    return state


async def sync_knowledge_with_pdf_directory(knowledge_base, user_pdf_dir, force_refresh=False):
    """
    Sync knowledge base with current PDF directory state.
    Rebuilds the vector store from the current PDF directory to ensure
    deletions and updates are reflected reliably.
    
    Args:
        knowledge_base: The knowledge base to sync
        user_pdf_dir: Directory containing PDF files
        force_refresh: If True, forces a complete refresh regardless of cache state
    """
    try:
        # Compute current directory state
        current_state = _compute_dir_state(user_pdf_dir)
        current_files = set(current_state.keys())
        logging.info(f"KB sync: {len(current_files)} PDFs detected in {user_pdf_dir}")

        # Load previous state (per-directory cache key)
        # Ensure path is serialized as string for hashing (handles WindowsPath)
        cache_key = hashlib.sha1(str(user_pdf_dir).encode("utf-8")).hexdigest()
        cache_file = os.path.join(CACHE_DIR, f"kb_state_{cache_key}.json")
        prev_state = {}
        if os.path.isfile(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    prev_state = json.load(f)
            except Exception:
                prev_state = {}
        prev_files = set(prev_state.keys())

        # Detect changes
        added = current_files - prev_files
        deleted = prev_files - current_files
        modified = set(
            name for name in (current_files & prev_files)
            if prev_state.get(name) != current_state.get(name)
        )

        # Force refresh if requested or if any changes detected
        if force_refresh:
            logging.info("KB sync: force refresh requested; rebuilding collection")
            await knowledge_base.aload(recreate=True, upsert=False)
        elif not prev_state:
            logging.info("KB sync: no previous state found; performing initial load")
            await knowledge_base.aload(recreate=True, upsert=False)
        elif deleted or modified or added:
            # Always rebuild when ANY changes are detected to ensure consistency
            logging.info(
                f"KB sync: changes detected (added={len(added)}, deleted={len(deleted)}, modified={len(modified)}); rebuilding collection"
            )
            await knowledge_base.aload(recreate=True, upsert=False)
        else:
            # Even when no changes detected, do a light refresh to catch any missed updates
            logging.info("KB sync: no file changes detected; performing light refresh")
            await knowledge_base.aload(recreate=False, upsert=True)

        # Persist current state
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(current_state, f)
        except Exception:
            logging.warning("KB sync: failed to write state cache; continuing")

    except Exception as e:
        logging.error(f"Error syncing knowledge base: {e}")
        raise


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

async def initialize_knowledge_base(user_id: str):
    """
    Initialize the knowledge base with vector database.
    No custom caching is used; we rely on AGNO's internals and a fresh
    sync on each invocation to ensure newly added documents are available.
    """
    logging.info("Initializing knowledge base")
    logging.info(f"Using Ollama URL for embedder: {OLLAMA_BASE_URL}")
    
    # Create OllamaEmbedder with the correct host parameter
    embedder = OllamaEmbedder(
        id="nomic-embed-text",
        dimensions=768,
        host=OLLAMA_BASE_URL  # FIXED: Add host parameter
    )
    
    # Per-user ChromaDB collection and directory for isolation
    user_chroma_path = os.path.join("./tmp/chromadb_nomicembedtext", str(user_id))
    os.makedirs(user_chroma_path, exist_ok=True)
    vector_db = ChromaDb(
        collection=f"ragdocs{user_id}",
        path=user_chroma_path,
        persistent_client=True,
        embedder=embedder
    )
    logging.info(f"Initialized ChromaDB: collection=teacher_{user_id}, path={user_chroma_path}")

    # Use per-user PDF directory
    user_pdf_dir = get_user_pdf_dir(user_id)
    logging.info(f"Using user-specific PDF directory: {user_pdf_dir}")
    knowledge_base = PDFKnowledgeBase(
        path=user_pdf_dir,
        vector_db=vector_db,
        chunking_strategy=DocumentChunking()
    )
    
    # Log basic ingestion diagnostics: PDF count
    try:
        pdf_files = list(Path(user_pdf_dir).glob("*.pdf"))
        logging.info(f"Knowledge ingestion: found {len(pdf_files)} PDFs for user {user_id}")
        if len(pdf_files) == 0:
            logging.warning(f"No PDFs found in {user_pdf_dir} for user {user_id}. Retrieval may return no documents.")
    except Exception as e:
        logging.warning(f"Unable to list PDFs in {user_pdf_dir}: {e}")

    # Always force a fresh sync to ensure new documents are indexed
    await sync_knowledge_with_pdf_directory(knowledge_base, user_pdf_dir, force_refresh=True)
    
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

    return memory_rag

async def run_rag_agent_async(query, user_id, session_id):
    """
    AGNO RAG agent using ChromaDB and openhermes embedder.
    Initializes a fresh knowledge base sync on each query.
    """
    logging.info(f"Starting RAG agent with Ollama at: {OLLAMA_BASE_URL}")
    
    # Initialize knowledge base (no custom cache) and memory DBs
    knowledge_base = await initialize_knowledge_base(user_id)
    memory_rag = await initialize_memory_dbs(user_id, session_id)
    storage_session_id = f"{user_id}_{session_id}"  # For PostgresStorage isolation

    # Memory DBs already initialized via the cached function
    
    #knowledge tools reasoning, search, analyze, few shot, instructions
    knowledge_tools = KnowledgeTools(
    knowledge=knowledge_base,
    think=False,
    search=True,
    analyze=True,
    add_few_shot=False,
    add_instructions=False,
    )

    rag_expert_agent = Agent(
        model=get_current_model(),
        reasoning=False,
        name="rag_expert_agent",
        session_id=session_id,
        session_state={"user_id":user_id, "session_id":session_id},
        add_state_in_messages=True,
        role="AI Expert in Retrieval-Augmented Generation (RAG) systems that provides comprehensive, accurate, and contextually relevant responses by leveraging advanced document retrieval and knowledge synthesis techniques",
        user_id=user_id,
        description=dedent(f"""\
            You are an AI RAG Expert, optimized for maximum retrieval accuracy, semantic understanding, and knowledge synthesis. 
            Your expertise lies in intelligently retrieving, analyzing, and synthesizing information from knowledge bases to provide comprehensive, accurate, and contextually relevant responses.
            """),
        tools=[knowledge_tools],
        knowledge=knowledge_base,
        #search_knowledge=True, #we alreadu have repetition and avoid confusion for the agent
        markdown=True,
        read_chat_history=True,
        add_history_to_messages=True,
        num_history_responses=2,
        monitoring=True,
        show_tool_calls=True,
        storage = PostgresStorage(table_name="agent_session", db_url=DB_URL),
        memory=memory_rag,  # Add memory instance here
        enable_user_memories=True,
        enable_session_summaries=True,
        instructions=dedent("""\
        You are an AI RAG Expert. Follow these advanced retrieval and synthesis protocols for optimal performance:

        1. ▶ Intelligent Query Analysis & Retrieval Strategy
        - Analyze query complexity, domain specificity, and information requirements before deciding on retrieval strategy
        - For simple factual queries with high confidence: Provide direct answers from built-in knowledge
        - For complex, domain-specific, or multi-faceted queries: Always invoke retrieval to ensure accuracy and completeness
        - Use semantic understanding to identify key concepts, entities, and relationships in the query
        - Formulate multiple retrieval angles when dealing with complex queries to capture comprehensive information

        2. ▶ Advanced Document Retrieval & Ranking
        - Leverage semantic similarity and contextual relevance for document selection
        - Prioritize documents with high semantic overlap and factual density
        - Cross-reference multiple sources when available to validate information consistency
        - Identify and utilize the most authoritative and recent sources in the knowledge base
        - Apply relevance thresholds to filter out low-quality or tangentially related content

        3. ▶ Knowledge Synthesis & Response Construction
        - Synthesize information from multiple retrieved documents into coherent, comprehensive responses
        - Maintain factual accuracy while creating natural, flowing explanations
        - Structure responses hierarchically: overview → detailed explanation → specific examples/applications
        - Integrate retrieved facts seamlessly without obvious source boundaries
        - Provide context and background information to enhance understanding
        - Use evidence-based reasoning to connect concepts and draw insights

        4. ▶ Quality Assurance & Accuracy Protocols
        - Always ground responses in retrieved content when available
        - Clearly distinguish between retrieved information and general knowledge
        - If retrieval yields insufficient or conflicting information, state: "Based on the available documents in the knowledge base, [provide what you found], however, this may not be comprehensive."
        - Never fabricate or hallucinate information not present in retrieved documents
        - Maintain consistency across related queries within the same session

        5. ▶ Response Optimization & Clarity
        - Structure responses for maximum comprehension and actionability
        - Use clear, professional language appropriate for the query's complexity level
        - Provide specific examples, case studies, or applications when relevant
        - Include relevant details, methodologies, or step-by-step processes when applicable
        - Ensure responses are complete and self-contained

        6. ▶ Performance & Efficiency Guidelines
        - Optimize retrieval queries for maximum relevant document recall
        - Balance comprehensiveness with response conciseness
        - Prioritize the most critical information first
        - Use structured formatting (lists, sections) when it enhances clarity
        - Maintain low latency while ensuring thorough information processing
        
 """),
    )

    try:

        response = await rag_expert_agent.arun(query)
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

        return result_content

    except Exception as e:
        logging.error(f"Error in RAG agent: {type(e).__name__}: {str(e)}")
        import traceback
        logging.error(f"Full traceback: {traceback.format_exc()}")
        raise RuntimeError(f"An error occurred while generating a response: {e}")