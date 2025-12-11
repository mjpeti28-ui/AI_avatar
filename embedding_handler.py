# Import necessary libraries
import json
import os

import faiss
import numpy as np
from openai import OpenAI

from data_processor import get_convo

# Initialize OpenAI client
client = OpenAI()

# Simple in-memory caches to avoid repeated disk I/O on each request.
_cached_index = None
_cached_knowledge_base = None


def generate_embedding(text, model="text-embedding-3-small"):
    response = client.embeddings.create(input=text, model=model)
    return response.data[0].embedding


def create_embeddings(knowledge_base, index_file="embeddings.index", json_file="knowledge_base.json"):
    global _cached_index, _cached_knowledge_base

    embeddings = []
    for item in knowledge_base:
        embedding = generate_embedding(item["text"])
        item["embedding"] = embedding
        embeddings.append(embedding)

    dimension = len(embeddings[0])
    index = faiss.IndexFlatIP(dimension)
    embedding_matrix = np.array(embeddings, dtype='float32')

    # Normalize for cosine similarity when using inner product index.
    faiss.normalize_L2(embedding_matrix)
    index.add(embedding_matrix)

    faiss.write_index(index, index_file)

    with open(json_file, 'w') as f:
        json.dump(knowledge_base, f)

    # Clear caches so the next load picks up the fresh artifacts.
    _cached_index = None
    _cached_knowledge_base = None

    print("Embeddings and index successfully saved.")


def load_embeddings(index_file="embeddings.index", json_file="knowledge_base.json"):
    global _cached_index, _cached_knowledge_base

    if _cached_index is not None and _cached_knowledge_base is not None:
        return _cached_index, _cached_knowledge_base

    if not os.path.exists(index_file) or not os.path.exists(json_file):
        raise FileNotFoundError(
            f"Embedding resources not found. Expected '{index_file}' and '{json_file}'. "
            "Run the embedding creation step first."
        )

    index = faiss.read_index(index_file)

    with open(json_file, 'r') as f:
        knowledge_base = json.load(f)

    _cached_index = index
    _cached_knowledge_base = knowledge_base
    return index, knowledge_base


def retrieve_relevant_knowledge(query, index, knowledge_base, k=3):
    query_embedding = generate_embedding(query)
    query_vector = np.array([query_embedding], dtype='float32')

    # Normalize to match index normalization for cosine similarity.
    faiss.normalize_L2(query_vector)

    D, I = index.search(query_vector, k)  # noqa: E741

    relevant_knowledge = [knowledge_base[i]["text"] for i in I[0]]
    return relevant_knowledge


def get_relevant_context(query, k=3):
    try:
        index, knowledge_base = load_embeddings()
    except FileNotFoundError as exc:
        print(exc)
        return []
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to load embeddings: {exc}")
        return []

    relevant_knowledge = retrieve_relevant_knowledge(query, index, knowledge_base, k)
    return relevant_knowledge


if __name__ == "__main__":
    synthetic_conversation = get_convo()

    knowledge_base = []
    for i in range(0, len(synthetic_conversation), 2):
        if i + 1 < len(synthetic_conversation):
            combined_text = f"User: {synthetic_conversation[i]['content']} Assistant: {synthetic_conversation[i+1]['content']}"
            knowledge_base.append({"text": combined_text})

    create_embeddings(knowledge_base)
