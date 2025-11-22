"""
Main entry point for the AI Teacher Assistant application.
"""
import os
import uvicorn

def run_fastapi():
    """Run the FastAPI service"""
    API_HOST = os.getenv("API_HOST", "127.0.0.1")
    API_PORT = int(os.getenv("API_PORT", 8000))
    API_RELOAD = bool(int(os.getenv("API_RELOAD", 1)))

    app_env = os.getenv("APP_ENV")
    if not app_env:
        os.environ["APP_ENV"] = "production" if not API_RELOAD else "development"
        app_env = os.environ["APP_ENV"]

    print(f"Starting AI Teacher Assistant API on http://{API_HOST}:{API_PORT}")
    print(f"API documentation available at http://{API_HOST}:{API_PORT}/docs")
    print(f"Environment: {app_env}")

    uvicorn.run(
        "api:app",
        host=API_HOST,
        port=API_PORT,
        reload=API_RELOAD
    )

if __name__ == "__main__":
    run_fastapi()
