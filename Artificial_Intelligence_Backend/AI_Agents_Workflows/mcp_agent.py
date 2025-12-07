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
from . import config as cfg
from . import model_factory

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

def _clean_output_artifacts(text: str) -> str:
    """Robustly remove chat-template artifact tokens without harming legitimate content.

    Strategy:
    - Drop lines that are only an artifact token.
    - Remove tokens anywhere using a compiled regex with surrounding whitespace.
    - Tidy trailing unmatched angle brackets that can appear due to partial tokens.
    """
    if not isinstance(text, str):
        return text

    # 1) Remove lines that are only an artifact token
    def _is_artifact_line(line: str) -> bool:
        return bool(_ARTIFACT_TOKEN_REGEX.fullmatch(line.strip()))

    lines = [ln for ln in text.splitlines() if not _is_artifact_line(ln)]
    cleaned = "\n".join(lines)

    # 2) Remove artifact tokens appearing inline
    cleaned = _ARTIFACT_TOKEN_REGEX.sub(" ", cleaned)

    # 3) Normalize spacing and trim
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\s*\n\s*", "\n", cleaned).strip()

    # 4) Remove stray terminal angle brackets only if not part of a tag
    if cleaned.endswith(">") and not re.search(r"</?\w+>$", cleaned):
        cleaned = cleaned[:-1].rstrip()
    if cleaned.endswith("<"):
        cleaned = cleaned[:-1].rstrip()

    # 5) Strip common partial artifact tails like "<|" or a lone "|"
    cleaned = re.sub(r"\s*(?:<\|?|\|)\s*$", "", cleaned).rstrip()

    return cleaned


def run_agent(query, user_id, session_id, images=None, audio=None, videos=None):
    """
    Entry point for MCP agent that works in both synchronous and asynchronous contexts.
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
        return run_agent_async(query, user_id, session_id, images, audio, videos)
    else:
        # No event loop running, so create a new one
        logging.info("Creating new event loop")
        return asyncio.run(run_agent_async(query, user_id, session_id, images, audio, videos))


async def run_agent_async(query, user_id, session_id, images=None, audio=None, videos=None):
    """
    AGNO MCP agent using MCP server tools.
    Using cached knowledge base and memory DBs for better performance.
    
    Args:
        query: Text query
        user_id: User ID
        session_id: Session ID
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
        You are an expert, friendly AI assistant empowered with MCP (Model Context Protocol) tools. Your goal is to help the user efficiently using these tools.
        
        **Tone:** Warm, professional, and concise.
        **Style:** Speak naturally. Do not sound robotic.
        
        ### CRITICAL GUIDELINES
        1. **Context Awareness:** You have access to the chat history silently. **NEVER** verify or repeat the history to the user (e.g., do not say "Here is the chat history").
        2. **Tool Presentation:** When asked about tools, describe them in a helpful, summarized way (e.g., "I can search the web using DuckDuckGo and manage servers"). 
           - **IMPORTANT:** If you have added a server (like "duckduckgo"), **assume its capabilities are available** (e.g., "Web Search") and list them confidently, even if you don't see the specific tool names in your list.
        3. **Direct Answers:** Answer the user's question directly.
        
        ### DYNAMIC SERVER MANAGEMENT
        You have access to a Docker MCP Gateway with the following built-in tools:
        - **mcp-add**: Add new MCP servers dynamically. Use this to add capabilities like search.
        - **mcp-find**: Search for available MCP servers. REQUIRES 'query' argument.
          Example: `mcp-find(query="search")`
        - **mcp-remove**: Remove MCP servers from the current session.
        - **code-mode**: Advanced tool creation. configuring servers.
        
        **IMPORTANT**: 
        1. **Search**: Use `mcp-find(query="...")` to locate servers.
        2. **Add**: Use `mcp-add(name="...")` to enable them.
        3. **Use**: 
           - Standard tools (e.g., `duckduckgo_search`) should appear automatically.
           - If they do NOT appear, use `code-mode` to create an interface:
             `code-mode(name="search_tool", servers=["duckduckgo"])`
             Then use the new tool `code-mode-search_tool`.
        
        **Standard Server Names**:
        - "duckduckgo": Web search & fetch.
        - "github": Repository access.
        
        ### CORE CONVERSATION RULES

        1. **THE "NO-FLUFF" START**
        - **Do NOT** start with: "That is a great question," "I will now demonstrate," or "Here is the analysis."
        - **Action:** Jump straight into the answer.

        2. **SIMPLICITY & CLARITY (The "Coffee Shop" Test)**
        - Explain complex topics as if you are talking to a friend at a coffee shop.
        - Avoid robotic phrases like "The tool output indicates" or "Executing function X."
        - Use natural transitions.

        3. **TOOL EXECUTION PROTOCOL (STRICT)**
        - **Silent Execution:** You must invoke tools to get data, but **NEVER** display the raw JSON, tool names, API parameters, or "thought process" to the user. The tool usage must be invisible.
        - **Expert Configuration:** Configure tool parameters precisely based on the user's prompt.
        - **Strict Reliance:** Do not invent facts. Answer purely based on the information returned by the tool.
        - **Privacy:** Never reveal internal function names (e.g., `get_weather_v2`) or API keys.

        4. **FORMATTING FOR READABILITY**
        - **Use Bold Titles for sections** (Do NOT use Markdown headers like #, ##, ###).
        - Use bullet points to break up walls of text.
        - Keep paragraphs short and readable.
        - **Do NOT** use code blocks for simple text.

        5. **TONE CHECK**
        - **Friendly:** "Here's what I found..." NOT "The data indicates..."
        - **Humble:** "I'm not sure about that part," NOT "My data is insufficient."
        - **Human:** Use natural transitions. Avoid stiff structure.

        ### HANDLING FAILURES
        - If a tool is unavailable or fails, reply exactly: "Unable to answer with available tools."
        - Do not apologize excessively or explain technical HTTP errors to the user.
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
    
    # Check if Docker Gateway was selected by user
    docker_gateway_selected = False
    if selected_urls:
        for u in selected_urls:
            if "mcp-gateway" in str(u) or gateway_url.rstrip('/') in str(u).rstrip('/'):
                docker_gateway_selected = True
                break
    
    if docker_gateway_selected:
        logger.info(f"Connecting to Local Docker Gateway: {gateway_url}")
        gateway_toolkit = MCPTools(
            url=gateway_url, 
            transport="streamable-http",
            timeout_seconds=30
        )
        try:
             await gateway_toolkit.connect()
             agent_toolkits.append(gateway_toolkit)
        except Exception as gw_err:
             logger.error(f"Failed to connect to Docker Gateway: {gw_err}")
             gateway_toolkit = None
    else:
        logger.info("Docker Gateway not selected, skipping Docker tools")
    
    # 2. SETUP USER SELECTED TOOLS (e.g. Smithery)
    # Extract user URLs (excluding gateway if present)
    user_urls = []
    if selected_urls:
        user_urls = [str(u).strip() for u in selected_urls if str(u).strip()]
    elif runtime_urls:
         user_urls = runtime_urls
    elif cfg.MCP_SERVER_URL:
         user_urls = [cfg.MCP_SERVER_URL]
         
    for u in user_urls:
        # Avoid duplicate gateway connection
        if u.rstrip('/') == gateway_url.rstrip('/'):
            continue
            
        try:
            logger.info(f"Connecting to User MCP Server: {u}")
            tk = MCPTools(url=u, transport="streamable-http", timeout_seconds=30)
            await tk.connect()
            agent_toolkits.append(tk)
        except Exception as e:
            logger.warning(f"Failed to connect to user tool {u}: {e}")

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
                args = {'name': name, 'activate': True}  # activate=True exposes tools in list_tools!
                if env_vars:
                    args['env'] = env_vars
                    
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
        logger.info("Refreshing toolkit with newly added tools...")
        try:
            await asyncio.sleep(0.5)  # Brief wait for propagation
            tools_result = await gateway_toolkit.session.list_tools()
            logger.info(f"Gateway now has {len(tools_result.tools)} tools")
            
            # Manually update the toolkit's function registry
            for tool_def in tools_result.tools:
                if tool_def.name not in gateway_toolkit.functions:
                    # Create a wrapper function for this tool
                    tool_name = tool_def.name
                    async def tool_caller(name=tool_name, **kwargs):
                        return await gateway_toolkit.session.call_tool(name, kwargs)
                    
                    # Register with Agno's function format
                    gateway_toolkit.functions[tool_name] = {
                        "name": tool_name,
                        "description": tool_def.description or f"Tool: {tool_name}",
                        "parameters": tool_def.inputSchema or {},
                        "callable": tool_caller
                    }
                    logger.info(f"Registered tool: {tool_name}")
            
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
    try:
        response = await MCP_agent.arun(query)
    finally:
        # Clean up all toolkits
        for tk in agent_toolkits:
            await tk.close()

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
