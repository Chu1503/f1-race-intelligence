import os, re
from rag_pipeline.ingester import ingest_historical_session
base = 'data/spark_output/historical'
for folder in os.listdir(base):
    m = re.match(r'(\d{4})_round(\d+)', folder)
    if m:
        year, round_num = int(m.group(1)), int(m.group(2))
        path = os.path.join(base, folder)
        print(f'Ingesting {year} R{round_num}...')
        ingest_historical_session(path, year, round_num)
print('All done')