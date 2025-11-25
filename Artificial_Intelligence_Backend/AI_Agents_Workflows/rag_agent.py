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


def run_rag_agent(query, user_id, session_id, images=None, audio=None, videos=None):
    """
    Entry point for RAG agent that works in both synchronous and asynchronous contexts.
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
        # We're already in an event loop, so we need to return a coroutine
        # that the caller can await
        logging.info("Running in existing event loop")
        return run_rag_agent_async(query, user_id, session_id, images, audio, videos)
    else:
        # No event loop running, so create a new one
        logging.info("Creating new event loop")
        return asyncio.run(run_rag_agent_async(query, user_id, session_id, images, audio, videos))

async def initialize_knowledge_base(user_id: str, only_path: str | None = None, only_kind: str | None = None):
    """
    Initialize the per-user knowledge base and let AGNO/Chroma manage persistence.
    """
    user_pdf_dir = cfg.get_user_pdf_dir(user_id)
    user_docx_dir = cfg.get_user_docx_dir(user_id)
    user_text_dir = cfg.get_user_text_dir(user_id)
    user_csv_dir = cfg.get_user_csv_dir(user_id)

    logging.info("Initializing knowledge base")
    logging.info(f"Using Ollama URL for embedder: {cfg.OLLAMA_BASE_URL}")
    logging.info(f"OpenAI-compatible base URL (embeddings): {cfg.get_openai_base_url()}")


    embedder = OllamaEmbedder(
            id="nomic-embed-text",
            dimensions=768,
            host="http://host.docker.internal:11434"
        )
    def _uid_suffix(uid: str) -> str:
        import hashlib
        dig = hashlib.sha1(str(uid).encode("utf-8")).hexdigest()[:12]
        return f"u_{dig}"
    def _tbl(base: str) -> str:
        return f"{base}_{_uid_suffix(user_id)}"

    pdf_vector_db = PgVector(
        table_name=_tbl("pdf_documents"),
        db_url=cfg.VECTOR_DB_URL,
        embedder=embedder,
        search_type=SearchType.hybrid
    )
    docx_vector_db = PgVector(
        table_name=_tbl("docx_documents"),
        db_url=cfg.VECTOR_DB_URL,
        embedder=embedder,
        search_type=SearchType.hybrid
    )
    text_vector_db = PgVector(
        table_name=_tbl("text_documents"),
        db_url=cfg.VECTOR_DB_URL,
        embedder=embedder,
        search_type=SearchType.hybrid
    )
    csv_vector_db = PgVector(
        table_name=_tbl("csv_documents"),
        db_url=cfg.VECTOR_DB_URL,
        embedder=embedder,
        search_type=SearchType.hybrid
    )
    combined_vector_db = PgVector(
        table_name=_tbl("combined_documents"),
        db_url=cfg.VECTOR_DB_URL,
        embedder=embedder,
        search_type=SearchType.hybrid
    )
    logging.info("Initialized PgVector user-scoped tables for pdf, docx, text, csv, combined")

    logging.info(f"Using user-specific directories: pdf={user_pdf_dir}, docx={user_docx_dir}, text={user_text_dir}, csv={user_csv_dir}")
    try:
        pdf_files_for_kb = list(Path(user_pdf_dir).glob("*.pdf"))
    except Exception:
        pdf_files_for_kb = []
    try:
        docx_files_for_kb = list(Path(user_docx_dir).glob("*.docx")) + list(Path(user_docx_dir).glob("*.doc"))
    except Exception:
        docx_files_for_kb = []
    try:
        text_files_for_kb = list(Path(user_text_dir).glob("*.txt")) + list(Path(user_text_dir).glob("*.md"))
    except Exception:
        text_files_for_kb = []
    try:
        csv_files_for_kb = list(Path(user_csv_dir).glob("*.csv"))
    except Exception:
        csv_files_for_kb = []

    if only_path and only_kind:
        p = Path(only_path)
        kind = only_kind.lower()
        pdf_files_for_kb = [p] if kind == "pdf" and p.suffix.lower() == ".pdf" else []
        docx_files_for_kb = [p] if kind == "docx" and p.suffix.lower() in {".doc", ".docx"} else []
        text_files_for_kb = [p] if kind == "text" and p.suffix.lower() in {".txt", ".md"} else []
        csv_files_for_kb = [p] if kind == "csv" and p.suffix.lower() == ".csv" else []

    def _sha256(path: Path) -> str:
        import hashlib
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    pdf_kb = PDFKnowledgeBase(
        path=[{"path": str(p), "metadata": {"user_id": str(user_id), "type": "pdf", "file_sha256": _sha256(p)}} for p in pdf_files_for_kb],
        vector_db=pdf_vector_db,
        chunking_strategy=AgenticChunking(),
        num_documents=5
    )
    docx_kb = DocxKnowledgeBase(
        path=[{"path": str(p), "metadata": {"user_id": str(user_id), "type": "docx", "file_sha256": _sha256(p)}} for p in docx_files_for_kb],
        vector_db=docx_vector_db,
        formats=[".doc", ".docx"],
        num_documents=5
    )
    text_kb = TextKnowledgeBase(
        path=[{"path": str(p), "metadata": {"user_id": str(user_id), "type": "text", "file_sha256": _sha256(p)}} for p in text_files_for_kb],
        vector_db=text_vector_db,
        formats=[".txt", ".md"],
        num_documents=5
    )
    csv_kb = CSVKnowledgeBase(
        path=[{"path": str(p), "metadata": {"user_id": str(user_id), "type": "csv", "file_sha256": _sha256(p)}} for p in csv_files_for_kb],
        vector_db=csv_vector_db,
        num_documents=5
    )

    knowledge_base = CombinedKnowledgeBase(
        sources=[pdf_kb, docx_kb, text_kb, csv_kb],
        vector_db=combined_vector_db,
        num_documents=6
    )

    # Log basic ingestion diagnostics
    try:
        logging.info(f"Knowledge ingestion: pdf={len(pdf_files_for_kb)} docx={len(docx_files_for_kb)} text={len(text_files_for_kb)} csv={len(csv_files_for_kb)} for user {user_id}")
    except Exception as e:
        logging.warning(f"Unable to list PDFs in {user_pdf_dir}: {e}")

    # Do not load here; callers will decide recreate/upsert based on context
    logging.info("Knowledge base object created; loading deferred to caller")
    return knowledge_base


async def run_rag_agent_async(query, user_id, session_id):
    """
    AGNO RAG agent using ChromaDB and nomic embedder.
    Initializes a fresh knowledge base sync on each query.
    
    Args:
        query: Text query
        user_id: User ID
        session_id: Session ID
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
