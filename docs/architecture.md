# F1 Race Intelligence architecture

## Product mode

The default product is a historical race-analysis application. A race becomes visible only after an atomic Parquet dataset with a `_SUCCESS` marker exists. Optional live mode is a separate, explicit OpenF1 → Kafka → Spark path; `/live/sessions` reports whether a processed live snapshot is actually available. The UI no longer presents historical data as live telemetry.

## User workflows and API calls

1. `/` reads `/data/manifest.json` from Vercel. The manifest contains seasons and every archived race, so the page does not wait for Render.
2. Selecting a season opens `/{year}` and reads its calendar plus availability from that same in-browser manifest cache.
3. Selecting an archived race opens `/{year}/{round}` and downloads one content-hashed static bundle containing laps, driver summaries, results, incidents, positions, fastest laps, tyre strategies, and pit stops. A newly processed race that is not in the current deployment falls back to the dynamic FastAPI endpoints.
4. Selecting an unloaded past race and pressing `LOAD DATA` calls same-origin `POST /api/processing/jobs`. The Next route adds the server-only service credential and forwards to `POST /processing/jobs`. The UI polls `/api/processing/jobs/{id}` until `succeeded` or `failed`; there is no unbounded timer and every failure is recorded.
5. AI Strategy posts the selected lap plus tyre, degradation, circuit, position, and race-distance context to `/api/ai/strategy`. Next authenticates to the backend. The backend retrieves same-circuit RAG examples, calls the CrewAI/Anthropic strategist, and returns the recommendation plus auditable RAG source metadata.
6. Commentary follows the same protected proxy path and includes the selected position and any generated strategy recommendation.

## Services

| Service | Purpose | Data path |
| --- | --- | --- |
| Next.js 16 / Vercel | UI, CDN-hosted historical bundles, and secret-preserving proxy for dynamic operations | Browser → `/data/*` for history; `/api/ai/*` or `/api/processing/*` → FastAPI |
| FastAPI / Render | Read APIs, validation, rate limits, jobs, AI orchestration | Parquet/Jolpica/FastF1/Pinecone → JSON |
| Jolpica | Calendar, roster, official result and pit-stop records | Cached on disk after successful HTTP responses |
| FastF1 | Historical lap ingestion and fallback session detail | Race session → normalized `LapData` |
| SQLite + one-worker executor | Durable job status and serialized historical ingestion | queued → running → succeeded/failed |
| Pandas + PyArrow | Portable historical feature processing | normalized laps → atomic partitioned Parquet |
| OpenF1 | Optional live laps, stints, pits, positions and session metadata | joined before Kafka publication |
| Kafka | Optional live event transport | OpenF1 events → Spark consumer |
| Spark Structured Streaming | Optional live micro-batches | Kafka → accumulated per-session Parquet snapshot |
| Voyage AI | Query/document embeddings (`voyage-2`, 1024 dimensions) | text → vector |
| Pinecone | Versioned historical similarity search | `historical-v2` namespace, cosine search |
| CrewAI + Anthropic | Strategy and commentary generation | validated telemetry + retrieved evidence → prose |

## Feature semantics

Historical API reads and new ingestion jobs use the same portable Pandas feature function. Laps outside 60–200 seconds and duplicate driver/lap pairs are excluded. A stint starts when compound changes or tyre age resets. Degradation is the non-negative rolling linear slope of the last five valid laps within that stint, clipped at 1.5 seconds/lap; improving pace is zero degradation rather than “negative wear.” Pit-stop duration is the stationary/pit-lane duration reported by Jolpica, with FastF1 used only as an explicitly approximate fallback.

## Live path

OpenF1's `/laps` payload does not contain compound or tyre age. The connector joins `/stints` by driver and inclusive lap range, derives current tyre age from `tyre_age_at_start`, and adds the next-stint compound to pit events. Per-driver watermarks prevent a leading car from causing a lapped car's newest lap to be dropped; pit event keys prevent duplicate publication. Spark merges every micro-batch with the prior raw session snapshot, deduplicates it, recomputes rolling features over the accumulated race, and atomically replaces `features.parquet`. The API reads that exact location through `/live/sessions/{session_key}/laps`.

## RAG guarantees

`reingest.py` processes every completed race folder. It recomputes corrected features, fetches the real circuit and official outcome, derives the next observed pit lap/compound, and indexes one representative situation per driver stint in the versioned `historical-v2` namespace. Strategy retrieval filters by the exact circuit name. If same-circuit evidence does not exist or retrieval times out, the prompt says that no historical context is available; it does not silently substitute unrelated races. Returned `rag_sources` identify year, round, circuit, driver, lap, similarity, and observed outcome.

## Security and operations

AI, RAG search, and processing endpoints require `X-API-Key`; only Next server routes know the shared key. Per-IP sliding-window rate limits protect each costly route. Production refuses protected calls if the key is missing. `/health` reports dependency configuration without revealing secrets, while `/health/ready` returns 503 when core dependencies are unavailable. The free Render configuration uses `/tmp`; job records, newly downloaded FastF1 files, live snapshots, and dynamically loaded races are therefore ephemeral. Durable historical availability comes from the versioned static frontend artifacts committed to the repository.

Set the same `SERVICE_API_KEY` value on Render and Vercel. Set `API_BASE_URL` on Vercel to the Render origin. Historical browser reads use same-origin static files. A non-blocking health request begins waking Render in the background for AI, processing, or a new race. Dynamic reads use the `/api/data/*` proxy; `NEXT_PUBLIC_API_URL` remains a server-side fallback for existing deployments.

## Refreshing the static archive

After adding or reprocessing historical races, run:

```powershell
.\venv\Scripts\python.exe scripts\export_static_data.py
```

Commit the generated `frontend/public/data/manifest.json` and content-hashed files below `frontend/public/data/races/`, then deploy the frontend. The exporter writes each bundle before atomically replacing the manifest. Hashed bundles are cached for one year; the manifest is shared-cached for five minutes with a one-hour stale window. Protected AI and processing responses remain private and uncached.

The checked-in snapshot contains 82 completed races: 22 from 2023, 24 from 2024, 24 from 2025, and the first 12 from 2026. The scheduled `.github/workflows/update-race-archive.yml` job checks the current season each Monday, processes only new races, refreshes the manifest, and commits the durable artifacts. It can also be run manually from the GitHub Actions page. If repository policy blocks workflow pushes, enable read/write workflow permissions or run the commands above locally.

For local development, run the FastAPI service on port `8100` and Next.js on port `3000`. Ports `8000` and `8001` are intentionally not assumed because they are occupied by other local services on the development machine. The frontend's `.env.local` routes its server-side proxy to `http://localhost:8100`.
