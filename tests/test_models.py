import os
import anthropic
from config import settings

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

models = client.models.list()
for m in models.data:
    print(m.id)