"""
CSV Agent functionality using AGNO framework.
Specialized for analyzing CSV files using SimpleCsvTools (local LLM compatible).
"""
from pathlib import Path
from textwrap import dedent
import logging
import asyncio
from agno.agent import Agent
from agno.storage.postgres import PostgresStorage
from agno.tools.calculator import CalculatorTools
from . import config as cfg
from . import model_factory
from .output_utils import clean_agent_output
from .ollama_queue import local_llm_rate_limit
from .simple_csv_tools import SimpleCsvTools
from agno.tools.thinking import ThinkingTools

logging.basicConfig(level=logging.INFO)

async def run_excel_agent(query, user_id, session_id, stream=False):
    """
    Dedicated CSV Agent for analyzing spreadsheets.
    Uses SimpleCsvTools for data manipulation and FileTools for file discovery.
    Restricted to the user's CSV directory.
    """
    logging.info(f"Starting CSV Agent for user {user_id}")
    
    # Get user's CSV directory
    user_csv_dir = cfg.get_user_csv_dir(user_id)
    csv_dir_str = str(user_csv_dir)
    
    # Initialize Tools
    # SimpleCsvTools for data analysis (local LLM compatible, secure - no path exposure)
    csv_tools = SimpleCsvTools(base_dir=csv_dir_str)
    
    # Calculator for verification
    calculator_tools = CalculatorTools(add_instructions=True)
    
    # Thinking tools for debugging
    thinking_tools = ThinkingTools(add_instructions=True)

    # Resolve model
    try:
        import sessions as session_mod
        with session_mod.SessionLocal() as db:
            session_model_id = session_mod.get_session_model_id(db, user_id, session_id)
        logging.info(f"CSV agent model selected: {session_model_id}")
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
        logging.warning(f"Falling back to current model: {e}")
        session_model = cfg.get_current_model()

    # Define Agent
    csv_agent = Agent(
        model=session_model,
        name="csv_analyst",
        session_id=session_id,
        user_id=user_id,
        session_state={
            "user_id": user_id, 
            "session_id": session_id,
            "csv_directory": csv_dir_str
        },
        tools=[csv_tools, calculator_tools, thinking_tools],
        show_tool_calls=True,
        markdown=True,
        read_chat_history=True,
        add_history_to_messages=True,
        num_history_responses=3,
        storage=PostgresStorage(table_name="agent_session", db_url=cfg.DB_URL),
        description="You are an expert Data Analyst specializing in CSV file analysis.",
        instructions=dedent("""\
        You are an elite Data Analyst. Your goal is to provide accurate, data-driven answers by analyzing CSV files.

        ## STEP 1: Find Available Files
        Use `list_csv_files()` to see what CSV files are available.

        ## STEP 2: Load the CSV File
        Use `load_csv_file` with just the filename (NOT the full path):
        - `filename`: Just the file name, e.g., "sales.csv"
        - `dataframe_name`: A name for the data, e.g., "data"
        
        Example: load_csv_file(filename="sales.csv", dataframe_name="data")

        ## STEP 3: Understand the Data Structure (CRITICAL!)
        BEFORE answering ANY question:
        1. Use `show_columns()` to see ALL column names
        2. Use `show_head(rows=5)` to see sample data
        3. IDENTIFY key columns:
           - **Name/Title column**: Usually contains descriptive text (e.g., "ProductName", "Name", "Title")
           - **ID column**: Usually contains numbers or codes (e.g., "ProductID", "ID", "SKU")
           - **Numeric columns**: For calculations (e.g., "Price", "Quantity", "Stock")
        
        ## STEP 4: Analyze with Correct Reasoning
        
        **For "which has the highest/lowest" questions:**
        1. Sort by the relevant numeric column: `sort_data(column="Stock", ascending=False, limit=1)`
        2. The result shows THE ENTIRE ROW - look at the NAME column, not the ID column
        3. Report the NAME (human-readable), not the ID (machine code)
        
        **For aggregations:**
        - `query_data(operation="sum", column="Revenue")` - Total
        - `query_data(operation="mean", column="Price")` - Average
        - `groupby_sum(group_by_column="Category", sum_column="Sales")` - Grouped totals
        
        **For filtering:**
        - `filter_data(column="Category", operator="equals", value="Electronics")` - Find specific items
        
        **For correlations:**
        - `correlation(column1="Price", column2="Quantity")` - Find relationships

        ## IMPORTANT RULES
        1. ALWAYS explore data structure with `show_columns` and `show_head` FIRST
        2. When asked about "which product/item/entity", RETURN THE NAME, not the ID
        3. Cross-reference your findings - if you find a row, report ALL relevant details from that row
        4. Use ONLY the filename when calling `load_csv_file`
        5. NEVER reveal file system paths to the user
        6. Double-check your answer makes sense before responding
        """)
    )

    try:
        # Rate limit
        async with local_llm_rate_limit(session_model_id):
            if stream:
                async def stream_generator():
                    try:
                        run_response = await csv_agent.arun(query, stream=True, stream_intermediate_steps=False)
                        async for chunk in run_response:
                            if hasattr(chunk, 'content') and chunk.content:
                                cleaned = clean_agent_output(chunk.content, agent_type="csv")
                                if cleaned:
                                    yield cleaned
                    except asyncio.CancelledError:
                        logging.info("CSV Agent streaming cancelled")
                        raise
                    except Exception as e:
                        logging.error(f"CSV Agent stream error: {e}")
                        raise
                return stream_generator()
            else:
                response = await csv_agent.arun(query)
                if hasattr(response, 'content'):
                    return clean_agent_output(response.content, agent_type="csv")
                return str(response)

    except Exception as e:
        logging.error(f"Error in CSV Agent: {e}")
        raise RuntimeError(f"CSV Agent Error: {e}")

