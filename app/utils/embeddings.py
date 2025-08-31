from sentence_transformers import SentenceTransformer
from functools import lru_cache
import os

@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    model = SentenceTransformer(model_name, device="cpu")
    return model

def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()
    # model outputs numpy array -> convert to python lists for Chroma
    return model.encode(texts, normalize_embeddings=True).tolist()

def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]
