"""
file_parser.py
Takes raw file content and splits it into meaningful chunks
suitable for embedding and retrieval.
"""

import re
from typing import List, Dict
from loguru import logger

from utils.config import settings


CODE_SPLIT_PATTERNS = {
    ".py": r"(?=\ndef |\nclass |\nasync def )",
    ".js": r"(?=\nfunction |\nconst |\nclass |\nasync function )",
    ".ts": r"(?=\nfunction |\nconst |\nclass |\nasync function |\nexport )",
    ".jsx": r"(?=\nfunction |\nconst |\nclass |\nexport )",
    ".tsx": r"(?=\nfunction |\nconst |\nclass |\nexport )",
    ".java": r"(?=\n\s*(public|private|protected|static)\s)",
    ".go": r"(?=\nfunc )",
    ".rb": r"(?=\ndef |\nclass )",
    ".rs": r"(?=\nfn |\nimpl |\nstruct |\npub fn )",
}

TEXT_EXTENSIONS = {".md", ".txt", ".rst"}


def chunk_content(content: str, extension: str, chunk_size: int = None, chunk_overlap: int = None) -> List[str]:
    chunk_size = chunk_size or settings.CHUNK_SIZE
    chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP

    if extension in TEXT_EXTENSIONS:
        return _chunk_by_paragraph(content, chunk_size, chunk_overlap)

    if extension in CODE_SPLIT_PATTERNS:
        chunks = _chunk_by_code_blocks(content, extension, chunk_size, chunk_overlap)
        if chunks:
            return chunks

    return _chunk_by_characters(content, chunk_size, chunk_overlap)


def _chunk_by_code_blocks(content: str, extension: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    pattern = CODE_SPLIT_PATTERNS.get(extension)
    if not pattern:
        return []

    blocks = re.split(pattern, content)
    blocks = [b.strip() for b in blocks if b.strip()]

    chunks = []
    current_chunk = ""

    for block in blocks:
        if len(current_chunk) + len(block) <= chunk_size:
            current_chunk += "\n\n" + block
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            if len(block) > chunk_size:
                chunks.extend(_chunk_by_characters(block, chunk_size, chunk_overlap))
                current_chunk = ""
            else:
                current_chunk = block

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


def _chunk_by_paragraph(content: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    paragraphs = re.split(r"\n{2,}", content)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    chunks = []
    current_chunk = ""

    for para in paragraphs:
        if len(current_chunk) + len(para) <= chunk_size:
            current_chunk += "\n\n" + para
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = para

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks if chunks else _chunk_by_characters(content, chunk_size, chunk_overlap)


def _chunk_by_characters(content: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    chunks = []
    start = 0
    while start < len(content):
        end = start + chunk_size
        chunk = content[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start += chunk_size - chunk_overlap
    return chunks


def parse_file(file_data: Dict) -> List[Dict]:
    """Take a file dict from repo_loader and return list of chunk dicts."""
    content = file_data["content"]
    extension = file_data["extension"]
    relative_path = file_data["relative_path"]

    chunks = chunk_content(content, extension)

    if not chunks:
        logger.debug(f"No chunks produced for: {relative_path}")
        return []

    parsed_chunks = []
    for i, chunk_text in enumerate(chunks):
        parsed_chunks.append({
            "chunk_text": chunk_text,
            "metadata": {
                "relative_path": relative_path,
                "extension": extension,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "size_kb": file_data.get("size_kb", 0),
            }
        })

    return parsed_chunks


def parse_files(files: List[Dict]) -> List[Dict]:
    """Parse a list of file dicts and return all chunks across all files."""
    all_chunks = []
    for file_data in files:
        try:
            chunks = parse_file(file_data)
            all_chunks.extend(chunks)
        except Exception as e:
            logger.warning(f"Failed to parse {file_data.get('relative_path')}: {e}")

    logger.info(f"Total chunks produced: {len(all_chunks)} from {len(files)} files")
    return all_chunks