
from sentence_transformers import SentenceTransformer

_model = None

def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer('all-mpnet-base-v2')
    return _model

def get_embedding(texts):
    """
    Takes a string or list of strings and returns their embeddings.
    """
    model = get_model()
    if isinstance(texts, str):
        texts = [texts]
    return model.encode(texts)