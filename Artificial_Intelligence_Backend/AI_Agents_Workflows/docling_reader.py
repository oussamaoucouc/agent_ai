"""
Docling-powered document reader for enhanced RAG quality.

This module provides readers that use IBM's Docling library for 
superior document parsing with layout understanding, table extraction,
and rich metadata preservation.

Uses Docling's native HybridChunker for structure-aware, token-controlled chunking.
"""

import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

# Lazy import to avoid breaking if docling is not installed
_DOCLING_AVAILABLE = None

def _check_docling_available():
    global _DOCLING_AVAILABLE
    if _DOCLING_AVAILABLE is None:
        try:
            from docling.document_converter import DocumentConverter
            _DOCLING_AVAILABLE = True
        except ImportError:
            _DOCLING_AVAILABLE = False
            logging.warning(
                "Docling is not installed. Install with: uv pip install docling\n"
                "Falling back to AGNO's default readers."
            )
    return _DOCLING_AVAILABLE


class DoclingReader:
    """
    Universal document reader powered by Docling.
    Handles PDF, DOCX, PPTX, XLSX, HTML, and images.
    
    Uses Docling's HybridChunker for structure-aware chunking that:
    - Respects document hierarchy (sections, headings)
    - Controls chunk size based on token limits
    - Preserves rich metadata (page numbers, sections, element types)
    
    Automatically detects and uses GPU acceleration if available.
    """
    
    SUPPORTED_EXTENSIONS = {
        ".pdf", ".docx", ".doc", ".pptx", ".ppt", 
        ".xlsx", ".xls", ".html", ".htm",
        ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".gif"
    }
    
    def __init__(
        self,
        enable_vlm: bool = False,
        vlm_model: str = "granite_docling",
        ocr_enabled: bool = True,
        force_cpu: bool = False,
        max_tokens: int = 512,  # Token limit per chunk
    ):
        """
        Initialize DoclingReader.
        
        Args:
            enable_vlm: Enable Visual Language Model for image descriptions
            vlm_model: VLM model to use (default: granite_docling)
            ocr_enabled: Enable OCR for scanned documents
            force_cpu: Force CPU usage even if GPU is available
            max_tokens: Maximum tokens per chunk (for HybridChunker)
        """
        if not _check_docling_available():
            raise ImportError(
                "Docling is required but not installed. "
                "Install with: uv pip install docling"
            )
        
        from docling.document_converter import DocumentConverter
        
        self.max_tokens = max_tokens
        
        # Detect GPU availability
        self.device = "cpu"
        self.gpu_available = False
        try:
            import torch
            if torch.cuda.is_available() and not force_cpu:
                self.gpu_available = True
                self.device = "cuda"
                gpu_name = torch.cuda.get_device_name(0)
                gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                logging.info(f"🚀 Docling GPU acceleration enabled: {gpu_name} ({gpu_memory:.1f} GB)")
            else:
                logging.info("📊 Docling running on CPU (no CUDA available or force_cpu=True)")
        except ImportError:
            logging.info("📊 Docling running on CPU (PyTorch not available)")
        except Exception as e:
            logging.warning(f"GPU detection failed: {e}, falling back to CPU")
        
        # Configure pipeline options (may not be available in all versions)
        pipeline_options = None
        try:
            from docling.datamodel.pipeline_options import PipelineOptions
            pipeline_options = PipelineOptions()
            
            if hasattr(pipeline_options, 'ocr_options'):
                pipeline_options.ocr_options.do_ocr = ocr_enabled
            
            if enable_vlm:
                try:
                    from docling.datamodel.pipeline_options import VlmOptions
                    if hasattr(pipeline_options, 'vlm_options'):
                        pipeline_options.vlm_options = VlmOptions(enabled=True, model=vlm_model)
                        logging.info(f"VLM enabled with model: {vlm_model}")
                except ImportError:
                    logging.warning("VLM options not available in this docling version")
            
            logging.info(f"Docling pipeline configured (device={self.device})")
            
        except ImportError as e:
            logging.warning(f"PipelineOptions not available: {e}")
        except Exception as e:
            logging.warning(f"Failed to configure pipeline options: {e}")
        
        # Initialize converter (try with pipeline_options if supported)
        try:
            if pipeline_options:
                self.converter = DocumentConverter(pipeline_options=pipeline_options)
            else:
                self.converter = DocumentConverter()
        except TypeError:
            # Older versions of Docling don't accept pipeline_options
            logging.warning("DocumentConverter doesn't accept pipeline_options, using defaults")
            self.converter = DocumentConverter()
        
        # Initialize chunker (HybridChunker for best RAG results)
        self.chunker = None
        try:
            from docling.chunking import HybridChunker
            self.chunker = HybridChunker(
                tokenizer="sentence-transformers/all-MiniLM-L6-v2",  # Compatible with most embedders
                max_tokens=max_tokens,
            )
            logging.info(f"Docling HybridChunker initialized (max_tokens={max_tokens})")
        except ImportError:
            logging.warning("HybridChunker not available, will use fallback chunking")
        except Exception as e:
            logging.warning(f"Failed to initialize HybridChunker: {e}, using fallback")
        
        self.ocr_enabled = ocr_enabled
        self.enable_vlm = enable_vlm

    def read(
        self, 
        file_path: str, 
        user_id: Optional[str] = None,
        file_sha256: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Convert document and return structured chunks with metadata.
        
        Args:
            file_path: Path to the document file
            user_id: User ID for metadata tagging
            file_sha256: Pre-computed file hash (computed if not provided)
        
        Returns:
            List of document chunks, each containing:
            - content: Text content of the chunk
            - metadata: Dict with page_number, element_type, section_path, etc.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        ext = path.suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type: {ext}. "
                f"Supported: {self.SUPPORTED_EXTENSIONS}"
            )
        
        # Compute file hash if not provided
        if not file_sha256:
            import hashlib
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            file_sha256 = h.hexdigest()
        
        # Convert document using Docling
        logging.info(f"Docling processing: {path.name}")
        result = self.converter.convert(str(path))
        
        documents = []
        file_name = path.name
        
        # Use HybridChunker if available (best practice)
        if self.chunker:
            try:
                chunk_iter = self.chunker.chunk(result.document)
                for idx, chunk in enumerate(chunk_iter):
                    # Extract text content
                    content = chunk.text if hasattr(chunk, 'text') else str(chunk)
                    if not content or not content.strip():
                        continue
                    
                    # Extract metadata from chunk
                    meta = {
                        "user_id": str(user_id) if user_id else None,
                        "source_file": str(path),
                        "filename": file_name,
                        "file_sha256": file_sha256,
                        "element_type": "hybrid_chunk",
                        "chunk_index": idx,
                    }
                    
                    # Try to get page info from chunk metadata
                    if hasattr(chunk, 'meta') and chunk.meta:
                        if hasattr(chunk.meta, 'doc_items') and chunk.meta.doc_items:
                            first_item = chunk.meta.doc_items[0]
                            if hasattr(first_item, 'prov') and first_item.prov:
                                prov = first_item.prov[0] if first_item.prov else None
                                if prov and hasattr(prov, 'page_no'):
                                    meta["page_number"] = prov.page_no
                        
                        # Get heading/section info
                        if hasattr(chunk.meta, 'headings') and chunk.meta.headings:
                            meta["section_path"] = " > ".join(chunk.meta.headings)
                    
                    documents.append({
                        "content": content.strip(),
                        "metadata": meta
                    })
                
                logging.info(f"HybridChunker extracted {len(documents)} chunks from {file_name}")
                
            except Exception as e:
                logging.warning(f"HybridChunker failed: {e}, falling back to element-based chunking")
                documents = []  # Reset and try fallback
        
        # Fallback: Element-based chunking from document structure
        if not documents:
            try:
                doc_dict = result.document.export_to_dict()
                body = doc_dict.get("body", doc_dict.get("content", []))
                
                if isinstance(body, list):
                    for idx, element in enumerate(body):
                        if not isinstance(element, dict):
                            continue
                        
                        content = element.get("text", "")
                        if not content or not str(content).strip():
                            continue
                        
                        prov = element.get("prov", [])
                        page_no = None
                        if prov and isinstance(prov, list) and len(prov) > 0:
                            page_no = prov[0].get("page_no") if isinstance(prov[0], dict) else None
                        
                        meta = {
                            "user_id": str(user_id) if user_id else None,
                            "source_file": str(path),
                            "filename": file_name,
                            "file_sha256": file_sha256,
                            "element_type": element.get("type", "text"),
                            "page_number": page_no,
                            "section_path": element.get("section_header", ""),
                            "chunk_index": idx,
                        }
                        
                        documents.append({
                            "content": str(content).strip(),
                            "metadata": meta
                        })
            except Exception as e:
                logging.warning(f"Element-based chunking failed: {e}")
        
        # Last resort: Markdown with simple splitting
        if not documents:
            try:
                markdown = result.document.export_to_markdown()
                if markdown and markdown.strip():
                    chunks = self._split_text_into_chunks(markdown, chunk_size=1000, overlap=200)
                    for idx, chunk_text in enumerate(chunks):
                        documents.append({
                            "content": chunk_text,
                            "metadata": {
                                "user_id": str(user_id) if user_id else None,
                                "source_file": str(path),
                                "filename": file_name,
                                "file_sha256": file_sha256,
                                "element_type": "text_chunk",
                                "page_number": None,
                                "section_path": "",
                                "chunk_index": idx,
                                "total_chunks": len(chunks),
                            }
                        })
            except Exception as e:
                logging.warning(f"Markdown fallback failed: {e}")
        
        logging.info(f"Docling extracted {len(documents)} chunks from {file_name}")
        return documents
    
    def _split_text_into_chunks(
        self, 
        text: str, 
        chunk_size: int = 1000, 
        overlap: int = 200
    ) -> List[str]:
        """Fallback text splitter for when Docling chunkers aren't available."""
        if not text or len(text) <= chunk_size:
            return [text] if text else []
        
        chunks = []
        paragraphs = text.split('\n\n')
        current_chunk = ""
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            if len(current_chunk) + len(para) + 2 > chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                if overlap > 0 and len(current_chunk) > overlap:
                    current_chunk = current_chunk[-overlap:] + "\n\n" + para
                else:
                    current_chunk = para
            else:
                current_chunk = (current_chunk + "\n\n" + para) if current_chunk else para
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks if chunks else [text]
    
    def is_supported(self, file_path: str) -> bool:
        """Check if a file type is supported by this reader."""
        ext = Path(file_path).suffix.lower()
        return ext in self.SUPPORTED_EXTENSIONS


def get_docling_reader(
    enable_vlm: bool = False,
    fallback_to_agno: bool = True,
    max_tokens: int = 512,
) -> Optional[DoclingReader]:
    """
    Factory function to get a DoclingReader instance.
    
    Args:
        enable_vlm: Enable Visual Language Model for image descriptions
        fallback_to_agno: If True, return None when Docling is not available
        max_tokens: Maximum tokens per chunk for HybridChunker
    
    Returns:
        DoclingReader instance or None if not available and fallback is enabled
    """
    if not _check_docling_available():
        if fallback_to_agno:
            return None
        raise ImportError("Docling is not installed")
    
    return DoclingReader(enable_vlm=enable_vlm, max_tokens=max_tokens)

