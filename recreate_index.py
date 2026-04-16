from config import settings
import pinecone
pc = pinecone.Pinecone(api_key=settings.PINECONE_API_KEY)
pc.create_index(
    name='f1-race-intelligence',
    dimension=1024,
    metric='cosine',
    spec=pinecone.ServerlessSpec(cloud='aws', region='us-east-1')
)
print('Done')