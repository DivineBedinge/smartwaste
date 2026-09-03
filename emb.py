# Dans un script temporaire ou dans un notebook Colab
from sentence_transformers import SentenceTransformer, CrossEncoder

# Embedding multilingue (plus robuste pour le français/camfranglais)
embedder = SentenceTransformer('intfloat/multilingual-e5-small')
embedder.save('models/multilingual-e5-small')

# Cross-encoder pour re-ranking
reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
reranker.save('models/ms-marco-MiniLM-L-6-v2')