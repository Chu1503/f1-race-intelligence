import time
from sentence_transformers import SentenceTransformer

models = [
    ("all-MiniLM-L6-v2", 384),
    ("all-mpnet-base-v2", 768),
]

test_texts = [
    "SOFT tyres 20 laps high degradation Bahrain",
    "driver should pit soon tyre cliff approaching",
    "undercut opportunity gap closing fast pit window",
    "MEDIUM compound low degradation rate consistent pace",
    "safety car deployed pit window open all drivers",
] * 20

query = "driver on soft tyres showing tyre degradation should pit soon"

for model_name, dims in models:
    print(f"\n{'='*50}")
    print(f"Model: {model_name} ({dims} dims)")
    
    model = SentenceTransformer(model_name)
    start = time.time()
    embeddings = model.encode(test_texts)
    elapsed = time.time() - start
    print(f"Speed: {len(test_texts)} texts in {elapsed:.2f}s ({len(test_texts)/elapsed:.1f} texts/sec)")

    query_emb = model.encode(query)
    from sentence_transformers import util
    scores = util.cos_sim(query_emb, embeddings)[0]
    
    top3_idx = scores.topk(3).indices.tolist()
    print("Top 3 most similar to query:")
    print(f"  Query: '{query}'")
    for i, idx in enumerate(top3_idx):
        print(f"  {i+1}. [{scores[idx]:.3f}] {test_texts[idx % 5]}")
    
    print(f"Worst match score: {scores.min():.3f}")
    print(f"Best match score:  {scores.max():.3f}")