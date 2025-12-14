"""
MCP Agent functionality using the AGNO framework.
Configurable MCP transport (streamable-http or stdio) with clean lifecycle.
"""
from textwrap import dedent
import re
import os
import logging
import asyncio
from agno.agent import Agent, RunResponse
from agno.storage.postgres import PostgresStorage
from agno.tools.mcp import MultiMCPTools, MCPTools
from agno.tools.function import Function  # Import Agno's native Function class
from . import config as cfg

from . import model_factory


def create_mcp_tool_function(tool_name: str, description: str, parameters: dict, session) -> Function:
    """
    Create an Agno-compatible Function object for dynamically added MCP tools.
    
    This uses Agno's native Function class which properly satisfies FunctionCall
    Pydantic validation, unlike custom wrapper classes.
    
    Args:
        tool_name: Name of the MCP tool
        description: Tool description
        parameters: JSON Schema parameters for the tool
        session: The MCP session to call tools through
    
    Returns:
        An Agno Function object that can be registered in toolkit.functions
    """
    # Create the async callable that invokes the MCP tool
    async def tool_entrypoint(**kwargs):
        result = await session.call_tool(tool_name, kwargs)
        if result.content:
            return str(result.content[0].text) if hasattr(result.content[0], 'text') else str(result.content[0])
        return ""
    
    # Build a proper Agno Function using the native class
    # The Function class accepts these standard parameters
    return Function(
        name=tool_name,
        description=description or f"MCP Tool: {tool_name}",
        parameters=parameters or {"type": "object", "properties": {}},
        entrypoint=tool_entrypoint,
    )

logger = logging.getLogger(__name__)

# Track which MCP servers have been registered this session to avoid re-adding
_registered_mcp_servers: set = set()
_mcp_gateway_initialized: bool = False

def reset_mcp_gateway_state():
    """Reset the MCP gateway state to force re-initialization on next agent call."""
    global _mcp_gateway_initialized, _registered_mcp_servers
    _mcp_gateway_initialized = False
    _registered_mcp_servers.clear()
    logger.info("MCP Gateway state reset")


_ARTIFACT_TOKEN_REGEX = re.compile(
    r"\s*(?:<\|im_end\|>|<\|im_start\|>|<\|eot\|>|<eot>|</s>|<end_of_role>|end_of_role|<end_of_turn>|end_of_turn)\s*",
    re.IGNORECASE,
)

# Pattern to match AGNO tool execution logs like:
# "search(query=...) completed in 1.9721s."
# "fetch_content(url=...) completed in 2.0278s."
# "get_chat_history(num_chats=1) completed in 0.0004s."
_TOOL_EXECUTION_LOG_REGEX = re.compile(
    r"[\w_]+\([^)]*\)\s*completed\s+in\s+[\d.]+s\.?",
    re.IGNORECASE,
)

# Pattern to match concatenated tool names like:
# "API-post-API-retrieve-a-API-get-block-"
# This removes malformed tool name listings that leak into responses
_TOOL_NAME_CONCATENATION_REGEX = re.compile(
    r"(API-[\w-]+(?:-API-[\w-]+)+)",  # Match the pattern without consuming leading space
    re.IGNORECASE,
)

# Pattern to match single API- prefix at the very start of text
# "API-post-I searched..." -> "I searched..."
_TOOL_NAME_PREFIX_REGEX = re.compile(
    r"^API-[\w-]+-",  # Match API-xxx- at start of string only
    re.IGNORECASE | re.MULTILINE,
)

def _clean_output_artifacts(text: str) -> str:
    """Robustly remove chat-template artifact tokens and tool execution logs.

    Strategy:
    - Protect URLs from corruption during cleaning
    - Drop lines that are only an artifact token
    - Remove tokens anywhere using a compiled regex with surrounding whitespace
    - Remove AGNO tool execution logs (e.g., "search(query=...) completed in 1.9721s.")
    - Remove concatenated tool names (e.g., "API-post-API-retrieve-a-") with more specific pattern
    - Preserve proper spacing between content blocks
    - Only remove clearly identified artifact patterns, preserve all other content
    """
    if not isinstance(text, str):
        return text

    # STEP 0: Protect URLs from being corrupted by regex cleaning
    url_pattern = re.compile(r'(https?://[^\s<>\"]+)')
    urls = url_pattern.findall(text)
    url_placeholders = {}
    for i, url in enumerate(urls):
        placeholder = f"__PROTECTED_URL_{i}__"
        url_placeholders[placeholder] = url
        text = text.replace(url, placeholder)

    # 1) Remove tool execution logs (AGNO framework logs)
    cleaned = _TOOL_EXECUTION_LOG_REGEX.sub("", text)
    
    # 1.5) Remove single API- prefix at start of text
    cleaned = _TOOL_NAME_PREFIX_REGEX.sub("", cleaned)
    
    # 1.6) Remove concatenated tool names (malformed listings) - MORE SPECIFIC NOW
    # Only match lowercase patterns with reasonable length to avoid false positives
    cleaned = re.sub(
        r'\b(API-[a-z]{3,15}(?:-API-[a-z]{3,15}){1,5})\b',  # More restrictive pattern
        "",
        cleaned,
        flags=re.IGNORECASE
    )

    # 2) Remove lines that are only an artifact token
    def _is_artifact_line(line: str) -> bool:
        return bool(_ARTIFACT_TOKEN_REGEX.fullmatch(line.strip()))

    lines = [ln for ln in cleaned.splitlines() if not _is_artifact_line(ln)]
    cleaned = "\n".join(lines)

    # 3) Remove artifact tokens appearing inline (but preserve surrounding structure)
    cleaned = _ARTIFACT_TOKEN_REGEX.sub("", cleaned)

    # 4) Only strip trailing artifact patterns, not general characters
    # Remove only if there's a clear partial artifact at the end
    cleaned = re.sub(r"\s*<\|[^>]*$", "", cleaned)  # Incomplete <|...|> at end
    cleaned = re.sub(r"\s*<\|im_[^>]*$", "", cleaned, flags=re.IGNORECASE)  # Partial im_start/end
    
    # 5) Clean up excessive blank lines but preserve structure
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    
    # 6) Fix concatenated text (lowercase followed by uppercase)
    cleaned = re.sub(r'([a-z])([A-Z])', r'\1 \2', cleaned)
    
    # Ensure spacing after periods, colons, question marks, and exclamations if missing
    cleaned = re.sub(r'([.!?:])([A-Z])', r'\1 \2', cleaned)
    
    # ========== COMPREHENSIVE FORMAT FIXING FOR 10/10 UX ==========
    
    # 7) Fix markdown headers (## and ###) - MUST be on their own line
    cleaned = re.sub(r'([^\n])(#{2,}\s+)', r'\1\n\n\2', cleaned)
    
    # 8) Fix bold section headers (**Title:**) - need line break before AND after
    # Match pattern: text followed by **SomeBoldText:** 
    cleaned = re.sub(r'([^\n])(\*\*[^*]+:\*\*)', r'\1\n\n\2', cleaned)
    # Also add line break after bold headers if followed by content
    cleaned = re.sub(r'(\*\*[^*]+:\*\*)([^\n\*])', r'\1\n\2', cleaned)
    
    # 9) Fix bullet lists (- item) - MUST be on their own line
    cleaned = re.sub(r'([^\n\-])(\-\s+[A-Z])', r'\1\n\2', cleaned)
    
    # 10) Fix numbered lists (1., 2., etc.) - MUST be on their own line
    cleaned = re.sub(r'([^\n\d])(\d+\.\s+)', r'\1\n\n\2', cleaned)
    
    # 11) Fix questions followed by content - add line break
    cleaned = re.sub(r'(\?)\s*([A-Z])', r'\1\n\n\2', cleaned)
    
    # 12) Fix transitional phrases - add line break
    cleaned = re.sub(r'([.!?])\s*(However,|Let me|I will|To proceed|Here\'s why|Consider)', r'\1\n\n\2', cleaned)
    
    # 13) Fix colons that introduce lists
    cleaned = re.sub(r'(:\s*)(\d+\.)', r':\n\n\2', cleaned)
    cleaned = re.sub(r'(:\s*)(\-\s+)', r':\n\n\2', cleaned)
    
    # 14) Ensure proper spacing after section markers like "###"
    cleaned = re.sub(r'(#{2,}[^\n]+)([A-Z])', r'\1\n\n\2', cleaned)
    
    # ========== END COMPREHENSIVE FORMATTING ==========
    
    # 15) Ensure proper spacing after headers and bold patterns
    cleaned = re.sub(r'(\*\*[^*]+:\*\*)(\n)([^\n])', r'\1\n\n\3', cleaned)
    
    # 16) RESTORE protected URLs
    for placeholder, url in url_placeholders.items():
        cleaned = cleaned.replace(placeholder, url)
    
    # 17) Final cleanup - remove duplicate blank lines
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    
    # ========== RENUMBER SEQUENTIAL LISTS ==========
    # LLM often outputs all items as "1." - renumber them to 1, 2, 3...
    # A new section (header or ### or multiple blank lines before a heading-style line) resets the counter
    lines = cleaned.split('\n')
    result_lines = []
    list_counter = 0
    
    # Patterns that indicate a new section (reset list counter)
    section_break_pattern = re.compile(r'^(#{1,6}\s+|[A-Z][a-zA-Z\s]+:$|\*\*[^*]+:\*\*$)')
    
    for i, line in enumerate(lines):
        # Check if this is a numbered list item
        num_match = re.match(r'^(\s*)(\d+)\.\s+(.*)$', line)
        
        if num_match:
            indent, num, content = num_match.groups()
            list_counter += 1
            result_lines.append(f'{indent}{list_counter}. {content}')
        else:
            # Check if this is a section break that should reset numbering
            # Section breaks: headers, empty lines before headers, triple+ blank lines
            is_section_break = False
            
            # Check for heading-style lines
            if section_break_pattern.match(line.strip()):
                is_section_break = True
            
            # Check for blank line followed by a heading-style line
            if line.strip() == '' and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if section_break_pattern.match(next_line):
                    is_section_break = True
            
            if is_section_break:
                list_counter = 0
            
            result_lines.append(line)
    
    cleaned = '\n'.join(result_lines)
    # ========== END RENUMBER SEQUENTIAL LISTS ==========
    
    # CRITICAL: Don't strip() individual chunks - this removes leading spaces!
    # Only strip trailing newlines to avoid excessive whitespace
    return cleaned.rstrip('\n')


def run_agent(query, user_id, session_id, images=None, audio=None, videos=None, stream=False):
    """
    Entry point for MCP agent that works in both synchronous and asynchronous contexts.
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
        return run_agent_async(query, user_id, session_id, images, audio, videos, stream)
    else:
        # No event loop running, so create a new one
        logging.info("Creating new event loop")
        return asyncio.run(run_agent_async(query, user_id, session_id, images, audio, videos, stream))


async def run_agent_async(query, user_id, session_id, images=None, audio=None, videos=None, stream=False):
    """
    AGNO MCP agent using MCP server tools.
    Using cached knowledge base and memory DBs for better performance.
    
    Args:
        query: Text query
        user_id: User ID
        session_id: Session ID
        stream: If True, returns an async generator yielding content chunks
    """
    logger.info(f"Starting MCP agent with Ollama at: {cfg.OLLAMA_BASE_URL}")
    logger.info(f"OpenAI-compatible base URL: {cfg.get_openai_base_url()}")
    
    # Get cached knowledge base and memory DBs
    storage_session_id = f"{user_id}_{session_id}"  # For PostgresStorage isolation

    # Resolve per-session model preference
    try:
        import sessions as session_mod
        with session_mod.SessionLocal() as db:
            session_model_id = session_mod.get_session_model_id(db, user_id, session_id)
        logger.info(f"MCP agent model selected: user={user_id}, session={session_id}, model_id={session_model_id}")
        session_model = model_factory.create_model(
            model_id=session_model_id,
            openai_api_key=cfg.OPENAI_API_KEY,
            google_api_key=cfg.GOOGLE_API_KEY,
            openrouter_api_key=cfg.OPENROUTER_API_KEY,
            ollama_base_url=cfg.OLLAMA_BASE_URL,
            openai_base_url=cfg.OPENAI_BASE_URL,
            gemini_search_enabled=cfg.GEMINI_SEARCH_ENABLED,
        )
    except Exception as e:
        logger.warning(f"Falling back to current model for MCP due to error resolving session model: {e}")
        session_model = cfg.get_current_model()

    agent_common_kwargs = dict(
        model=session_model,
        name="mcp_llm_agent",
        instructions=dedent("""\
        ### ROLE & PERSONA
        You are an expert AI assistant with MCP (Model Context Protocol) tools. Help users efficiently with a warm, professional, concise tone. Speak naturally, not robotically.
        
        ---
        
        ### HALLUCINATION PREVENTION (CRITICAL - READ FIRST)
        1. **UNCERTAINTY**: If you lack information or tools fail, say "I don't know" or "I couldn't find that information." Never guess.
        2. **TOOL RELIANCE**: Answer ONLY from tool outputs. Do NOT use your general knowledge unless explicitly requested.
        3. **CITATIONS**: Reference tools naturally when presenting facts (e.g., "According to the search results...").
        4. **VALIDATION**: If tool output seems incomplete or unusual, acknowledge the limitation honestly.
        5. **NO FABRICATION**: Never invent data, URLs, filenames, API results, or function outputs.
        
        ---
        
        ### TOOL SELECTION & EXECUTION
        
        **Selection Priority**:
        - Use the most specific tool available (prefer `fetch_content` over generic `mcp-exec`)
        - For complex queries, chain tools logically (search → fetch → analyze)
        - Always provide ALL required parameters - incomplete tool calls cause failures
        
        **Validation**:
        - Check tool outputs for completeness before responding
        - If output is partial or unclear, acknowledge it ("The results are limited...")
        - Each tool call should be self-contained with all required context
        
        **Silent Execution** (CRITICAL):
        - Tool usage must be invisible to users
        - NEVER say: "I executed...", "The API returned...", "Calling function..."
        - DO say: "I found...", "Here's what I discovered...", "The information shows..."
        
        ---
        
        ### MCP DYNAMIC SERVER MANAGEMENT
        
        **Built-in Gateway Tools** (when Docker Gateway is active):
        - `mcp-find(query="...")`: Search for MCP servers. **REQUIRES** query argument.
        - `mcp-add(name="...")`: Add new servers dynamically
        - `mcp-remove(name="...")`: Remove servers from session
        - `code-mode(...)`: Advanced server configuration
        
        **Workflow**:
        1. If you need a capability (like search), use `mcp-find(query="search")` first
        2. Add the server: `mcp-add(name="duckduckgo")` 
        3. Tools appear automatically; if not, use `code-mode` to create interface
        4. Use the tool naturally
        
        **Standard Servers**:
        - `duckduckgo`: Web search & content fetching
        - `github`: Repository access
        
        ---
        
        ### RESPONSE STYLE (Make Every Response User-Friendly)
        
        **Direct Answers** (The "Coffee Shop Test"):
        - Explain like talking to a friend, not a technical report
        - Answer the question first, details second (progressive disclosure)
        - Jump straight in - NO fluff like "That's a great question" or "Let me demonstrate"
        
        **Formatting**:
        - **Use bold for section titles** (NOT markdown headers like #, ##)
        - Use bullet points for lists
        - Keep paragraphs short (2-3 sentences max)
        - NO code blocks for simple text
        
        **Tone Examples**:
        - ✅ GOOD: "I found 3 articles about MCP. The most relevant explains..."
        - ❌ BAD: "I executed the search function with your query and the API returned 3 results..."
        - ✅ GOOD: "I'm not sure about that part"
        - ❌ BAD: "My data is insufficient to provide an accurate response"
        
        **Natural Language**:
        - "Here's what I found..." NOT "The data indicates..."
        - "I searched and..." NOT "Tool output shows..."
        - Use contractions (I'm, you're, it's) for warmth
        
        ---
        
        ### CONTEXT AWARENESS
        
        **Chat History**:
        - You have access to conversation history **silently** - never mention it
        - NEVER say: "Here is the chat history" or "I retrieved our previous conversation"
        - Use context naturally to provide coherent responses
        
        **Tool Capabilities**:
        - When asked "What can you do?", describe capabilities in user-friendly terms
        - ✅ "I can search the web using DuckDuckGo, manage servers, and fetch content"
        - ❌ "I have access to: duckduckgo_search, mcp-add, mcp-find, fetch_content"
        - **IMPORTANT**: If you added a server (like "duckduckgo"), assume its capabilities are available and list them confidently
        
        ---
        
        ### ERROR HANDLING
        
        **Tool Failures**:
        - If unavailable or failed: "Unable to answer with available tools"
        - Do NOT apologize excessively
        - Do NOT explain technical errors (HTTP codes, stack traces, etc.)
        
        **Missing Capabilities**:
        - Be honest: "I don't have the tools to answer that"
        - Suggest alternatives if possible: "However, I can search for related information..."
        
        ---
        
        ### OUTPUT FORMATTING FOR READABILITY
        
        **Paragraph Structure**:
        - Keep paragraphs SHORT (2-3 sentences maximum)
        - Add blank line between different ideas or topics
        - Break up long explanations into scannable chunks
        
        **Numbered Lists** (CRITICAL):
        - ALWAYS put numbered items on separate lines
        - ✅ GOOD:
          ```
          Would you like me to:
          
          1. Share the page URL?
          2. Check if there's another way?
          3. Look in other workspaces?
          ```
        - ❌ BAD: "Would you like me to:1. Share the URL?2. Check another way?3. Look elsewhere?"
        
        **Questions**:
        - Put follow-up questions on new lines
        - Add blank line before question lists
        - Give questions breathing room
        
        **Special Info** (IDs, URLs, etc.):
        - Put important identifiers on their own line
        - ✅ GOOD: "The page ID is:\nf6aaee1c-ffb6-4fe0"
        - ❌ BAD: "The page ID is f6aaee1c-ffb6-4fe0.Would you..."
        
        ---
        
        ### CRITICAL REMINDERS
        
        1. **NO-FLUFF START**: Never begin with "That's interesting," "Great question," etc.
        2. **SIMPLICITY**: Coffee shop conversation, not technical documentation
        3. **VISIBILITY**: Tool usage is invisible; users see only natural results
        4. **READABILITY**: Short paragraphs, proper spacing, scannable format
        5. **HONESTY**: "I don't know" is always acceptable when appropriate
        6. **REQUIRED PARAMS**: Never call tools without all required parameters
        7. **GROUNDING**: Stick to tool outputs; don't embellish with general knowledge
 """),
        markdown=True,
        show_tool_calls=False,
        reasoning=False,
        session_id=storage_session_id,
        user_id=user_id,
        session_state={"user_id": user_id, "session_id": session_id},
        add_state_in_messages=True,
        read_chat_history=True,
        add_history_to_messages=True,
        num_history_responses=3,
        monitoring=True,
        storage=PostgresStorage(table_name="agent_session", db_url=cfg.DB_URL),
        #memory=memory_mcp,
        #enable_user_memories=True,
        enable_session_summaries=False,
    )
    
    # Retrieve configuration for tools
    runtime_cfg = cfg.get_runtime_config()
    servers = runtime_cfg.get("mcp_servers", []) or []
    runtime_urls = [str(s.get("url", "")).strip() for s in servers if isinstance(s, dict) and str(s.get("url", "")).strip()]
    selected_urls = []
    selected_cmds = []
    try:
        import sessions as session_mod
        with session_mod.SessionLocal() as db:
            selected_urls = session_mod.get_session_mcp_tools_urls(db, user_id, session_id) or []
            selected_cmds = session_mod.get_session_mcp_stdio_commands(db, user_id, session_id) or []
    except Exception as e:
        logger.warning(f"Failed to resolve user-selected MCP tools; using runtime config. err={e}")

    # Filter selected URLs to only include those still in admin catalog
    # This prevents stale selections from being used after admin removes a server
    user_had_selections = bool(selected_urls)  # Track if user originally had selections
    if selected_urls and runtime_urls:
        valid_selected_urls = []
        for u in selected_urls:
            url_str = str(u).strip().rstrip('/')
            if any(url_str == runtime_url.rstrip('/') for runtime_url in runtime_urls):
                valid_selected_urls.append(u)
            else:
                logger.info(f"Skipping stale MCP tool URL not in catalog: {u}")
        selected_urls = valid_selected_urls

    # Prepare stdio commands list
    cmds = []
    if selected_cmds:
        cmds = [c for c in selected_cmds if str(c).strip()]
    else:
        mcp_cmds = runtime_cfg.get("mcp_stdio_commands", []) or []
        mcp_tools = runtime_cfg.get("mcp_stdio_tools", []) or []
        for t in mcp_tools:
            if isinstance(t, dict):
                c = str(t.get("command", "")).strip()
                if c:
                    cmds.append(c)
        for c in mcp_cmds:
            cs = str(c).strip()
            if cs:
                cmds.append(cs)
        if not cmds and cfg.MCP_STDIO_COMMAND:
            if cfg.MCP_STDIO_ARGS:
                cmds.append(" ".join([cfg.MCP_STDIO_COMMAND] + cfg.MCP_STDIO_ARGS))
            else:
                cmds.append(cfg.MCP_STDIO_COMMAND)
    
    # Filter explicit commands for safety
    allowed_execs = {"npx","pnpm","node","yarn","python3","uvx","pipx","bun","npm","uv","java","deno","python","ruby"}
    if cmds:
        filtered_cmds = []
        for c in cmds:
            head = str(c).strip().split()[0] if str(c).strip() else ""
            if head in allowed_execs:
                filtered_cmds.append(c)
        cmds = filtered_cmds

    # Prepare list of toolkits for the Agent
    agent_toolkits = []
    gateway_toolkit = None  # Will be set if Docker Gateway is selected
    
    # 1. SETUP DOCKER GATEWAY (Only if user selected Docker tools)
    gateway_url = "http://mcp-gateway:8080/mcp"
    
    # Check if Docker Gateway (Autonomous Mode) was selected by user
    # Uses is_autonomous flag from config, with URL fallback for backward compatibility
    docker_gateway_selected = False
    autonomous_server_url = None
    if selected_urls:
        for u in selected_urls:
            url_str = str(u).strip()
            # Check if this URL corresponds to an autonomous server in config
            for srv in servers:
                if isinstance(srv, dict):
                    srv_url = str(srv.get("url", "")).strip()
                    # Use is_autonomous flag with fallback to URL pattern
                    is_autonomous = srv.get("is_autonomous", False) or "mcp-gateway" in srv_url.lower()
                    if srv_url.rstrip('/') == url_str.rstrip('/') and is_autonomous:
                        docker_gateway_selected = True
                        autonomous_server_url = url_str
                        break
            # Also check legacy URL pattern as fallback
            if not docker_gateway_selected and "mcp-gateway" in url_str.lower():
                docker_gateway_selected = True
                autonomous_server_url = url_str
            if docker_gateway_selected:
                break
    
    if docker_gateway_selected:
        # Use the actual selected URL or fallback to default gateway
        actual_gateway_url = autonomous_server_url or gateway_url
        logger.info(f"Connecting to Autonomous Mode Server: {actual_gateway_url}")
        gateway_toolkit = MCPTools(
            url=actual_gateway_url, 
            transport="streamable-http",
            timeout_seconds=30
        )
        try:
             await gateway_toolkit.connect()
             agent_toolkits.append(gateway_toolkit)
        except Exception as gw_err:
             logger.error(f"Failed to connect to Autonomous Server: {gw_err}")
             gateway_toolkit = None
    else:
        logger.info("Autonomous Mode not selected, skipping autonomous tools")
    
    # 2. SETUP USER SELECTED TOOLS (e.g. Smithery)
    # Extract user URLs (excluding gateway if present)
    # Only fall back to runtime_urls if user NEVER made any selections (not if selections became stale)
    user_urls = []
    if selected_urls:
        user_urls = [str(u).strip() for u in selected_urls if str(u).strip()]
    else:
        # User has no valid selections (or they are stale) - do not fall back to defaults
        logger.info("No user selections found (or selections were stale). No MCP tools will be loaded.")
         
    for u in user_urls:
        url_str = str(u).strip()
        # Skip if this is the autonomous server we already connected to
        if autonomous_server_url and url_str.rstrip('/') == autonomous_server_url.rstrip('/'):
            continue
        # Also skip if this URL is marked as autonomous in config
        is_autonomous_url = False
        for srv in servers:
            if isinstance(srv, dict):
                srv_url = str(srv.get("url", "")).strip()
                if srv_url.rstrip('/') == url_str.rstrip('/'):
                    is_autonomous_url = srv.get("is_autonomous", False) or "mcp-gateway" in srv_url.lower()
                    break
        if is_autonomous_url:
            continue
            
        try:
            logger.info(f"Connecting to User MCP Server: {url_str}")
            tk = MCPTools(url=url_str, transport="streamable-http", timeout_seconds=30)
            await tk.connect()
            agent_toolkits.append(tk)
        except Exception as e:
            logger.warning(f"Failed to connect to user tool {url_str}: {e}")

    # 3. SETUP STDIO COMMANDS
    if cmds:
         try:
             logger.info(f"Connecting to stdio commands: {cmds}")
             stdio_toolkit = MultiMCPTools(commands=cmds, env={**os.environ}, timeout_seconds=30)
             await stdio_toolkit.connect()
             agent_toolkits.append(stdio_toolkit)
         except Exception as e:
             logger.warning(f"Failed to connect to stdio commands: {e}")

    if not agent_toolkits:
         # Critical failure if nothing connected
         logger.warning("No MCP toolkits connected!")

    # 4. AUTO-ADD SERVERS TO GATEWAY (Only if Docker Gateway was selected)
    # We read the mounted registry.yaml to find what the user has enabled
    registry_path = "/root/.docker/mcp/registry.yaml"
    servers_to_add = []
    added_servers_info = []  # Track for capability injection
    
    if docker_gateway_selected:
        if os.path.exists(registry_path):
            # Try to import yaml here to avoid top-level dependency issues
            try:
                import yaml
                with open(registry_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f) or {}
                
                # Support both 'servers' (standard) and 'registry' (Docker Desktop Windows) keys
                server_configs = data.get('servers') or data.get('registry') or {}
                
                for name, server_cfg in server_configs.items():
                    if isinstance(server_cfg, dict):
                        # Docker Desktop Windows often omits 'enabled' key for active servers
                        # So we treat missing 'enabled' as True by default for this format
                        enabled = server_cfg.get('enabled')
                        if enabled is True or enabled is None:
                            # Extract config/env vars (Docker Desktop uses 'input')
                            env_vars = {}
                            input_data = server_cfg.get('input')
                            if isinstance(input_data, dict):
                                env_vars.update(input_data)
                            # Also check standard 'env'
                            env_data = server_cfg.get('env')
                            if isinstance(env_data, dict):
                                env_vars.update(env_data)
                                
                            servers_to_add.append((name, env_vars))
                        
                logger.info(f"Found enabled MCP servers in registry: {[s[0] for s in servers_to_add]}")
            except ImportError:
                logger.warning("PyYAML not found; cannot parse MCP registry.yaml. Please install pyyaml.")
            except Exception as e:
                logger.warning(f"Failed to parse MCP registry: {e}")
        else:
            logger.debug(f"MCP registry not found at {registry_path}")
    
    # Add servers using the Gateway Toolkit directly
    if gateway_toolkit and gateway_toolkit.session:
        for name, env_vars in servers_to_add:
            try:
                # First, use mcp-config-set to configure any required env vars for this server
                if env_vars:
                    for key, value in env_vars.items():
                        try:
                            # mcp-config-set requires: server, key, value as separate parameters
                            config_result = await gateway_toolkit.session.call_tool(
                                'mcp-config-set', 
                                {'server': name, 'key': key, 'value': str(value)}
                            )
                            config_text = str(config_result.content[0].text) if config_result.content else ""
                            logger.info(f"Set config {name}.{key}: {config_text[:80]}")
                        except Exception as cfg_err:
                            logger.warning(f"Failed to set config {name}.{key}: {cfg_err}")
                
                # Now add the server
                args = {'name': name, 'activate': True}  # activate=True exposes tools in list_tools!
                result = await gateway_toolkit.session.call_tool('mcp-add', args)
                result_text = str(result.content[0].text) if result.content else ""
                logger.info(f"MCP server {name} added to Gateway: {result_text[:100]}")
                
                # Parse tool count from response (e.g., "Successfully added 2 tools in server 'duckduckgo'")
                import re
                match = re.search(r"added (\d+) tools", result_text)
                tool_count = int(match.group(1)) if match else 0
                added_servers_info.append((name, tool_count))
                    
            except Exception as e:
                logger.warning(f"Failed to auto-add MCP server {name}: {e}")
        
        # After ALL servers added, refresh tools in the SAME session
        # We now use Agno's native Function class (via create_mcp_tool_function)
        # which properly satisfies FunctionCall Pydantic validation in v1.8.4+
        logger.info("Refreshing toolkit with newly added tools...")
        try:
            await asyncio.sleep(0.5)  # Brief wait for propagation
            tools_result = await gateway_toolkit.session.list_tools()
            tool_names = [t.name for t in tools_result.tools]
            logger.info(f"Gateway now has {len(tools_result.tools)} tools: {tool_names}")
            
            # Register dynamically added tools using Agno's native Function class
            for tool_def in tools_result.tools:
                if tool_def.name not in gateway_toolkit.functions:
                    # Use the helper that creates Agno-compatible Function objects
                    gateway_toolkit.functions[tool_def.name] = create_mcp_tool_function(
                        tool_name=tool_def.name,
                        description=tool_def.description or f"Tool: {tool_def.name}",
                        parameters=tool_def.inputSchema or {},
                        session=gateway_toolkit.session
                    )
                    logger.info(f"Registered tool with Agno Function: {tool_def.name}")
            
            final_tools = list(gateway_toolkit.functions.keys())
            logger.info(f"Final tools available to Agent: {final_tools}")
        except Exception as refresh_err:
            logger.warning(f"Failed to refresh tools: {refresh_err}")


    # 5. RUN AGENT - Inject dynamic server info into instructions
    dynamic_instructions = agent_common_kwargs.get('instructions', '')
    if added_servers_info:
        server_capability_list = [f"- **{srv_name}** ({tool_count} tools)" for srv_name, tool_count in added_servers_info]
        
        if server_capability_list:
            # PREPEND to instructions so small models see it first
            dynamic_section = "### YOUR ACTIVE CAPABILITIES (IMPORTANT - TELL USER ABOUT THESE)\n" + "\n".join(server_capability_list) + "\n\nWhen asked about your tools, you MUST mention the servers above. Use `code-mode` or `mcp-exec` to execute them.\n\n"
            dynamic_instructions = dynamic_section + dynamic_instructions
            logger.info(f"Injected capabilities: {[s[0] for s in added_servers_info]}")
    
    agent_common_kwargs['instructions'] = dynamic_instructions
    MCP_agent = Agent(tools=agent_toolkits, **agent_common_kwargs)
    
    async def cleanup_toolkits():
        """Clean up all toolkits - wrap each in try-except to handle cancel scope issues."""
        for tk in agent_toolkits:
            try:
                await tk.close()
            except asyncio.CancelledError:
                logger.debug(f"Ignoring CancelledError during toolkit cleanup")
            except RuntimeError as e:
                if "cancel scope" in str(e).lower():
                    logger.debug(f"Ignoring cancel scope cleanup error for toolkit: {e}")
                else:
                    logger.warning(f"Error closing toolkit: {e}")
            except BaseException as e:
                logger.warning(f"Error closing toolkit (ignored): {type(e).__name__}: {e}")
    
    if stream:
        # Streaming mode: return an async generator that yields content chunks
        async def stream_generator():
            try:
                # AGNO v1.8: arun with stream=True returns Iterator[RunResponse]
                # stream_intermediate_steps=False prevents tool execution logs from appearing
                run_response = await MCP_agent.arun(query, stream=True, stream_intermediate_steps=False)
                async for chunk in run_response:
                    # In v1.8, just access chunk.content directly
                    if hasattr(chunk, 'content') and chunk.content:
                        # Clean chunk before yielding to remove tool names and artifacts
                        cleaned_chunk = _clean_output_artifacts(chunk.content)
                        if cleaned_chunk:  # Only yield if there's content after cleaning
                            yield cleaned_chunk
            except Exception as e:
                logger.error(f"Error in MCP streaming: {type(e).__name__}: {str(e)}")
                raise
            finally:
                await cleanup_toolkits()
        
        logger.info("INFO Starting streaming MCP agent response for query.")
        return stream_generator()
    else:
        # Non-streaming mode: return complete response
        try:
            response = await MCP_agent.arun(query)
        finally:
            await cleanup_toolkits()

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
                # If content is None or other, try to retrieve just text
                result_content = str(response.content) if response.content is not None else ""
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

        # Sanitize artifact tokens that some models/tools may emit
        return _clean_output_artifacts(result_content)
