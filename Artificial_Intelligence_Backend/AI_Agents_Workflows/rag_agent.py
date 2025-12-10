"""
RAG Agent functionality using AGNO framework.
"""
from pathlib import Path
import tempfile
from textwrap import dedent
import os
import logging
import pickle
from agno.agent import Agent
from agno.embedder.ollama import OllamaEmbedder
try:
    from agno.embedder.openai import OpenAIEmbedder
    HAS_OPENAI_EMBEDDER = True
except Exception:
    HAS_OPENAI_EMBEDDER = False
from agno.knowledge.pdf import PDFKnowledgeBase, PDFReader
from agno.knowledge.docx import DocxKnowledgeBase
from agno.knowledge.text import TextKnowledgeBase
from agno.knowledge.csv import CSVKnowledgeBase
from agno.knowledge.combined import CombinedKnowledgeBase
from agno.vectordb.pgvector import PgVector, SearchType
from agno.models.groq import Groq
from agno.models.ollama import Ollama
from agno.models.openai import OpenAIChat
from agno.storage.postgres import PostgresStorage
from agno.document.chunking.document import DocumentChunking
from agno.document.chunking.agentic import AgenticChunking
from agno.tools.reasoning import ReasoningTools
from agno.tools.thinking import ThinkingTools
from agno.tools.knowledge import KnowledgeTools
from agno.storage.sqlite import SqliteStorage
from . import config as cfg
from . import model_factory
from .locks import get_user_kb_lock
import re

import logging
logging.basicConfig(level=logging.INFO)


def format_rag_output(content: str) -> str:
    """
    Format RAG output to be more user-friendly.
    Cleans up markdown formatting and makes content more readable.
    """
    if not content:
        return content
    
    # Remove excessive markdown headers (#### to ##)
    content = re.sub(r'^####\s+(.+)$', r'**\1**', content, flags=re.MULTILINE)
    content = re.sub(r'^###\s+(.+)$', r'**\1**', content, flags=re.MULTILINE)
    
    # Clean up "Source & Context" section to be more natural
    content = re.sub(r'\*\*Source & Context\*\*', '\n📄 **Source Information:**', content)
    content = re.sub(r'From the\s+', '\n📌 ', content)
    
    # Clean up "Key Additional Notes" section
    content = re.sub(r'\*\*Key Additional Notes\*\*', '\n📝 **Additional Notes:**', content)
    
    # Add emoji bullets for better readability
    content = re.sub(r'^-\s+', '  • ', content, flags=re.MULTILINE)
    
    # Clean up "Taxes:", "Validity:", "Assumptions:" to be more readable
    content = re.sub(r'\*\*Taxes:\*\*', '\n💰 **Taxes:**', content)
    content = re.sub(r'\*\*Validity:\*\*', '\n📅 **Validity:**', content)
    content = re.sub(r'\*\*Assumptions:\*\*', '\n📋 **Assumptions:**', content)
    
    # Format currency amounts nicely
    content = re.sub(r'\$(\d+)\s+USD', r'💵 $\1 USD', content)
    
    # Add spacing around sections for better readability
    content = re.sub(r'\n\n+', '\n\n', content)
    
    return content.strip()

# Removed custom KB cache directory; rely on AGNO/Chroma persistence.


# Removed custom directory state sync; AGNO's knowledge base handles loading/upserts.


def run_rag_agent(query, user_id, session_id, images=None, audio=None, videos=None, stream=False):
    """
    Entry point for RAG agent that works in both synchronous and asynchronous contexts.
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
        # We're already in an event loop, so we need to return a coroutine
        # that the caller can await
        logging.info("Running in existing event loop")
        return run_rag_agent_async(query, user_id, session_id, images, audio, videos, stream)
    else:
        # No event loop running, so create a new one
        logging.info("Creating new event loop")
        return asyncio.run(run_rag_agent_async(query, user_id, session_id, images, audio, videos, stream))

async def initialize_knowledge_base(user_id: str, force_recreate: bool = False):
    """
    Initialize the per-user knowledge base using MinIO-stored documents.
    Downloads documents from MinIO to temp files, embeds them, and stores in PgVector.
    
    This is called:
    - In background after document upload (force_recreate=False) - upserts new docs
    - In background after document delete (force_recreate=True) - rebuilds from scratch
    - As fallback if vector table doesn't exist during query (force_recreate=True)
    
    Args:
        user_id: User ID to initialize knowledge base for
        force_recreate: If True, recreates vector DB from scratch (for delete operations)
        
    Returns:
        CombinedKnowledgeBase: Knowledge base with embeddings loaded
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    from users import DocumentMetadata, SessionLocal as UserSessionLocal
    import minio_storage
    
    action = "Recreating" if force_recreate else "Initializing"
    logging.info(f"{action} knowledge base from MinIO for user {user_id}")
    logging.info(f"Using Ollama URL for embedder: {cfg.OLLAMA_BASE_URL}")

    embedder = OllamaEmbedder(
        id="nomic-embed-text",
        dimensions=768,
        host=cfg.OLLAMA_BASE_URL
    )
    
    def _uid_suffix(uid: str) -> str:
        import hashlib
        dig = hashlib.sha1(str(uid).encode("utf-8")).hexdigest()[:12]
        return f"u_{dig}"
    
    def _tbl(base: str) -> str:
        return f"{base}_{_uid_suffix(user_id)}"

    # Initialize vector databases
    pdf_vector_db = PgVector(
        table_name=_tbl("pdf_documents"),
        db_url=cfg.VECTOR_DB_URL,
        embedder=embedder,
        search_type=SearchType.hybrid,
        schema="rag"
    )
    docx_vector_db = PgVector(
        table_name=_tbl("docx_documents"),
        db_url=cfg.VECTOR_DB_URL,
        embedder=embedder,
        search_type=SearchType.hybrid,
        schema="rag"
    )
    text_vector_db = PgVector(
        table_name=_tbl("text_documents"),
        db_url=cfg.VECTOR_DB_URL,
        embedder=embedder,
        search_type=SearchType.hybrid,
        schema="rag"
    )
    csv_vector_db = PgVector(
        table_name=_tbl("csv_documents"),
        db_url=cfg.VECTOR_DB_URL,
        embedder=embedder,
        search_type=SearchType.hybrid,
        schema="rag"
    )
    combined_vector_db = PgVector(
        table_name=_tbl("combined_documents"),
        db_url=cfg.VECTOR_DB_URL,
        embedder=embedder,
        search_type=SearchType.hybrid,
        schema="rag"
    )
    logging.info("Initialized PgVector user-scoped tables")

    # Query ALL documents for this user from database
    with UserSessionLocal() as db:
        docs = db.query(DocumentMetadata).filter(
            DocumentMetadata.user_id == user_id
        ).all()
        logging.info(f"Found {len(docs)} documents for user {user_id}")

    # Download documents from MinIO to temp files
    pdf_files = []
    docx_files = []
    text_files = []
    csv_files = []

    def _sha256_bytes(data: bytes) -> str:
        import hashlib
        return hashlib.sha256(data).hexdigest()

    for doc in docs:
        if not doc.minio_object_key or not doc.minio_bucket_name:
            logging.warning(f"Skipping {doc.filename}: no MinIO metadata")
            continue

        try:
            # Download from MinIO to temp
            temp_path = minio_storage.download_to_temp(
                user_id, doc.filename, doc.file_type
            )
            
            # Calculate hash for metadata
            with open(temp_path, "rb") as f:
                file_data = f.read()
            file_hash = _sha256_bytes(file_data)
            
            path_obj = Path(temp_path)
            metadata = {
                "user_id": str(user_id),
                "type": doc.file_type,
                "file_sha256": file_hash
            }
            
            # Categorize by type
            if doc.file_type == "pdf":
                pdf_files.append({"path": str(path_obj), "metadata": metadata})
            elif doc.file_type == "docx":
                docx_files.append({"path": str(path_obj), "metadata": metadata})
            elif doc.file_type == "text":
                text_files.append({"path": str(path_obj), "metadata": metadata})
            elif doc.file_type == "csv":
                csv_files.append({"path": str(path_obj), "metadata": metadata})
                
        except Exception as e:
            logging.error(f"Error downloading {doc.filename} from MinIO: {e}")
            continue

    # Create knowledge bases
    pdf_kb = PDFKnowledgeBase(
        path=pdf_files,
        vector_db=pdf_vector_db,
        chunking_strategy=AgenticChunking(),
        num_documents=5
    )
    docx_kb = DocxKnowledgeBase(
        path=docx_files,
        vector_db=docx_vector_db,
        formats=[".doc", ".docx"],
        num_documents=5
    )
    text_kb = TextKnowledgeBase(
        path=text_files,
        vector_db=text_vector_db,
        formats=[".txt", ".md"],
        num_documents=5
    )
    csv_kb = CSVKnowledgeBase(
        path=csv_files,
        vector_db=csv_vector_db,
        num_documents=5
    )

    knowledge_base = CombinedKnowledgeBase(
        sources=[pdf_kb, docx_kb, text_kb, csv_kb],
        vector_db=combined_vector_db,
        num_documents=6
    )

    logging.info(f"Knowledge ingestion: pdf={len(pdf_files)} docx={len(docx_files)} text={len(text_files)} csv={len(csv_files)} for user {user_id}")
    logging.info("Knowledge base created from MinIO documents")
    
    # Load knowledge base
    # - Upload: upsert new documents (force_recreate=False)
    # - Delete: recreate from scratch to remove old embeddings (force_recreate=True)
    try:
        if force_recreate:
            logging.info("Recreating knowledge base from scratch...")
            knowledge_base.load(recreate=True, upsert=False)
            logging.info("Knowledge base recreated successfully")
        else:
            logging.info("Loading knowledge base and upserting documents...")
            knowledge_base.load(recreate=False, upsert=True)  # Upsert = add new, skip existing
            logging.info("Knowledge base loaded and embeddings created successfully")
    except Exception as e:
        error_msg = str(e).lower()
        # If table doesn't exist at all, create it
        if "does not exist" in error_msg or "relation" in error_msg:
            logging.warning("Vector table doesn't exist, creating fresh...")
            knowledge_base.load(recreate=True, upsert=False)
            logging.info("Knowledge base created successfully")
        else:
            logging.error(f"Failed to load knowledge base: {e}")
            # Don't fail the upload, KB will lazy-load on first query
    
    # Note: Temp files will be cleaned up by OS temp directory cleanup
    # We cannot delete them immediately as the KB needs them for processing
    
    return knowledge_base


async def run_rag_agent_async(query, user_id, session_id, images=None, audio=None, videos=None, stream=False):
    """
    AGNO RAG agent using PgVector and nomic embedder.
    Uses existing vector DB embeddings (created during upload).
    Properly handles first-time KB creation and subsequent queries.
    
    Args:
        query: Text query
        user_id: User ID
        session_id: Session ID
        stream: If True, returns an async generator yielding content chunks
    """
    logging.info(f"Starting RAG agent with Ollama at: {cfg.OLLAMA_BASE_URL}")
    logging.info(f"OpenAI-compatible base URL: {cfg.get_openai_base_url()}")
    
    # Create KB structure that connects to existing vector DB
    # No file downloading during queries - embeddings created during upload
    embedder = OllamaEmbedder(
        id="nomic-embed-text",
        dimensions=768,
        host=cfg.OLLAMA_BASE_URL
    )
    
    def _uid_suffix(uid: str) -> str:
        import hashlib
        dig = hashlib.sha1(str(uid).encode("utf-8")).hexdigest()[:12]
        return f"u_{dig}"
    def _tbl(base: str) -> str:
        return f"{base}_{_uid_suffix(user_id)}"

    # Create empty KB structures that point to existing vector DBs
    combined_vector_db = PgVector(
        table_name=_tbl("combined_documents"),
        db_url=cfg.VECTOR_DB_URL,
        embedder=embedder,
        search_type=SearchType.hybrid,
        schema="rag"
    )
    
    # Create knowledge base with empty sources - we only need the vector DB for search
    knowledge_base = CombinedKnowledgeBase(
        sources=[],  # Empty - files are in MinIO, embeddings in vector DB
        vector_db=combined_vector_db,
        num_documents=6
    )
    
    # Use lock to prevent concurrent KB operations for same user
    lock = get_user_kb_lock(user_id)
    async with lock:
        try:
            # Try to load existing embeddings (don't recreate, don't upsert)
            await knowledge_base.aload(recreate=False, upsert=False)
            logging.info(f"KB loaded for user {user_id} - using existing embeddings")
        except Exception as e:
            # If vector table doesn't exist yet, initialize it from MinIO
            m = str(e).lower()
            if "does not exist" in m or "relation" in m or "not found" in m:
                logging.warning(f"Vector table doesn't exist for user {user_id}, initializing from MinIO...")
                # This happens on first query if upload background task hasn't completed
                kb_with_files = await initialize_knowledge_base(user_id)
                knowledge_base = kb_with_files
                logging.info(f"KB initialized from MinIO for user {user_id}")
            else:
                # Other error - log and re-raise
                logging.error(f"Error loading KB: {e}")
                raise
    #memory_rag = await initialize_memory_dbs(user_id, session_id)
    storage_session_id = f"{user_id}_{session_id}"  # For PostgresStorage isolation

    # Memory DBs already initialized via the cached function
    
    #knowledge tools reasoning, search, analyze, few shot, instructions
    knowledge_tools = KnowledgeTools(
    knowledge=knowledge_base,
    think=False,
    search=True,
    analyze=False,
    add_few_shot=False,
    add_instructions=False,
    )

    # Resolve per-session model preference
    try:
        import sessions as session_mod
        with session_mod.SessionLocal() as db:
            session_model_id = session_mod.get_session_model_id(db, user_id, session_id)
        logging.info(f"RAG agent model selected: user={user_id}, session={session_id}, model_id={session_model_id}")
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
        logging.warning(f"Falling back to current model due to error resolving session model: {e}")
        session_model = cfg.get_current_model()

    rag_expert_agent = Agent(
        model=session_model,
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
        knowledge_filters={"user_id": str(user_id)},
        #search_knowledge=True,
        markdown=True,
        read_chat_history=True,
        add_history_to_messages=True,
        num_history_responses=3,
        monitoring=True,
        show_tool_calls=True,
        storage = PostgresStorage(table_name="agent_session", db_url=cfg.DB_URL),
        #memory=memory_rag,  # Add memory instance here
        #enable_user_memories=True,
        enable_session_summaries=False,
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
        
        7. ▶ Knowledge Base Priority Over Memory
        - Prefer retrieved knowledge base content over chat history and user/session memory.
        - After a document upload or deletion in the same session, treat prior memory as secondary; only use it if corroborated by retrieved documents.
        - If no relevant documents are retrieved, do not answer from memory about user-uploaded files; reply that no relevant KB documents were found.
        - When memory conflicts with the current knowledge base, resolve in favor of the KB.
        
 """),
    )

    try:
        if stream:
            # Streaming mode: return an async generator that yields content chunks
            async def stream_generator():
                try:
                    # AGNO v1.8: arun with stream=True returns Iterator[RunResponse]
                    # stream_intermediate_steps=False prevents tool execution logs from appearing
                    run_response = await rag_expert_agent.arun(query, stream=True, stream_intermediate_steps=False)
                    async for chunk in run_response:
                        # In v1.8, just access chunk.content directly
                        if hasattr(chunk, 'content') and chunk.content:
                            yield chunk.content
                except Exception as e:
                    logging.error(f"Error in RAG streaming: {type(e).__name__}: {str(e)}")
                    raise
            
            logging.info("INFO Starting streaming RAG agent response for query.")
            return stream_generator()
        else:
            # Non-streaming mode: return complete response
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

            # Format the output to be more user-friendly
            formatted_content = format_rag_output(result_content)
            return formatted_content

    except Exception as e:
        logging.error(f"Error in RAG agent: {type(e).__name__}: {str(e)}")
        import traceback
        logging.error(f"Full traceback: {traceback.format_exc()}")
        raise RuntimeError(f"An error occurred while generating a response: {e}")
