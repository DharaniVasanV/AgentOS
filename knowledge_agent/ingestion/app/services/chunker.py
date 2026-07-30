"""
app/services/chunker.py

STEP 6: Semantic Chunker.
Splits document into chunks (~700 words target, ~120 words overlap) preserving sentence and paragraph boundaries.
"""

import re
from typing import List, Dict


def chunk_document(clean_text: str, target_words: int = 700, overlap_words: int = 120) -> List[Dict[str, str]]:
    if not clean_text or not clean_text.strip():
        return []

    # Split text into sentences using regex boundary detection
    sentence_pattern = r"(?<=[.!?])\s+"
    sentences = [s.strip() for s in re.split(sentence_pattern, clean_text) if s.strip()]

    if not sentences:
        return [{"text": clean_text, "word_count": len(clean_text.split())}]

    chunks = []
    current_sentences = []
    current_word_count = 0

    for sentence in sentences:
        sentence_words = len(sentence.split())

        if current_word_count + sentence_words > target_words and current_sentences:
            # Complete current chunk
            chunk_text = " ".join(current_sentences)
            chunks.append({
                "text": chunk_text,
                "word_count": len(chunk_text.split())
            })

            # Calculate overlap from the end of current_sentences
            overlap_sentences = []
            overlap_count = 0
            for s in reversed(current_sentences):
                w_count = len(s.split())
                if overlap_count + w_count <= overlap_words:
                    overlap_sentences.insert(0, s)
                    overlap_count += w_count
                else:
                    break

            current_sentences = overlap_sentences + [sentence]
            current_word_count = sum(len(s.split()) for s in current_sentences)
        else:
            current_sentences.append(sentence)
            current_word_count += sentence_words

    if current_sentences:
        chunk_text = " ".join(current_sentences)
        chunks.append({
            "text": chunk_text,
            "word_count": len(chunk_text.split())
        })

    return chunks
