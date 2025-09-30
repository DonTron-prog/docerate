"""
Document chunking module for processing markdown posts.
Chunks by semantic sections (H2/H3) while preserving boundaries.
"""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import hashlib


@dataclass
class Chunk:
    """Represents a document chunk with metadata."""
    chunk_id: str
    content: str
    post_slug: str
    post_title: str
    section_heading: Optional[str]
    tags: List[str]
    url_fragment: str
    position: int
    token_count: int


class MarkdownChunker:
    """Chunks markdown documents by semantic sections."""

    def __init__(self, max_tokens: int = 512, overlap_tokens: int = 50):
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens

    def chunk_document(self, content: str, metadata: Dict[str, Any], post_slug: str) -> List[Chunk]:
        """
        Chunk a markdown document by sections.

        Args:
            content: Raw markdown content
            metadata: Post metadata (title, tags, date, etc.)
            post_slug: URL slug for the post

        Returns:
            List of Chunk objects
        """
        chunks = []

        # Split by H2 sections first
        h2_pattern = r'^## (.+)$'
        h2_sections = re.split(h2_pattern, content, flags=re.MULTILINE)

        # Process introduction (content before first H2)
        if h2_sections[0].strip():
            intro_chunks = self._create_chunks_from_section(
                content=h2_sections[0],
                metadata=metadata,
                post_slug=post_slug,
                section_heading=None,
                position=0
            )
            chunks.extend(intro_chunks)

        # Process each H2 section
        position = len(chunks)
        for i in range(1, len(h2_sections), 2):
            h2_heading = h2_sections[i]
            h2_content = h2_sections[i + 1] if i + 1 < len(h2_sections) else ""

            # Check for H3 subsections within H2
            h3_pattern = r'^### (.+)$'
            h3_sections = re.split(h3_pattern, h2_content, flags=re.MULTILINE)

            # Process H2 intro content (before first H3)
            if h3_sections[0].strip():
                section_chunks = self._create_chunks_from_section(
                    content=h3_sections[0],
                    metadata=metadata,
                    post_slug=post_slug,
                    section_heading=h2_heading,
                    position=position
                )
                chunks.extend(section_chunks)
                position += len(section_chunks)

            # Process each H3 subsection
            for j in range(1, len(h3_sections), 2):
                h3_heading = h3_sections[j]
                h3_content = h3_sections[j + 1] if j + 1 < len(h3_sections) else ""

                if h3_content.strip():
                    subsection_chunks = self._create_chunks_from_section(
                        content=h3_content,
                        metadata=metadata,
                        post_slug=post_slug,
                        section_heading=f"{h2_heading} > {h3_heading}",
                        position=position
                    )
                    chunks.extend(subsection_chunks)
                    position += len(subsection_chunks)

        return chunks

    def _create_chunks_from_section(
        self,
        content: str,
        metadata: Dict[str, Any],
        post_slug: str,
        section_heading: Optional[str],
        position: int
    ) -> List[Chunk]:
        """
        Create chunks from a section, respecting token limits.
        """
        chunks = []

        # Clean content
        content = content.strip()
        if not content:
            return chunks

        # Estimate tokens (rough approximation: 1 token ≈ 4 characters)
        estimated_tokens = len(content) // 4

        if estimated_tokens <= self.max_tokens:
            # Section fits in one chunk
            chunk = self._create_chunk(
                content=content,
                metadata=metadata,
                post_slug=post_slug,
                section_heading=section_heading,
                position=position
            )
            chunks.append(chunk)
        else:
            # Split section into multiple chunks by sentences
            sentences = self._split_into_sentences(content)
            current_chunk = []
            current_tokens = 0

            for sentence in sentences:
                sentence_tokens = len(sentence) // 4

                if current_tokens + sentence_tokens <= self.max_tokens:
                    current_chunk.append(sentence)
                    current_tokens += sentence_tokens
                else:
                    # Save current chunk
                    if current_chunk:
                        chunk_content = " ".join(current_chunk)
                        chunk = self._create_chunk(
                            content=chunk_content,
                            metadata=metadata,
                            post_slug=post_slug,
                            section_heading=section_heading,
                            position=position + len(chunks)
                        )
                        chunks.append(chunk)

                    # Start new chunk with overlap
                    if self.overlap_tokens > 0 and current_chunk:
                        # Include last few sentences as overlap
                        overlap_sentences = []
                        overlap_tokens = 0
                        for sent in reversed(current_chunk):
                            sent_tokens = len(sent) // 4
                            if overlap_tokens + sent_tokens <= self.overlap_tokens:
                                overlap_sentences.insert(0, sent)
                                overlap_tokens += sent_tokens
                            else:
                                break
                        current_chunk = overlap_sentences + [sentence]
                        current_tokens = overlap_tokens + sentence_tokens
                    else:
                        current_chunk = [sentence]
                        current_tokens = sentence_tokens

            # Save final chunk
            if current_chunk:
                chunk_content = " ".join(current_chunk)
                chunk = self._create_chunk(
                    content=chunk_content,
                    metadata=metadata,
                    post_slug=post_slug,
                    section_heading=section_heading,
                    position=position + len(chunks)
                )
                chunks.append(chunk)

        return chunks

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences, preserving code blocks."""
        # Simple sentence splitter (can be improved with nltk or spacy)
        # Preserve code blocks
        code_block_pattern = r'```[\s\S]*?```'
        code_blocks = re.findall(code_block_pattern, text)

        # Replace code blocks with placeholders
        for i, block in enumerate(code_blocks):
            text = text.replace(block, f"__CODE_BLOCK_{i}__")

        # Split by sentence endings
        sentences = re.split(r'(?<=[.!?])\s+', text)

        # Restore code blocks
        for i, block in enumerate(code_blocks):
            sentences = [s.replace(f"__CODE_BLOCK_{i}__", block) for s in sentences]

        return sentences

    def _create_chunk(
        self,
        content: str,
        metadata: Dict[str, Any],
        post_slug: str,
        section_heading: Optional[str],
        position: int
    ) -> Chunk:
        """Create a Chunk object with metadata."""
        # Generate chunk ID
        chunk_id = hashlib.md5(f"{post_slug}_{position}_{content[:50]}".encode()).hexdigest()[:16]

        # Create URL fragment
        if section_heading:
            # Convert heading to URL-friendly fragment
            fragment = re.sub(r'[^\w\s-]', '', section_heading.lower())
            fragment = re.sub(r'[-\s]+', '-', fragment)
            url_fragment = f"#{fragment}"
        else:
            url_fragment = ""

        return Chunk(
            chunk_id=chunk_id,
            content=content,
            post_slug=post_slug,
            post_title=metadata.get('title', ''),
            section_heading=section_heading,
            tags=metadata.get('tags', []),
            url_fragment=url_fragment,
            position=position,
            token_count=len(content) // 4  # Rough estimate
        )