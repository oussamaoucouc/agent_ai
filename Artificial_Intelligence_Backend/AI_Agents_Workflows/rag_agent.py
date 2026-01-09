"""
RAG Agent functionality using AGNO framework.
Enhanced with Docling for superior PDF/DOCX/PPTX/Image parsing.
"""
from pathlib import Path
import tempfile
from textwrap import dedent
import os
import logging
import asyncio
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
from agno.knowledge.document import DocumentKnowledgeBase
from agno.document.base import Document
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

# Try to import Docling reader - graceful fallback if not installed
try:
    from .docling_reader import DoclingReader, get_docling_reader
    HAS_DOCLING = True
    logging.info("Docling reader available - enhanced document parsing enabled")
except ImportError:
    HAS_DOCLING = False
    logging.info("Docling not installed - using AGNO's default readers")

# Import custom CSV row reader for better tabular data handling
from .csv_reader import get_csv_row_reader

from .output_utils import clean_agent_output
from .ollama_queue import local_llm_rate_limit

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

async def initialize_knowledge_base(user_id: str, only_path: str | None = None, only_kind: str | None = None):
    """
    Initialize the per-user knowledge base and let AGNO/PgVector manage persistence.
    Uses Docling for PDF/DOCX/PPTX/Image parsing when available, falls back to AGNO otherwise.
    """
    user_pdf_dir = cfg.get_user_pdf_dir(user_id)
    user_docx_dir = cfg.get_user_docx_dir(user_id)
    user_text_dir = cfg.get_user_text_dir(user_id)
    user_csv_dir = cfg.get_user_csv_dir(user_id)
    user_pptx_dir = cfg.get_user_pptx_dir(user_id)
    user_images_dir = cfg.get_user_images_dir(user_id)

    logging.info("Initializing knowledge base")
    logging.info(f"Using Ollama URL for embedder: {cfg.OLLAMA_BASE_URL}")
    logging.info(f"OpenAI-compatible base URL (embeddings): {cfg.get_openai_base_url()}")
    logging.info(f"Docling enabled: {HAS_DOCLING}")


    embedder = OllamaEmbedder(
            id="bge-m3_ctx",
            dimensions=1024,
            host=cfg.OLLAMA_BASE_URL
        )
    def _uid_suffix(uid: str) -> str:
        import hashlib
        dig = hashlib.sha1(str(uid).encode("utf-8")).hexdigest()[:12]
        return f"u_{dig}"
    def _tbl(base: str) -> str:
        return f"{base}_{_uid_suffix(user_id)}"

    # Vector DBs for each document type
    docling_vector_db = PgVector(
        table_name=_tbl("docling_documents"),
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
    logging.info("Initialized PgVector user-scoped tables for docling, text, csv, combined")

    # Helper function to get existing file hashes from the database
    # NOTE: AGNO's CombinedKnowledgeBase stores all documents in the combined table
    combined_table_name = _tbl("combined_documents")
    _cached_indexed_hashes = None  # Cache to avoid repeated queries
    
    def _get_indexed_hashes() -> set:
        """Query the combined vector DB table to get already-indexed file SHA256 hashes."""
        nonlocal _cached_indexed_hashes
        if _cached_indexed_hashes is not None:
            return _cached_indexed_hashes
            
        from sqlalchemy import create_engine, text
        try:
            engine = create_engine(cfg.VECTOR_DB_URL)
            with engine.connect() as conn:
                # Query existing file hashes from the combined_documents table
                result = conn.execute(text(f"""
                    SELECT DISTINCT meta_data->>'file_sha256' as hash
                    FROM rag."{combined_table_name}"
                    WHERE meta_data->>'file_sha256' IS NOT NULL
                """))
                hashes = {row[0] for row in result if row[0]}
                logging.info(f"Found {len(hashes)} already-indexed file hashes in {combined_table_name}")
                _cached_indexed_hashes = hashes
                return hashes
        except Exception as e:
            logging.warning(f"Could not query existing hashes from {combined_table_name}: {e}")
            return set()

    logging.info(f"Using user-specific directories: pdf={user_pdf_dir}, docx={user_docx_dir}, pptx={user_pptx_dir}, images={user_images_dir}, text={user_text_dir}, csv={user_csv_dir}")
    
    # Gather all file paths
    try:
        pdf_files = list(Path(user_pdf_dir).glob("*.pdf"))
    except Exception:
        pdf_files = []
    try:
        docx_files = list(Path(user_docx_dir).glob("*.docx")) + list(Path(user_docx_dir).glob("*.doc"))
    except Exception:
        docx_files = []
    try:
        pptx_files = list(Path(user_pptx_dir).glob("*.pptx")) + list(Path(user_pptx_dir).glob("*.ppt"))
    except Exception:
        pptx_files = []
    try:
        image_files = (
            list(Path(user_images_dir).glob("*.png")) +
            list(Path(user_images_dir).glob("*.jpg")) +
            list(Path(user_images_dir).glob("*.jpeg")) +
            list(Path(user_images_dir).glob("*.tiff")) +
            list(Path(user_images_dir).glob("*.tif")) +
            list(Path(user_images_dir).glob("*.bmp")) +
            list(Path(user_images_dir).glob("*.gif"))
        )
    except Exception:
        image_files = []
    try:
        text_files = list(Path(user_text_dir).glob("*.txt")) + list(Path(user_text_dir).glob("*.md"))
    except Exception:
        text_files = []
    try:
        csv_files = list(Path(user_csv_dir).glob("*.csv"))
    except Exception:
        csv_files = []

    # Handle single-file processing mode
    if only_path and only_kind:
        p = Path(only_path)
        kind = only_kind.lower()
        pdf_files = [p] if kind == "pdf" and p.suffix.lower() == ".pdf" else []
        docx_files = [p] if kind == "docx" and p.suffix.lower() in {".doc", ".docx"} else []
        pptx_files = [p] if kind == "pptx" and p.suffix.lower() in {".ppt", ".pptx"} else []
        image_files = [p] if kind == "images" and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".gif"} else []
        text_files = [p] if kind == "text" and p.suffix.lower() in {".txt", ".md"} else []
        csv_files = [p] if kind == "csv" and p.suffix.lower() == ".csv" else []

    def _sha256(path: Path) -> str:
        import hashlib
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    knowledge_sources = []
    
    # --- Docling-handled documents (PDF, DOCX, PPTX, Images) ---
    docling_files = pdf_files + docx_files + pptx_files + image_files
    
    if docling_files and HAS_DOCLING:
        # Get already-indexed hashes to skip re-processing (from combined table)
        indexed_hashes = _get_indexed_hashes()
        
        # Filter out already-indexed files
        files_to_process = []
        for file_path in docling_files:
            file_sha = _sha256(file_path)
            if file_sha in indexed_hashes:
                logging.info(f"⏭️ Skipping already-indexed: {file_path.name}")
            else:
                files_to_process.append((file_path, file_sha))
        
        if files_to_process:
            logging.info(f"📄 Processing {len(files_to_process)} new files with Docling (skipped {len(docling_files) - len(files_to_process)} already-indexed)")
            
            # Use Docling for enhanced parsing
            docling_reader = get_docling_reader(enable_vlm=False, fallback_to_agno=True)
            if docling_reader:
                docling_documents = []
                for file_path, file_sha in files_to_process:
                    try:
                        file_type = file_path.suffix.lower().lstrip('.')
                        chunks = docling_reader.read(
                            str(file_path), 
                            user_id=user_id,
                            file_sha256=file_sha
                        )
                        for chunk in chunks:
                            meta = chunk.get("metadata", {})
                            meta["user_id"] = str(user_id)
                            meta["type"] = file_type
                            meta["file_sha256"] = file_sha
                            
                            doc = Document(
                                content=chunk["content"],
                                name=file_path.name,
                                meta_data=meta
                            )
                            docling_documents.append(doc)
                    except Exception as e:
                        logging.warning(f"Docling failed to process {file_path.name}: {e}, falling back to AGNO")
                        # Fallback handled below
                
            if docling_documents:
                docling_kb = DocumentKnowledgeBase(
                    documents=docling_documents,
                    vector_db=docling_vector_db,
                    num_documents=5
                )
                knowledge_sources.append(docling_kb)
                logging.info(f"Docling processed {len(docling_documents)} chunks from {len(docling_files)} files")
    
    # Fallback to AGNO readers if Docling not available or failed
    if not HAS_DOCLING and docling_files:
        logging.info("Using AGNO fallback readers for PDF/DOCX")
        # Legacy AGNO handling for PDF
        if pdf_files:
            pdf_vector_db = PgVector(
                table_name=_tbl("pdf_documents"),
                db_url=cfg.VECTOR_DB_URL,
                embedder=embedder,
                search_type=SearchType.hybrid,
                schema="rag"
            )
            pdf_kb = PDFKnowledgeBase(
                path=[{"path": str(p), "metadata": {"user_id": str(user_id), "type": "pdf", "file_sha256": _sha256(p)}} for p in pdf_files],
                vector_db=pdf_vector_db,
                chunking_strategy=AgenticChunking(),
                num_documents=5
            )
            knowledge_sources.append(pdf_kb)
        
        # Legacy AGNO handling for DOCX
        if docx_files:
            docx_vector_db = PgVector(
                table_name=_tbl("docx_documents"),
                db_url=cfg.VECTOR_DB_URL,
                embedder=embedder,
                search_type=SearchType.hybrid,
                schema="rag"
            )
            docx_kb = DocxKnowledgeBase(
                path=[{"path": str(p), "metadata": {"user_id": str(user_id), "type": "docx", "file_sha256": _sha256(p)}} for p in docx_files],
                vector_db=docx_vector_db,
                formats=[".doc", ".docx"],
                num_documents=5
            )
            knowledge_sources.append(docx_kb)
    
    # --- AGNO-handled documents (Text) with skip optimization ---
    if text_files:
        # Get already-indexed hashes (cached from combined table)
        text_indexed_hashes = _get_indexed_hashes()
        
        # Filter out already-indexed text files
        text_to_process = []
        for text_path in text_files:
            file_hash = _sha256(text_path)
            if file_hash in text_indexed_hashes:
                logging.info(f"⏭️ Skipping already-indexed text: {text_path.name}")
            else:
                text_to_process.append(text_path)
        
        if text_to_process:
            logging.info(f"📝 Processing {len(text_to_process)} new text files (skipped {len(text_files) - len(text_to_process)} already-indexed)")
            text_kb = TextKnowledgeBase(
                path=[{"path": str(p), "metadata": {"user_id": str(user_id), "type": "text", "file_sha256": _sha256(p)}} for p in text_to_process],
                vector_db=text_vector_db,
                formats=[".txt", ".md"],
                num_documents=5
            )
            knowledge_sources.append(text_kb)
    
    # --- Custom CSV row-based processing for better retrieval accuracy ---
    if csv_files:
        # Get already-indexed hashes (cached from combined table)
        csv_indexed_hashes = _get_indexed_hashes()
        
        # Filter out already-indexed CSV files
        csv_to_process = []
        for csv_path in csv_files:
            file_hash = _sha256(csv_path)
            if file_hash in csv_indexed_hashes:
                logging.info(f"⏭️ Skipping already-indexed CSV: {csv_path.name}")
            else:
                csv_to_process.append((csv_path, file_hash))
        
        if csv_to_process:
            logging.info(f"📊 Processing {len(csv_to_process)} new CSV files (skipped {len(csv_files) - len(csv_to_process)} already-indexed)")
            csv_reader = get_csv_row_reader(max_rows_per_chunk=1)  # 1 row per chunk for precise lookup
            csv_documents = []
            for csv_path, file_hash in csv_to_process:
                rows = csv_reader.read(csv_path, user_id=user_id, file_sha256=file_hash)
                for row in rows:
                    csv_documents.append(Document(
                        name=row["metadata"].get("filename", str(csv_path.name)),
                        id=f"{file_hash}_{row['metadata'].get('row_numbers', [0])[0]}",
                        content=row["content"],
                        meta_data=row["metadata"]
                    ))
            
            if csv_documents:
                csv_kb = DocumentKnowledgeBase(
                    documents=csv_documents,
                    vector_db=csv_vector_db,
                    num_documents=10  # Retrieve more rows for CSV since each row is small
                )
                knowledge_sources.append(csv_kb)
                logging.info(f"CSV row-chunking: processed {len(csv_documents)} row-chunks from {len(csv_to_process)} files")

    # Combine all knowledge sources
    knowledge_base = CombinedKnowledgeBase(
        sources=knowledge_sources,
        vector_db=combined_vector_db,
        num_documents=6
    )

    # Log basic ingestion diagnostics
    try:
        logging.info(f"Knowledge ingestion: pdf={len(pdf_files)} docx={len(docx_files)} pptx={len(pptx_files)} images={len(image_files)} text={len(text_files)} csv={len(csv_files)} for user {user_id}")
    except Exception as e:
        logging.warning(f"Unable to list files in user directories: {e}")

    # Do not load here; callers will decide recreate/upsert based on context
    logging.info("Knowledge base object created; loading deferred to caller")
    return knowledge_base


async def run_rag_agent_async(query, user_id, session_id, images=None, audio=None, videos=None, stream=False):
    """
    AGNO RAG agent using ChromaDB and nomic embedder.
    Initializes a fresh knowledge base sync on each query.
    
    Args:
        query: Text query
        user_id: User ID
        session_id: Session ID
        stream: If True, returns an async generator yielding content chunks
    """
    logging.info(f"Starting RAG agent with Ollama at: {cfg.OLLAMA_BASE_URL}")
    logging.info(f"OpenAI-compatible base URL: {cfg.get_openai_base_url()}")
    
    knowledge_base = await initialize_knowledge_base(user_id)
    lock = get_user_kb_lock(user_id)
    async with lock:
        try:
            await knowledge_base.aload(recreate=False, upsert=False)
        except Exception as e:
            m = str(e).lower()
            if "does not exist" in m or "relation" in m or "not found" in m:
                await knowledge_base.aload(recreate=True, upsert=False)
    #memory_rag = await initialize_memory_dbs(user_id, session_id)
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
        # Note: User isolation already handled by per-user table names (_uid_suffix)
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
        
        8. ▶ Response Formatting for Optimal Readability
        - Structure responses in SHORT paragraphs (2-3 sentences maximum)
        - Add blank lines between different topics or concepts
        - Use numbered lists for multi-step information (ALWAYS on separate lines)
        - Put source citations and references in clearly separated sections
        - Give important information (IDs, URLs, specific data) breathing room
        - Example GOOD format:
          ```
          Based on the retrieved documents, here's what I found:
          
          **Key Points:**
          
          1. First important finding
          2. Second important finding
          3. Third important finding
          
          **Source Information:**
          
          📄 From document: "filename.pdf"
          ```
        - Example BAD format: "Based on documents here's what I found:1. Finding2. Finding3. FindingFrom document filename.pdf"
        
        9. ▶ Data Privacy & Compliance (CRITICAL)
        - NEVER expose internal system metadata to users, including:
          • User IDs, session IDs, or any internal identifiers
          • File paths (e.g., /app/data/pdfs/..., C:\\Users\\..., etc.)
          • SHA256 hashes, chunk indices, or embedding details
          • Database table names, schema names, or internal configuration
          • Source file absolute paths or system directory structures
        - When citing sources, use ONLY the document filename (e.g., "According to Commercial_Proposal.pdf...")
        - If document metadata contains paths, user_id, file_sha256, or similar internal fields, DO NOT include them in your response
        - Treat all internal metadata as confidential application data
        - Focus responses on the CONTENT of documents, not their storage or processing details
        
 """)
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
                        run_response = await rag_expert_agent.arun(query, stream=True, stream_intermediate_steps=False)
                        async for chunk in run_response:
                            # In v1.8, just access chunk.content directly
                            if hasattr(chunk, 'content') and chunk.content:
                                # Clean each chunk for consistency (matching Assistant agent)
                                cleaned_chunk = clean_agent_output(chunk.content, agent_type="rag")
                                if cleaned_chunk:  # Only yield non-empty chunks
                                    yield cleaned_chunk
                    except asyncio.CancelledError:
                        # User cancelled - re-raise to ensure httpx closes the connection
                        # This tells Ollama to stop THIS specific generation (not others)
                        logging.info("RAG streaming cancelled by user - closing connection to abort Ollama")
                        raise
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

                # Use shared output cleaning for consistency
                formatted_content = clean_agent_output(result_content, agent_type="rag")
                return formatted_content


    except Exception as e:
        logging.error(f"Error in RAG agent: {type(e).__name__}: {str(e)}")
        import traceback
        logging.error(f"Full traceback: {traceback.format_exc()}")
        raise RuntimeError(f"An error occurred while generating a response: {e}")
