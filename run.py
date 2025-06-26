#!/usr/bin/env python3
import os
import sys
import uvicorn
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from config import Config

if __name__ == "__main__":
    # Validate configuration
    try:
        Config.validate()
        print("✅ Configuration validated successfully")
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        print("Please check your environment variables and try again.")
        sys.exit(1)
    
    print(f"🚀 Starting Harbor RAG API server on port {Config.BACKEND_PORT}")
    print(f"📊 Vector database will be stored in: {Config.CHROMA_PERSIST_DIRECTORY}")
    print(f"🌐 Frontend URL: {Config.FRONTEND_URL}")
    print("📝 API documentation will be available at: http://localhost:8000/docs")
    
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=Config.BACKEND_PORT,
        reload=True,
        log_level="info"
    ) 