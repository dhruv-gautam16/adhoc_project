"""
generator.py
Takes a developer query + retrieved context chunks and calls GPT-4o
to generate a clear, accurate, and grounded answer.
"""

from typing import List, Dict, Optional
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log
from loguru import logger
import logging

from utils.config import settings
from rag.retriever import Retriever


# System prompt that defines the AI assistant's persona and behavior
SYSTEM_PROMPT = """You are an expert AI assistant embedded in a software development team.
You have deep knowledge of the team's codebase, architecture, and git history.

Your job is to help developers by:
- Answering questions about how the code works
- Explaining design decisions and architectural choices
- Summarizing modules, functions, and APIs in plain language
- Helping new developers onboard quickly
- Identifying which files or functions are relevant to a given task

Always base your answers on the provided code context. If the context doesn't contain enough
information to answer confidently, say so clearly and suggest where the developer might look.

Be concise, specific, and developer-friendly. Use code references when helpful.
Format code snippets with markdown code blocks."""


class Generator:
    def __init__(self, repo_name: str):
        self.repo_name = repo_name
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_CHAT_MODEL
        self.retriever = Retriever(repo_name=repo_name)
        logger.info(f"Generator initialized | Model: {self.model} | Repo: {repo_name}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _call_llm(self, messages: List[Dict]) -> str:
        """Make the OpenAI chat completion call with retry logic."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,        # Lower = more factual, less creative
            max_tokens=1500,
        )
        return response.choices[0].message.content.strip()

    def answer(
        self,
        query: str,
        top_k: int = 5,
        source_type: Optional[str] = None,
        conversation_history: Optional[List[Dict]] = None,
    ) -> Dict:
        """
        Full RAG pipeline: retrieve relevant chunks → build prompt → call GPT-4o.

        Args:
            query: The developer's question
            top_k: Number of context chunks to retrieve
            source_type: Optional filter ('git_commit' for history-only search)
            conversation_history: Optional prior messages for multi-turn chat
                                  Format: [{"role": "user"/"assistant", "content": "..."}]

        Returns:
            Dict with: answer, sources (list of file paths), chunks_used
        """
        logger.info(f"Answering query for repo '{self.repo_name}': '{query[:80]}'")

        # ── Step 1: Retrieve relevant chunks ───────────────────────────────
        retrieved_chunks = self.retriever.retrieve(
            query=query,
            top_k=top_k,
            source_type=source_type,
        )
        context = self.retriever.format_context(retrieved_chunks)

        # ── Step 2: Build the messages array ───────────────────────────────
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Inject prior conversation turns (multi-turn support)
        if conversation_history:
            messages.extend(conversation_history[-6:])  # Last 3 turns max to save tokens

        # Final user message with context injected
        user_message = (
            f"Here is the relevant code context from the repository '{self.repo_name}':\n\n"
            f"{context}\n\n"
            f"---\n\n"
            f"Developer Question: {query}"
        )
        messages.append({"role": "user", "content": user_message})

        # ── Step 3: Call the LLM ───────────────────────────────────────────
        answer_text = self._call_llm(messages)

        # ── Step 4: Collect source references ─────────────────────────────
        sources = list({
            chunk["metadata"].get("relative_path", "unknown")
            for chunk in retrieved_chunks
        })

        result = {
            "answer": answer_text,
            "sources": sources,
            "chunks_used": len(retrieved_chunks),
            "repo_name": self.repo_name,
            "query": query,
        }

        logger.info(f"Answer generated | Sources: {sources}")
        return result

    def generate_documentation(self, file_path: str) -> Dict:
        """
        Special mode: generate documentation for a specific file.
        Retrieves chunks from that file and asks GPT-4o to write docs.
        """
        doc_query = f"Explain what the file {file_path} does, its purpose, key functions, and how it fits into the overall project."

        retrieved_chunks = self.retriever.retrieve(query=doc_query, top_k=8)

        # Filter to only chunks from the requested file
        file_chunks = [
            c for c in retrieved_chunks
            if file_path in c["metadata"].get("relative_path", "")
        ]

        if not file_chunks:
            file_chunks = retrieved_chunks  # Fallback to all if no exact match

        context = self.retriever.format_context(file_chunks)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Generate comprehensive documentation for the following code file: `{file_path}`\n\n"
                    f"Code Context:\n\n{context}\n\n"
                    "Include:\n"
                    "1. **Overview**: What this file does and its role in the project\n"
                    "2. **Key Functions/Classes**: Brief description of each\n"
                    "3. **Dependencies**: What it imports or depends on\n"
                    "4. **Usage Example**: How a developer would use this\n"
                    "5. **Notes**: Any important design decisions or gotchas\n"
                )
            }
        ]

        doc_text = self._call_llm(messages)

        return {
            "file_path": file_path,
            "documentation": doc_text,
            "chunks_used": len(file_chunks),
            "repo_name": self.repo_name,
        }