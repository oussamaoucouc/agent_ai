"""
Shared output cleaning utilities for all AI agents.
Provides consistent, robust cleaning across MCP, RAG, and Assistant agents.
"""
import re

# Pattern to match chat template artifact tokens
_ARTIFACT_TOKEN_REGEX = re.compile(
    r"\s*(?:<\|im_end\|>|<\|im_start\|>|<\|eot\|>|<eot>|</s>|<end_of_role>|end_of_role|<end_of_turn>|end_of_turn)\s*",
    re.IGNORECASE,
)

# Pattern to match AGNO tool execution logs
_TOOL_EXECUTION_LOG_REGEX = re.compile(
    r"[\w_]+\([^)]*\)\s*completed\s+in\s+[\d.]+s\.?",
    re.IGNORECASE,
)

# Pattern to match single API- prefix at start of text
_TOOL_NAME_PREFIX_REGEX = re.compile(
    r"^API-[\w-]+-",
    re.IGNORECASE | re.MULTILINE,
)


def clean_agent_output(text: str, agent_type: str = "general") -> str:
    """
    Robustly clean agent output to remove artifacts and ensure user-friendly formatting.
    
    Args:
        text: Raw output from agent
        agent_type: Type of agent ("mcp", "rag", "assistant", "general")
    
    Returns:
        Cleaned, user-friendly formatted text
    
    Strategy:
    - Protect URLs from corruption during cleaning
    - Remove chat template artifact tokens
    - Remove AGNO tool execution logs
    - Remove concatenated tool names (e.g., "API-post-API-retrieve-a-")
    - Preserve proper spacing between content blocks
    - Only remove clearly identified artifact patterns, preserve all other content
    """
    if not isinstance(text, str) or not text.strip():
        return text

    # STEP 0: Protect URLs from being corrupted by regex cleaning
    url_pattern = re.compile(r'(https?://[^\s<>"]+)')
    urls = url_pattern.findall(text)
    url_placeholders = {}
    for i, url in enumerate(urls):
        placeholder = f"__PROTECTED_URL_{i}__"
        url_placeholders[placeholder] = url
        text = text.replace(url, placeholder)

    # STEP 1: Remove tool execution logs (AGNO framework logs)
    cleaned = _TOOL_EXECUTION_LOG_REGEX.sub("", text)
    
    # STEP 2: Remove single API- prefix at start of text
    cleaned = _TOOL_NAME_PREFIX_REGEX.sub("", cleaned)
    
    # STEP 3: Remove concatenated tool names (malformed listings)
    # More specific pattern to avoid false positives
    cleaned = re.sub(
        r'\b(API-[a-z]{3,15}(?:-API-[a-z]{3,15}){1,5})\b',
        "",
        cleaned,
        flags=re.IGNORECASE
    )

    # STEP 4: Remove lines that are only an artifact token
    def _is_artifact_line(line: str) -> bool:
        return bool(_ARTIFACT_TOKEN_REGEX.fullmatch(line.strip()))

    lines = [ln for ln in cleaned.splitlines() if not _is_artifact_line(ln)]
    cleaned = "\n".join(lines)

    # STEP 5: Remove artifact tokens appearing inline
    cleaned = _ARTIFACT_TOKEN_REGEX.sub("", cleaned)

    # STEP 6: Remove partial artifact patterns at end of text
    cleaned = re.sub(r"\s*<\|[^>]*$", "", cleaned)  # Incomplete <|...|> at end
    cleaned = re.sub(r"\s*<\|im_[^>]*$", "", cleaned, flags=re.IGNORECASE)  # Partial im_start/end
    
    # STEP 7: Clean up excessive blank lines but preserve structure
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    
    # STEP 8: Fix concatenated text issues (e.g., "managementCould" -> "management Could")
    # Ensure spacing between sentences that might be concatenated
    # Match: lowercase letter followed by uppercase letter (no space between)
    cleaned = re.sub(r'([a-z])([A-Z])', r'\1 \2', cleaned)
    
    # Ensure spacing after periods, colons, question marks, and exclamations if missing
    cleaned = re.sub(r'([.!?:])([A-Z])', r'\1 \2', cleaned)
    
    # STEP 9: Ensure proper spacing after headers and bold patterns
    # Add double newline after patterns like "**Title:**" if not already present
    cleaned = re.sub(r'(\*\*[^*]+:\*\*)(\n)([^\n])', r'\1\n\n\3', cleaned)
    
    # ========== COMPREHENSIVE FORMAT FIXING FOR 10/10 UX ==========
    
    # STEP 10: Fix markdown headers (## and ###) - MUST be on their own line
    cleaned = re.sub(r'([^\n])(#{2,}\s+)', r'\1\n\n\2', cleaned)
    
    # STEP 11: Fix bold section headers (**Title:**) - need line break before AND after
    cleaned = re.sub(r'([^\n])(\*\*[^*]+:\*\*)', r'\1\n\n\2', cleaned)
    cleaned = re.sub(r'(\*\*[^*]+:\*\*)([^\n\*])', r'\1\n\2', cleaned)
    
    # STEP 12: Fix bullet lists (- item) - MUST be on their own line
    cleaned = re.sub(r'([^\n\-])(\-\s+[A-Z])', r'\1\n\2', cleaned)
    
    # STEP 13: Fix numbered lists (1., 2., etc.) - MUST be on their own line
    cleaned = re.sub(r'([^\n\d])(\d+\.\s+)', r'\1\n\n\2', cleaned)
    
    # STEP 14: Fix questions followed by content - add line break
    cleaned = re.sub(r'(\?)\s*([A-Z])', r'\1\n\n\2', cleaned)
    
    # STEP 15: Fix transitional phrases - add line break
    cleaned = re.sub(r'([.!?])\s*(However,|Let me|I will|To proceed|Here\'s why|Consider)', r'\1\n\n\2', cleaned)
    
    # STEP 16: Fix colons that introduce lists
    cleaned = re.sub(r'(:\s*)(\d+\.)', r':\n\n\2', cleaned)
    cleaned = re.sub(r'(:\s*)(\-\s+)', r':\n\n\2', cleaned)
    
    # STEP 17: Ensure proper spacing after section markers like "###"
    cleaned = re.sub(r'(#{2,}[^\n]+)([A-Z])', r'\1\n\n\2', cleaned)
    
    # Normalize bullet points for consistency
    cleaned = re.sub(r'^\s*[•·●○]\s+', '- ', cleaned, flags=re.MULTILINE)
    
    # ========== END COMPREHENSIVE FORMATTING ==========
    
    # STEP 18: Agent-specific formatting enhancements
    if agent_type == "rag":
        cleaned = _enhance_rag_formatting(cleaned)
    
    # STEP 19: RESTORE protected URLs
    for placeholder, url in url_placeholders.items():
        cleaned = cleaned.replace(placeholder, url)
    
    # STEP 20: Final cleanup - remove duplicate blank lines
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    
    # FINAL: Only strip trailing newlines, preserve leading spaces
    return cleaned.rstrip('\n')


def _enhance_rag_formatting(text: str) -> str:
    """
    RAG-specific formatting enhancements for better readability.
    """
    # Remove excessive markdown headers (#### to ##)
    text = re.sub(r'^####\s+(.+)$', r'**\1**', text, flags=re.MULTILINE)
    text = re.sub(r'^###\s+(.+)$', r'**\1**', text, flags=re.MULTILINE)
    
    # Clean up "Source & Context" section
    text = re.sub(r'\*\*Source & Context\*\*', '\n📄 **Source Information:**', text)
    text = re.sub(r'From the\s+', '\n📌 ', text)
    
    # Clean up "Key Additional Notes" section
    text = re.sub(r'\*\*Key Additional Notes\*\*', '\n📝 **Additional Notes:**', text)
    
    # Add emoji bullets for better readability
    text = re.sub(r'^-\s+', '  • ', text, flags=re.MULTILINE)
    
    # Clean up common labels
    text = re.sub(r'\*\*Taxes:\*\*', '\n💰 **Taxes:**', text)
    text = re.sub(r'\*\*Validity:\*\*', '\n📅 **Validity:**', text)
    text = re.sub(r'\*\*Assumptions:\*\*', '\n📋 **Assumptions:**', text)
    
    # Format currency amounts
    text = re.sub(r'\$(\d+)\s+USD', r'💵 $\1 USD', text)
    
    return text.rstrip('\n')
