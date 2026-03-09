"""
server.py
FastAPI application exposing all Codebase AI Assistant endpoints.

Endpoints:
    POST /ingest/github    → Clone a GitHub repo and index it
    POST /ingest           → Index an already-local repository
    POST /ask              → Ask a question about the codebase
    POST /document         → Auto-generate docs for a file
    GET  /status/{repo}    → Check collection stats for a repo
    GET  /health           → Health check
    DELETE /index/{repo}   → Wipe a repo's index
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from loguru import logger
import sys

from utils.config import settings
from indexing.indexer import Indexer
from rag.generator import Generator
from indexing.vector_store import VectorStore
from ingestion.github_cloner import clone_repository


# ── Logger ─────────────────────────────────────────────────────────────────────
logger.remove()
logger.add(
    sys.stdout,
    level=settings.LOG_LEVEL,
    format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
)

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Codebase AI Assistant",
    description="AI-powered knowledge layer for software repositories.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response Models ──────────────────────────────────────────────────

class GithubIngestRequest(BaseModel):
    github_url: str = Field(..., description="GitHub repository URL")
    reindex: bool = Field(False, description="Force re-index even if already indexed")
    include_git_history: bool = Field(True, description="Also index git commit history")


class IngestRequest(BaseModel):
    repo_path: str
    repo_name: str
    reindex: bool = False
    include_git_history: bool = True


class IngestResponse(BaseModel):
    status: str
    repo_name: str
    github_url: Optional[str] = None
    files_loaded: int
    file_chunks: int
    git_chunks: int
    chunks_indexed: int
    total_in_collection: int


class AskRequest(BaseModel):
    repo_name: str
    query: str
    top_k: int = Field(5, ge=1, le=15)
    source_type: Optional[str] = None
    conversation_history: Optional[List[Dict]] = None


class AskResponse(BaseModel):
    answer: str
    sources: List[str]
    chunks_used: int
    repo_name: str
    query: str


class DocumentRequest(BaseModel):
    repo_name: str
    file_path: str


class DocumentResponse(BaseModel):
    file_path: str
    documentation: str
    chunks_used: int
    repo_name: str


class StatusResponse(BaseModel):
    collection_name: str
    repo_name: str
    total_chunks: int


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok", "model": settings.OPENAI_CHAT_MODEL}


@app.post("/ingest/github", response_model=IngestResponse, tags=["Ingestion"])
def ingest_github(request: GithubIngestRequest):
    """Clone a GitHub repo and index it end-to-end."""
    logger.info(f"GitHub ingest request: {request.github_url}")
    try:
        repo_name, local_path = clone_repository(
            github_url=request.github_url,
            force_reclone=request.reindex,
        )
        indexer = Indexer()
        result = indexer.index_repository(
            repo_path=local_path,
            repo_name=repo_name,
            reindex=request.reindex,
            include_git_history=request.include_git_history,
        )
        if result["status"] != "success":
            raise HTTPException(status_code=422, detail=f"Ingestion returned: {result['status']}")
        return IngestResponse(**result, github_url=request.github_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"GitHub ingest failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest", response_model=IngestResponse, tags=["Ingestion"])
def ingest_local(request: IngestRequest):
    """Index a repository already on the local filesystem."""
    try:
        indexer = Indexer()
        result = indexer.index_repository(
            repo_path=request.repo_path,
            repo_name=request.repo_name,
            reindex=request.reindex,
            include_git_history=request.include_git_history,
        )
        return IngestResponse(**result)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ask", response_model=AskResponse, tags=["Query"])
def ask_question(request: AskRequest):
    """Ask a natural language question about an indexed repository."""
    logger.info(f"Query | Repo: {request.repo_name} | '{request.query[:60]}'")
    try:
        generator = Generator(repo_name=request.repo_name)
        result = generator.answer(
            query=request.query,
            top_k=request.top_k,
            source_type=request.source_type,
            conversation_history=request.conversation_history,
        )
        return AskResponse(**result)
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/document", response_model=DocumentResponse, tags=["Documentation"])
def generate_documentation(request: DocumentRequest):
    """Auto-generate markdown documentation for a specific file."""
    try:
        generator = Generator(repo_name=request.repo_name)
        result = generator.generate_documentation(file_path=request.file_path)
        return DocumentResponse(**result)
    except Exception as e:
        logger.error(f"Doc generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status/{repo_name}", response_model=StatusResponse, tags=["System"])
def get_repo_status(repo_name: str):
    """Check how many chunks are indexed for a repo."""
    try:
        vs = VectorStore(repo_name=repo_name)
        info = vs.get_collection_info()
        return StatusResponse(**info)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/index/{repo_name}", tags=["System"])
def delete_index(repo_name: str):
    """Wipe the vector index for a repository."""
    try:
        vs = VectorStore(repo_name=repo_name)
        vs.delete_collection()
        return {"status": "deleted", "repo_name": repo_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))