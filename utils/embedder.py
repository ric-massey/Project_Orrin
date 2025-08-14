from typing import Union, List
from sentence_transformers import SentenceTransformer

_model = None

def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer('all-mpnet-base-v2')
    return _model

def get_embedding(texts: Union[str, List[str]], normalize: bool = True):
    """
    Takes a string or list of strings and returns their embeddings.
    If normalize=True, embeddings are L2-normalized (better for cosine similarity).
    Returns a single vector if input is a string.
    """
    model = get_model()
    is_single = isinstance(texts, str)
    if is_single:
        texts = [texts]

    embeddings = model.encode(
        texts,
        normalize_embeddings=normalize,
        show_progress_bar=False
    )
    return embeddings[0] if is_single else embeddings