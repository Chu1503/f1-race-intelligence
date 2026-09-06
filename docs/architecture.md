# F1 Race Intelligence architecture

## Product mode

The default product is a historical race-analysis application. A race becomes visible only after an atomic Parquet dataset with a `_SUCCESS` marker exists. Optional live mode is a separate, explicit OpenF1 → Kafka → Spark path; `/live/sessions` reports whether a processed live snapshot is actually available. The UI no longer presents historical data as live telemetry.

## User workflows and API calls

1. `/` requests `GET /seasons` and `GET /available-races`. The latter scans packaged and persistent historical data, but returns only complete datasets.
2. Selecting a season opens `/{year}` and requests `GET /calendar/{year}` from the Jolpica-backed calendar cache plus `GET /available-races`.
3. Selecting a loaded race opens `/{year}/{round}`. `useRaceData` loads laps, driver summaries, results, incidents, positions, fastest laps, tyre strategies, and pit stops concurrently. Failures are surfaced with a retry action instead of being converted to `null`.
4. Selecting an unloaded past race and pressing `LOAD DATA` calls same-origin `POST /api/processing/jobs`. The Next route adds the server-only service credential and forwards to `POST /processing/jobs`. The UI polls `/api/processing/jobs/{id}` until `succeeded` or `failed`; there is no unbounded timer and every failure is recorded.
5. AI Strategy posts the selected lap plus tyre, degradation, circuit, position, and race-distance context to `/api/ai/strategy`. Next authenticates to the backend. The backend retrieves same-circuit RAG examples, calls the CrewAI/Anthropic strategist, and returns the recommendation plus auditable RAG source metadata.
6. Commentary follows the same protected proxy path and includes the selected position and any generated strategy recommendation.

## Services

| Service | Purpose | Data path |
| --- | --- | --- |
| Next.js 16 / Vercel | UI and secret-preserving proxy for costly operations | Browser → `/api/ai/*` or `/api/processing/*` → FastAPI |
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

AI, RAG search, and processing endpoints require `X-API-Key`; only Next server routes know the shared key. Per-IP sliding-window rate limits protect each costly route. Production refuses protected calls if the key is missing. `/health` reports dependency configuration without revealing secrets, while `/health/ready` returns 503 when core dependencies are unavailable. Render mounts `/var/data` so job records, FastF1 cache, live snapshots, and dynamically loaded races survive restarts.

Set `SERVICE_API_KEY` on Render and set the identical value as `API_SERVICE_KEY` on Vercel. Set `API_BASE_URL` on Vercel to the Render origin. Browser data requests use the same-origin `/api/data/*` proxy, which avoids cross-origin blocking and lets the Vercel server wait for a sleeping Render instance to start. `NEXT_PUBLIC_API_URL` remains a server-side fallback for existing deployments.

For local development, run the FastAPI service on port `8100` and Next.js on port `3000`. Ports `8000` and `8001` are intentionally not assumed because they are occupied by other local services on the development machine. The frontend's `.env.local` routes its server-side proxy to `http://localhost:8100`.
