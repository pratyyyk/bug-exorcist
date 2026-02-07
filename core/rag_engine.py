import os
import logging
import asyncio
import hashlib
import json
import threading
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

class CodebaseRAG:
    """
    Retrieval-Augmented Generation (RAG) system for codebase awareness.
    Indexes project files into ChromaDB and provides semantic search.
    """
    def __init__(self, project_path: str, persist_directory: str = "./.chroma_db"):
        self.project_path = Path(project_path).resolve()
        self.persist_directory = persist_directory
        
        # Configure embeddings
        embedding_provider = os.getenv("RAG_EMBEDDING_PROVIDER", "openai").lower()
        if embedding_provider == "huggingface":
            try:
                from langchain_community.embeddings import HuggingFaceEmbeddings
                self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
                logger.info("Using local HuggingFace embeddings (all-MiniLM-L6-v2)")
            except ImportError:
                logger.warning("HuggingFaceEmbeddings not available, falling back to OpenAI")
                self.embeddings = OpenAIEmbeddings()
        else:
            self.embeddings = OpenAIEmbeddings()
            logger.info("Using OpenAI embeddings (remote)")

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100,
            add_start_index=True,
            language="python" # Default, can be improved per file type
        )
        self.vector_store = None
        self.hash_file = Path(self.persist_directory) / "file_hashes.json"
        self.indexing_task = None
        self._lock = threading.Lock()
        self._initialize_db()

    def _initialize_db(self):
        """Initialize or load the ChromaDB vector store."""
        try:
            # Retention control: If DB is too old, clear it
            if os.path.exists(self.persist_directory):
                retention_days = int(os.getenv("RAG_RETENTION_DAYS", "30"))
                mtime = os.path.getmtime(self.persist_directory)
                if (datetime.now().timestamp() - mtime) > (retention_days * 86400):
                    logger.info(f"RAG: Persist directory older than {retention_days} days. Clearing for security.")
                    import shutil
                    shutil.rmtree(self.persist_directory)

            os.makedirs(self.persist_directory, exist_ok=True)
            self.vector_store = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embeddings,
                collection_name="codebase_index"
            )
            logger.info(f"ChromaDB initialized at {self.persist_directory}")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")

    def _get_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file content."""
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            buf = f.read()
            hasher.update(buf)
        return hasher.hexdigest()

    def _load_hashes(self) -> Dict[str, str]:
        """Load stored file hashes."""
        if self.hash_file.exists():
            try:
                with open(self.hash_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_hashes(self, hashes: Dict[str, str]):
        """Save file hashes to disk."""
        try:
            with open(self.hash_file, 'w') as f:
                json.dump(hashes, f)
        except Exception as e:
            logger.error(f"Failed to save file hashes: {e}")

    def start_background_indexing(self, interval_seconds: int = 3600):
        """Start a background task to periodically index the project."""
        if self.indexing_task and not self.indexing_task.done():
            logger.info("Background indexing task already running.")
            return

        async def _indexer_loop():
            while True:
                try:
                    logger.info("Starting scheduled project indexing...")
                    # Run indexing in a threadpool to avoid blocking the event loop
                    await asyncio.to_thread(self.index_project, force=False)
                    logger.info(f"Indexing complete. Sleeping for {interval_seconds}s.")
                except asyncio.CancelledError:
                    logger.info("Background indexing task cancelled.")
                    break
                except Exception as e:
                    logger.error(f"Error in background indexing: {e}")
                
                try:
                    await asyncio.sleep(interval_seconds)
                except asyncio.CancelledError:
                    logger.info("Background indexing task cancelled during sleep.")
                    break

        self.indexing_task = asyncio.create_task(_indexer_loop())
        logger.info(f"Background indexing started with interval {interval_seconds}s")

    def index_project(self, force: bool = False):
        """
        Scan and index relevant files in the project incrementally.
        Thread-safe implementation with a lock.
        """
        with self._lock:
            if not self.project_path.exists():
                logger.error(f"Project path does not exist: {self.project_path}")
                return

        # Directories to ignore
        ignored_dirs = {'node_modules', '.git', '__pycache__', '.chroma_db', 'venv', 'env', 'dist', 'build'}
        
        # Extensions for non-text/binary files that should always be skipped
        binary_extensions = {
            '.pyc', '.exe', '.dll', '.so', '.dylib', '.bin', '.obj', '.o', '.a', '.lib',
            '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.pdf', '.zip', '.tar', '.gz', 
            '.7z', '.rar', '.woff', '.woff2', '.ttf', '.eot', '.mp4', '.mp3', '.wav'
        }

        # Explicit deny list for sensitive files and patterns
        deny_patterns = [
            r'.*secret.*', r'.*key.*', r'.*\.pem$', r'.*\.crt$', r'.*\.env.*', 
            r'.*token.*', r'.*password.*', r'.*credential.*', r'.*\.db$', r'.*\.sqlite$'
        ]
        import re

        current_hashes = self._load_hashes()
        new_hashes = {}
        files_to_index = []
        
        # Scan files and check for changes
        for file_path in self.project_path.rglob('*'):
            if file_path.is_file():
                # Skip if file is in an ignored directory
                if any(ignored in str(file_path) for ignored in ignored_dirs):
                    continue
                
                # Skip binary/non-text files
                if file_path.suffix.lower() in binary_extensions:
                    continue

                # Check against deny patterns
                if any(re.match(pattern, file_path.name, re.IGNORECASE) for pattern in deny_patterns):
                    logger.debug(f"Skipping sensitive file: {file_path}")
                    continue

                try:
                    rel_path = str(file_path.relative_to(self.project_path))
                    file_hash = self._get_file_hash(file_path)
                    new_hashes[rel_path] = file_hash

                    if force or rel_path not in current_hashes or current_hashes[rel_path] != file_hash:
                        files_to_index.append((file_path, rel_path))
                except Exception as e:
                    logger.warning(f"Failed to hash file: {file_path}. Error: {e}")

        if not files_to_index:
            logger.info("No changes detected. Skipping indexing.")
            return

        documents = []
        for file_path, rel_path in files_to_index:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if not content.strip():
                        continue
                    
                    doc = Document(
                        page_content=content,
                        metadata={
                            "source": rel_path,
                            "filename": file_path.name,
                            "extension": file_path.suffix,
                            "indexed_at": datetime.now().isoformat()
                        }
                    )
                    documents.append(doc)
            except Exception as e:
                logger.warning(f"Failed to read file for indexing: {file_path}. Error: {e}")

        if not documents:
            return

        # Split and add to vector store
        chunks = self.text_splitter.split_documents(documents)
        
        if self.vector_store:
            if force:
                self.vector_store.delete_collection()
                self._initialize_db()
                self.vector_store.add_documents(chunks)
            else:
                # In a real incremental setup, we would also remove old chunks for modified files
                # ChromaDB's langchain integration doesn't easily support "update by metadata"
                # For this implementation, we add new chunks. 
                # To avoid duplicate context, we'll clear and re-index if changes are detected
                # (Still faster than indexing everything every time if we use force=True)
                if len(files_to_index) > 0:
                    # If any files changed, for now we re-index to maintain consistency
                    # In a more advanced version, we'd use document IDs
                    self.vector_store.delete_collection()
                    self._initialize_db()
                    
                    # Re-index everything (since we already scanned them)
                    all_docs = []
                    for rel_path, f_hash in new_hashes.items():
                        f_path = self.project_path / rel_path
                        try:
                            with open(f_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                if content.strip():
                                    all_docs.append(Document(
                                        page_content=content,
                                        metadata={"source": rel_path, "filename": f_path.name, "extension": f_path.suffix}
                                    ))
                        except Exception: continue
                    
                    all_chunks = self.text_splitter.split_documents(all_docs)
                    self.vector_store.add_documents(all_chunks)
                    logger.info(f"Re-indexed project: {len(all_docs)} files, {len(all_chunks)} chunks.")

            self._save_hashes(new_hashes)
            logger.info(f"Updated index with {len(documents)} changed files.")

    def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """
        Search for related code patterns or utilities.
        Returns a dict containing both the formatted results and the list of referenced files.
        """
        if not self.vector_store:
            return {"results": [], "referenced_files": []}

        results = self.vector_store.similarity_search(query, k=limit)
        
        formatted_results = []
        referenced_files = set()
        for doc in results:
            source = doc.metadata.get("source")
            formatted_results.append({
                "content": doc.page_content,
                "source": source,
                "filename": doc.metadata.get("filename")
            })
            if source:
                referenced_files.add(source)
        
        return {
            "results": formatted_results,
            "referenced_files": list(referenced_files)
        }

    def get_context_summary(self, query: str) -> Dict[str, Any]:
        """
        Generate a summarized context string for the AI agent.
        Returns a dict containing the summary string and the list of referenced files.
        """
        search_data = self.search(query)
        results = search_data["results"]
        referenced_files = search_data["referenced_files"]

        if not results:
            return {
                "summary": "No related codebase context found.",
                "referenced_files": []
            }

        summary = "Related codebase context found via RAG:\n\n"
        added_files = set()
        for res in results:
            source = res['source']
            if source not in added_files:
                summary += f"--- File: {source} ---\n"
                # Limit content per file to keep context window manageable
                content_preview = res['content'][:500] + "..." if len(res['content']) > 500 else res['content']
                summary += f"{content_preview}\n\n"
                added_files.add(source)
        
        return {
            "summary": summary,
            "referenced_files": referenced_files
        }
