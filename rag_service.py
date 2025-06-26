import os
import logging
from typing import List, Dict, Any
from llama_index.core import VectorStoreIndex, Settings
from llama_index.core.storage.storage_context import StorageContext
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.readers.web import SimpleWebPageReader
from llama_index.core.node_parser import SimpleNodeParser
import chromadb
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from config import Config

# Set up OpenAI API key in environment
import openai

logger = logging.getLogger(__name__)

class RAGService:
    def __init__(self):
        self.config = Config()
        self.config.validate()
        
        # Set OpenAI API key in environment (required for newer versions)
        os.environ["OPENAI_API_KEY"] = self.config.OPENAI_API_KEY
        
        # Initialize LlamaIndex settings with minimal parameters
        try:
            Settings.llm = OpenAI(model=self.config.LLM_MODEL)
            Settings.embed_model = OpenAIEmbedding(model=self.config.EMBED_MODEL)
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI models: {e}")
            # Fallback to default models if specific ones fail
            Settings.llm = OpenAI()
            Settings.embed_model = OpenAIEmbedding()
        
        # Initialize ChromaDB
        self.chroma_client = chromadb.PersistentClient(path=self.config.CHROMA_PERSIST_DIRECTORY)
        self.collection_name = "harbor_website"
        
        # Initialize vector store and index
        self.vector_store = None
        self.index = None
        self.query_engine = None
        
        self._setup_vector_store()
        
    def _setup_vector_store(self):
        """Initialize or load the vector store and index"""
        try:
            # Try to get existing collection
            chroma_collection = self.chroma_client.get_collection(self.collection_name)
            logger.info(f"Found existing collection: {self.collection_name}")
        except:
            # Create new collection if it doesn't exist
            chroma_collection = self.chroma_client.create_collection(self.collection_name)
            logger.info(f"Created new collection: {self.collection_name}")
        
        self.vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=self.vector_store)
        
        # Check if index already exists by checking if collection has documents
        if chroma_collection.count() > 0:
            logger.info("Loading existing index from vector store")
            self.index = VectorStoreIndex.from_vector_store(self.vector_store)
        else:
            logger.info("Creating new empty index")
            self.index = VectorStoreIndex([], storage_context=storage_context)
        
        self._setup_query_engine()
        
    def _setup_query_engine(self):
        """Setup the query engine with source tracking"""
        self.query_engine = self.index.as_query_engine(
            similarity_top_k=5,
            response_mode="tree_summarize"
        )
        
    def discover_urls(self, base_url: str, max_depth: int = 3) -> List[str]:
        """Discover URLs by crawling the website"""
        discovered_urls = set()
        to_visit = [(base_url, 0)]
        visited = set()
        
        while to_visit:
            url, depth = to_visit.pop(0)
            
            if url in visited or depth > max_depth:
                continue
                
            visited.add(url)
            
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    discovered_urls.add(url)
                    
                    # Parse HTML to find more links (only if not at max depth)
                    if depth < max_depth:
                        soup = BeautifulSoup(response.content, 'html.parser')
                        
                        # Find traditional <a href="..."> links
                        for link in soup.find_all('a', href=True):
                            href = link['href']
                            full_url = urljoin(url, href)
                            
                            # Only follow internal links
                            if urlparse(full_url).netloc == urlparse(base_url).netloc:
                                if full_url not in visited:
                                    to_visit.append((full_url, depth + 1))
                        
                        # Find JavaScript navigation: onclick="window.location.href='...'"
                        import re
                        for element in soup.find_all(attrs={"onclick": True}):
                            onclick = element.get('onclick', '')
                            # Match patterns like: window.location.href='file.html'
                            matches = re.findall(r"window\.location\.href\s*=\s*['\"]([^'\"]+)['\"]", onclick)
                            for match in matches:
                                full_url = urljoin(url, match)
                                # Only follow internal links
                                if urlparse(full_url).netloc == urlparse(base_url).netloc:
                                    if full_url not in visited:
                                        logger.info(f"Found JavaScript link: {full_url}")
                                        to_visit.append((full_url, depth + 1))
                                    
            except Exception as e:
                logger.warning(f"Failed to fetch {url}: {e}")
                
        return list(discovered_urls)
        
    def index_website(self, base_url: str = None) -> Dict[str, Any]:
        """Index the entire website into the vector store, starting from homepage but excluding it"""
        if base_url is None:
            base_url = self.config.BASE_URL
            
        logger.info(f"Starting to index website from: {base_url} (homepage will be excluded)")
        
        # Clear existing collection to avoid duplicates
        try:
            collection = self.chroma_client.get_collection(self.collection_name)
            # Delete all documents in the collection
            all_docs = collection.get()
            if all_docs.get("ids"):
                collection.delete(ids=all_docs["ids"])
                logger.info(f"Cleared {len(all_docs['ids'])} existing documents from collection")
        except Exception as e:
            logger.info(f"No existing collection to clear: {e}")
        
        # Recreate the index
        self._setup_vector_store()
        
        # Discover all URLs starting from the homepage
        urls = self.discover_urls(base_url, self.config.MAX_DEPTH)
        logger.info(f"Discovered {len(urls)} URLs total")
        
        # Remove the homepage and its variations from the list of URLs to index
        def is_homepage_url(url, base_url):
            """Check if a URL represents the homepage (root or index files)"""
            from urllib.parse import urlparse, urljoin
            
            base_parsed = urlparse(base_url)
            url_parsed = urlparse(url)
            
            # Must be same scheme and netloc
            if base_parsed.scheme != url_parsed.scheme or base_parsed.netloc != url_parsed.netloc:
                return False
            
            # Get the path part
            path = url_parsed.path.lower().strip('/')
            
            # Check for various homepage representations
            homepage_paths = [
                '',  # root path
                'index.html',
                'index.htm', 
                'index.php',
                'home.html',
                'home.htm',
                'default.html',
                'default.htm'
            ]
            
            return path in homepage_paths
        
        urls_to_index = [url for url in urls if not is_homepage_url(url, base_url)]
        excluded_urls = [url for url in urls if is_homepage_url(url, base_url)]
        
        logger.info(f"Excluding {len(excluded_urls)} homepage URLs from indexing:")
        for excluded_url in excluded_urls:
            logger.info(f"  - {excluded_url}")
        logger.info(f"Will index {len(urls_to_index)} URLs (excluding homepage variations)")
        
        if not urls_to_index:
            return {"success": False, "message": "No URLs to index after excluding homepage", "indexed_count": 0}
        
        # Load documents using SimpleWebPageReader
        reader = SimpleWebPageReader(html_to_text=True)
        
        successfully_indexed = 0
        failed_urls = []
        
        for url in urls_to_index:
            try:
                logger.info(f"Indexing: {url}")
                documents = reader.load_data([url])
                
                if documents:
                    # Add metadata to documents
                    for doc in documents:
                        doc.metadata.update({
                            "source_url": url,
                            "source_type": "web_page"
                        })
                    
                    # Parse documents into nodes
                    parser = SimpleNodeParser.from_defaults(
                        chunk_size=self.config.CHUNK_SIZE,
                        chunk_overlap=self.config.CHUNK_OVERLAP
                    )
                    nodes = parser.get_nodes_from_documents(documents)
                    
                    # Add nodes to index
                    self.index.insert_nodes(nodes)
                    successfully_indexed += 1
                    logger.info(f"Successfully indexed: {url}")
                else:
                    logger.warning(f"No content extracted from: {url}")
                    failed_urls.append(url)
                    
            except Exception as e:
                logger.error(f"Failed to index {url}: {e}")
                failed_urls.append(url)
        
        # Refresh query engine after indexing
        self._setup_query_engine()
        
        return {
            "success": True,
            "message": f"Indexed {successfully_indexed} out of {len(urls_to_index)} URLs (homepage variations excluded)",
            "indexed_count": successfully_indexed,
            "total_urls": len(urls_to_index),
            "failed_urls": failed_urls
        }
        
    def query(self, question: str) -> Dict[str, Any]:
        """Query the indexed content and return response with sources"""
        if not self.query_engine:
            return {
                "success": False,
                "message": "RAG system not initialized. Please index content first.",
                "response": "",
                "sources": []
            }
        
        try:
            # Query the index
            response = self.query_engine.query(question)
            
            # Extract sources from the response
            sources = []
            if hasattr(response, 'source_nodes') and response.source_nodes:
                for node in response.source_nodes:
                    if hasattr(node.node, 'metadata') and 'source_url' in node.node.metadata:
                        source_info = {
                            "url": node.node.metadata['source_url'],
                            "score": float(node.score) if hasattr(node, 'score') else 0.0,
                            "text_snippet": node.node.text[:200] + "..." if len(node.node.text) > 200 else node.node.text
                        }
                        sources.append(source_info)
            
            # Remove duplicate sources based on URL
            unique_sources = []
            seen_urls = set()
            for source in sources:
                if source['url'] not in seen_urls:
                    unique_sources.append(source)
                    seen_urls.add(source['url'])
            
            # Sort by relevance score (descending)
            unique_sources.sort(key=lambda x: x['score'], reverse=True)
            
            return {
                "success": True,
                "response": str(response),
                "sources": unique_sources,
                "question": question
            }
            
        except Exception as e:
            logger.error(f"Error querying RAG system: {e}")
            return {
                "success": False,
                "message": f"Error processing query: {str(e)}",
                "response": "",
                "sources": []
            }
            
    def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about the indexed content"""
        try:
            collection = self.chroma_client.get_collection(self.collection_name)
            doc_count = collection.count()
            
            return {
                "success": True,
                "document_count": doc_count,
                "collection_name": self.collection_name,
                "is_ready": doc_count > 0
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error getting index stats: {str(e)}",
                "document_count": 0,
                "is_ready": False
            }
    
    def get_documents(self, limit: int = 10, offset: int = 0) -> Dict[str, Any]:
        """Get stored documents with their content and metadata"""
        try:
            collection = self.chroma_client.get_collection(self.collection_name)
            
            # Get documents with pagination - ids are included by default
            result = collection.get(
                limit=limit,
                offset=offset,
                include=["documents", "metadatas"]
            )
            
            documents = []
            if result and result.get("documents"):
                for i, doc_text in enumerate(result["documents"]):
                    doc_id = result["ids"][i] if result.get("ids") else f"doc_{i}"
                    metadata = result["metadatas"][i] if result.get("metadatas") else {}
                    
                    # Create text snippet (first 200 chars)
                    text_snippet = doc_text[:200] + "..." if len(doc_text) > 200 else doc_text
                    
                    documents.append({
                        "id": doc_id,
                        "source_url": metadata.get("source_url", "unknown"),
                        "text_snippet": text_snippet,
                        "full_text": doc_text,
                        "metadata": metadata
                    })
            
            total_count = collection.count()
            
            return {
                "success": True,
                "documents": documents,
                "total_count": total_count
            }
            
        except Exception as e:
            logger.error(f"Error getting documents: {e}")
            return {
                "success": False,
                "message": f"Error getting documents: {str(e)}",
                "documents": [],
                "total_count": 0
            } 