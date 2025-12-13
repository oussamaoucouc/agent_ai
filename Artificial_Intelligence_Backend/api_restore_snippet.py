
# LLM QUERY (Direct JSON)
@app.post("/query_direct", response_model=QueryResponse)
async def query_direct(request: QueryRequest, http_request: Request):
    key = f"{request.user_id}:{request.session_id}"
    active_tasks[key] = asyncio.current_task()
    
    try:
        # Auth check
        token_payload = get_user_from_auth_header(http_request.headers.get("Authorization"))
        if not token_payload:
            raise HTTPException(status_code=401, detail="Unauthorized")
        uid = token_payload.get("uid")

        with sessions.SessionLocal() as db:
            s = db.query(sessions.SessionDB).filter(sessions.SessionDB.id == request.session_id, sessions.SessionDB.user_id == uid).first()
            if not s:
                raise HTTPException(status_code=404, detail="Session not found")

        # Run RAG agent non-streaming
        response_text = await run_rag_agent(request.query, uid, request.session_id)
        
        return QueryResponse(
            user_id=request.user_id,
            session_id=request.session_id,
            response=response_text
        )
    except Exception as e:
        import traceback
        logging.error(f"Error in query_direct: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        active_tasks.pop(key, None)
