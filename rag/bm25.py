"""
BM25 implementation for keyword-based search.
Used for sparse retrieval in hybrid search.
"""

import math
import pickle
from typing import List, Dict, Any
from collections import Counter
import numpy as np


class BM25:
    """BM25 ranking function for document retrieval."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """
        Initialize BM25 parameters.

        Args:
            k1: Controls term frequency saturation (typically 1.2-2.0)
            b: Controls length normalization (0-1, typically 0.75)
        """
        self.k1 = k1
        self.b = b
        self.doc_lengths = []
        self.avgdl = 0
        self.doc_freqs = []
        self.idf = {}
        self.doc_count = 0
        self.vocab = set()

    def fit(self, documents: List[str]):
        """
        Fit BM25 on a corpus of documents.

        Args:
            documents: List of text documents
        """
        self.doc_count = len(documents)
        doc_freq_counter = Counter()

        # Tokenize and calculate statistics
        for doc in documents:
            tokens = self._tokenize(doc)
            self.doc_lengths.append(len(tokens))
            self.vocab.update(tokens)

            # Count unique tokens per document
            unique_tokens = set(tokens)
            for token in unique_tokens:
                doc_freq_counter[token] += 1

            # Store term frequencies for this document
            token_freq = Counter(tokens)
            self.doc_freqs.append(token_freq)

        # Calculate average document length
        self.avgdl = sum(self.doc_lengths) / len(self.doc_lengths) if self.doc_lengths else 0

        # Calculate IDF for each term
        for token, freq in doc_freq_counter.items():
            self.idf[token] = self._calculate_idf(freq, self.doc_count)

    def _calculate_idf(self, doc_freq: int, total_docs: int) -> float:
        """Calculate inverse document frequency."""
        return math.log((total_docs - doc_freq + 0.5) / (doc_freq + 0.5) + 1)

    def _tokenize(self, text: str) -> List[str]:
        """
        Simple tokenization (can be enhanced with better NLP tools).
        """
        # Convert to lowercase and split
        text = text.lower()

        # Remove punctuation and split
        import re
        tokens = re.findall(r'\b\w+\b', text)

        # Remove stopwords (basic list, can be expanded)
        stopwords = {
            'the', 'is', 'at', 'which', 'on', 'and', 'a', 'an', 'as', 'are',
            'was', 'were', 'be', 'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can',
            'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it',
            'we', 'they', 'what', 'which', 'who', 'when', 'where', 'why', 'how',
            'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other',
            'some', 'such', 'only', 'own', 'same', 'so', 'than', 'too', 'very',
            'just', 'in', 'of', 'to', 'for', 'with', 'by', 'from', 'about'
        }

        tokens = [t for t in tokens if t not in stopwords and len(t) > 2]
        return tokens

    def score(self, query: str, doc_index: int) -> float:
        """
        Calculate BM25 score for a query against a document.

        Args:
            query: Search query
            doc_index: Index of the document to score

        Returns:
            BM25 score
        """
        query_tokens = self._tokenize(query)
        doc_len = self.doc_lengths[doc_index]
        doc_freq = self.doc_freqs[doc_index]

        score = 0.0
        for token in query_tokens:
            if token not in self.idf:
                continue

            freq = doc_freq.get(token, 0)
            if freq == 0:
                continue

            idf = self.idf[token]
            numerator = freq * (self.k1 + 1)
            denominator = freq + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
            score += idf * numerator / denominator

        return score

    def search(self, query: str, top_k: int = 10) -> List[tuple[int, float]]:
        """
        Search for top-k documents matching the query.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of (doc_index, score) tuples
        """
        scores = []
        for i in range(self.doc_count):
            score = self.score(query, i)
            if score > 0:
                scores.append((i, score))

        # Sort by score (descending)
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def save(self, filepath: str):
        """Save BM25 model to disk."""
        model_data = {
            'k1': self.k1,
            'b': self.b,
            'doc_lengths': self.doc_lengths,
            'avgdl': self.avgdl,
            'doc_freqs': self.doc_freqs,
            'idf': self.idf,
            'doc_count': self.doc_count,
            'vocab': self.vocab
        }
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)

    @classmethod
    def load(cls, filepath: str) -> 'BM25':
        """Load BM25 model from disk."""
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)

        model = cls(k1=model_data['k1'], b=model_data['b'])
        model.doc_lengths = model_data['doc_lengths']
        model.avgdl = model_data['avgdl']
        model.doc_freqs = model_data['doc_freqs']
        model.idf = model_data['idf']
        model.doc_count = model_data['doc_count']
        model.vocab = model_data['vocab']

        return model