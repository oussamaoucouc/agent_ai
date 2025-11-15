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
from agno.knowledge.embedder.openai import OpenAIEmbedder
from agno.knowledge.knowledge import Knowledge
from agno.vectordb.chroma import ChromaDb
from agno.models.groq import Groq
from agno.models.ollama import Ollama
from agno.models.openai import OpenAIChat
from agno.db.postgres import PostgresDb
from agno.tools.reasoning import ReasoningTools
from agno.tools.knowledge import KnowledgeTools
 
from . import config as cfg
from .locks import get_user_kb_lock

import logging
logging.basicConfig(level=logging.INFO)

# Removed custom KB cache directory; rely on AGNO/Chroma persistence.


# Removed custom directory state sync; AGNO's knowledge base handles loading/upserts.


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
    Initialize the per-user knowledge base and let AGNO/Chroma manage persistence.
    """
    user_pdf_dir = cfg.get_user_pdf_dir(user_id)

    logging.info("Initializing knowledge base")
    logging.info(f"Using Ollama URL for embedder: {cfg.OLLAMA_BASE_URL}")
    logging.info(f"OpenAI-compatible base URL (embeddings): {cfg.get_openai_base_url()}")

    embedder = OpenAIEmbedder(
        id="ai/granite-embedding-multilingual",
        base_url=cfg.get_openai_base_url(),
        api_key=cfg.OPENAI_API_KEY or "anything",
    )

    user_chroma_path = os.path.join(tempfile.gettempdir(), "afriprof_ai_chroma", str(user_id))
    os.makedirs(user_chroma_path, exist_ok=True)
    vector_db = ChromaDb(
        collection=f"ragdocs{user_id}",
        path=user_chroma_path,
        persistent_client=True,
        embedder=embedder
    )
    logging.info(f"Initialized ChromaDB: collection=ragdocs{user_id}, path={user_chroma_path}")

    contents_db = PostgresDb(db_url=cfg.DB_URL, knowledge_table="knowledge_contents_v2")
    knowledge = Knowledge(
        name=f"user_{user_id}_kb",
        vector_db=vector_db,
        contents_db=contents_db,
        max_results=10
    )

    try:
        if hasattr(knowledge, "add_contents_async"):
            await knowledge.add_contents_async(
                paths=[user_pdf_dir],
                include=["*.pdf", "*.md", "*.mkd", "*.csv", "*.json", "*.txt", "*.pptx", "*.docx"],
                metadata={"user_id": user_id}
            )
        else:
            patterns = ["*.pdf", "*.md", "*.mkd", "*.csv", "*.json", "*.txt", "*.pptx", "*.docx"]
            files = []
            for pat in patterns:
                files.extend([str(p) for p in Path(user_pdf_dir).glob(pat)])
            for f in files:
                if hasattr(knowledge, "add_content_async"):
                    await knowledge.add_content_async(path=f, metadata={"user_id": user_id})
                else:
                    knowledge.add_content(path=f, metadata={"user_id": user_id})
    except Exception as e:
        logging.warning(f"Unable to add contents from {user_pdf_dir}: {e}")

    return knowledge

# Removed explicit Memory v2 setup. Agno v2 manages user memories via Agent(db=..., enable_user_memories=...).

async def run_rag_agent_async(query, user_id, session_id):
    """
    AGNO RAG agent using ChromaDB and openhermes embedder.
    Initializes a fresh knowledge base sync on each query.
    """
    logging.info(f"Starting RAG agent with Ollama at: {cfg.OLLAMA_BASE_URL}")
    logging.info(f"OpenAI-compatible base URL: {cfg.get_openai_base_url()}")
    
    knowledge_base = await initialize_knowledge_base(user_id)
    lock = get_user_kb_lock(user_id)
    logging.info(f"Waiting for KB lock for user {user_id} (query)")
    async with lock:
        logging.info(f"Entered KB lock for user {user_id} (query)")
    #memory_rag = await initialize_memory_dbs(user_id, session_id)
    storage_session_id = f"{user_id}_{session_id}"  # For PostgresStorage isolation

    # Memory DBs already initialized via the cached function
    
    

    # Resolve per-session model preference
    try:
        import sessions as session_mod
        with session_mod.SessionLocal() as db:
            session_model_id = session_mod.get_session_model_id(db, user_id, session_id)
        logging.info(f"RAG agent model selected: user={user_id}, session={session_id}, model_id={session_model_id}")
        session_model = OpenAIChat(id=session_model_id, base_url=cfg.get_openai_base_url(), api_key=cfg.OPENAI_API_KEY or "anything")
    except Exception as e:
        logging.warning(f"Falling back to current model due to error resolving session model: {e}")
        session_model = cfg.get_current_model()

    rag_expert_agent = Agent(
        model=session_model,
        reasoning=False,
        name="rag_expert_agent",
        session_id=session_id,
        session_state={"user_id":user_id, "session_id":session_id},
        
        role="AI Expert in Retrieval-Augmented Generation (RAG) systems that provides comprehensive, accurate, and contextually relevant responses by leveraging advanced document retrieval and knowledge synthesis techniques",
        user_id=user_id,
        description=dedent(f"""\
            You are an AI RAG Expert, optimized for maximum retrieval accuracy, semantic understanding, and knowledge synthesis. 
            Your expertise lies in intelligently retrieving, analyzing, and synthesizing information from knowledge bases to provide comprehensive, accurate, and contextually relevant responses.
            """),
        knowledge=knowledge_base,
        search_knowledge=True,
        markdown=True,
        read_chat_history=True,
        add_history_to_context=True,
        num_history_runs=2,
        db = PostgresDb(db_url=cfg.DB_URL, session_table="agent_session_v2"),
        enable_user_memories=False,
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

        return result_content

    except Exception as e:
        logging.error(f"Error in RAG agent: {type(e).__name__}: {str(e)}")
        import traceback
        logging.error(f"Full traceback: {traceback.format_exc()}")
        raise RuntimeError(f"An error occurred while generating a response: {e}")