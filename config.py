import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
    BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))
    CHROMA_PERSIST_DIRECTORY = os.getenv("CHROMA_PERSIST_DIRECTORY", "./chroma_db")
    
    # LlamaIndex settings
    EMBED_MODEL = "text-embedding-ada-002"
    LLM_MODEL = "gpt-3.5-turbo"
    CHUNK_SIZE = 512
    CHUNK_OVERLAP = 50
    
    # Website to crawl
    BASE_URL = "http://localhost:3000"  # This will be the frontend URL
    MAX_DEPTH = 3  # How deep to crawl
    
    @classmethod
    def validate(cls):
        if not cls.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        return True 