from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import logging
import asyncio
from contextlib import asynccontextmanager

from rag_service import RAGService
from config import Config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global RAG service instance
rag_service = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global rag_service
    logger.info("Initializing RAG service...")
    try:
        rag_service = RAGService()
        logger.info("RAG service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize RAG service: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")

app = FastAPI(
    title="Harbor RAG API",
    description="RAG-powered Q&A system for The Harbor website",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[Config.FRONTEND_URL, "http://localhost:3000"],  # Add your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class QueryRequest(BaseModel):
    question: str
    model: Optional[str] = "gpt-3.5-turbo"  # For compatibility with existing frontend
    messages: Optional[List[Dict[str, str]]] = None  # For compatibility

class QueryResponse(BaseModel):
    success: bool
    response: str
    sources: List[Dict[str, Any]]
    question: str
    message: Optional[str] = None

class IndexRequest(BaseModel):
    base_url: Optional[str] = None

class IndexResponse(BaseModel):
    success: bool
    message: str
    indexed_count: int
    total_urls: Optional[int] = None
    failed_urls: Optional[List[str]] = None

class StatsResponse(BaseModel):
    success: bool
    document_count: int
    collection_name: str
    is_ready: bool
    message: Optional[str] = None

class DocumentInfo(BaseModel):
    id: str
    source_url: str
    text_snippet: str
    full_text: str
    metadata: Dict[str, Any]

class DocumentsResponse(BaseModel):
    success: bool
    documents: List[DocumentInfo]
    total_count: int
    message: Optional[str] = None

class DiscoverResponse(BaseModel):
    success: bool
    urls: List[str]
    total_count: int
    message: Optional[str] = None

@app.get("/")
async def root():
    return {"message": "Harbor RAG API is running"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    global rag_service
    if rag_service is None:
        raise HTTPException(status_code=503, detail="RAG service not initialized")
    
    stats = rag_service.get_index_stats()
    return {
        "status": "healthy",
        "rag_ready": stats["is_ready"],
        "document_count": stats["document_count"]
    }

@app.post("/api/chat", response_model=QueryResponse)
async def chat(request: QueryRequest):
    """
    Main chat endpoint that's compatible with the existing frontend.
    Handles both the new question format and the OpenAI-compatible format.
    """
    global rag_service
    if rag_service is None:
        raise HTTPException(status_code=503, detail="RAG service not initialized")
    
    # Extract question from either direct question field or messages array
    question = request.question
    if not question and request.messages:
        # Find the last user message
        for msg in reversed(request.messages):
            if msg.get("role") == "user":
                question = msg.get("content", "")
                break
    
    if not question:
        raise HTTPException(status_code=400, detail="No question provided")
    
    logger.info(f"Processing question: {question}")
    
    try:
        result = rag_service.query(question)
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("message", "Query failed"))
        
        return QueryResponse(
            success=True,
            response=result["response"],
            sources=result["sources"],
            question=result["question"]
        )
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/index", response_model=IndexResponse)
async def index_website(request: IndexRequest, background_tasks: BackgroundTasks):
    """
    Index the website content. Can be run in the background.
    """
    global rag_service
    if rag_service is None:
        raise HTTPException(status_code=503, detail="RAG service not initialized")
    
    try:
        # Run indexing in background for better UX
        def run_indexing():
            return rag_service.index_website(request.base_url)
        
        # For now, run synchronously. In production, you might want to use background tasks
        result = run_indexing()
        
        return IndexResponse(
            success=result["success"],
            message=result["message"],
            indexed_count=result["indexed_count"],
            total_urls=result.get("total_urls"),
            failed_urls=result.get("failed_urls")
        )
        
    except Exception as e:
        logger.error(f"Error in index endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats", response_model=StatsResponse)
async def get_stats():
    """
    Get statistics about the indexed content
    """
    global rag_service
    if rag_service is None:
        raise HTTPException(status_code=503, detail="RAG service not initialized")
    
    try:
        result = rag_service.get_index_stats()
        
        return StatsResponse(
            success=result["success"],
            document_count=result["document_count"],
            collection_name=result["collection_name"],
            is_ready=result["is_ready"],
            message=result.get("message")
        )
        
    except Exception as e:
        logger.error(f"Error in stats endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/documents", response_model=DocumentsResponse)
async def get_documents(limit: int = 10, offset: int = 0):
    """
    Get stored documents with their content and metadata
    """
    global rag_service
    if rag_service is None:
        raise HTTPException(status_code=503, detail="RAG service not initialized")
    
    try:
        result = rag_service.get_documents(limit=limit, offset=offset)
        
        return DocumentsResponse(
            success=result["success"],
            documents=result["documents"],
            total_count=result["total_count"],
            message=result.get("message")
        )
        
    except Exception as e:
        logger.error(f"Error in documents endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/discover")
async def discover_urls(base_url: str = "http://localhost:3000"):
    """
    Discover URLs that would be crawled (without indexing them)
    """
    global rag_service
    if rag_service is None:
        raise HTTPException(status_code=503, detail="RAG service not initialized")
    
    try:
        urls = rag_service.discover_urls(base_url, rag_service.config.MAX_DEPTH)
        
        return DiscoverResponse(
            success=True,
            urls=urls,
            total_count=len(urls)
        )
        
    except Exception as e:
        logger.error(f"Error in discover endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate-questions")
async def generate_questions():
    """
    Generate related questions - keeping this for compatibility with frontend
    """
    # This could be enhanced to use RAG to generate contextual questions
    # For now, return some default questions
    default_questions = [
        "What are the main points discussed in this article?",
        "How do recent economic changes affect consumers?",
        "Can you summarize the key findings?"
    ]
    
    return {
        "questions": default_questions,
        "success": True
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=Config.BACKEND_PORT) 