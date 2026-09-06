# Performance Audit

Audit date: 2026-09-05. This report records the pre-fix state of the repository at commit `57c25ee`. The audit was completed before any performance implementation work began.

## Architecture and critical flows

- **Frontend:** Next.js 16.3.4 and React 19, deployed on Vercel. The pages are client components and browser reads are forwarded through a same-origin Next route.
- **Backend:** FastAPI/Uvicorn on a free Render web service. It reads packaged or generated Parquet through Pandas/PyArrow and stores ingestion-job state in SQLite.
- **External services:** Jolpica supplies calendars, rosters, official results, and pit stops; FastF1 supplies ingestion and fallback session detail; OpenF1, Kafka, and Spark form the optional live path; Voyage and Pinecone provide RAG embeddings/search; CrewAI and Anthropic generate strategy and commentary.
- **Historical landing flow:** `/` loads seasons plus the available-race scan. `/{year}` loads a Jolpica calendar plus available races.
- **Historical race flow:** `/{year}/{round}` starts ten browser-to-Next-to-Render reads and reveals the page only after every request has completed.
- **Processing flow:** a protected Next route forwards a job request with a server-only service key, then the UI polls a status endpoint backed by SQLite and a one-worker executor.
- **AI flow:** protected Next routes forward validated race context to FastAPI; strategy retrieval calls Voyage/Pinecone before CrewAI/Anthropic generation.

The repository contains 24 complete 2025 races (974 Parquet-related files, approximately 5.24 MB). That historical data is public and immutable enough to publish as static deployment artifacts. The dynamic cache and processing directories are larger and are not candidates for public deployment.

### 1. Response compression

Status: **Confirmed** (proxy-header defect and API overfetch); origin/CDN compression itself is present.

Severity: **High**

Evidence:

- Production Render returns the 2025 round 1 laps payload with gzip when the client advertises it: 489,548 bytes with identity encoding versus 36,392 bytes with gzip, a 92.6% transfer reduction.
- Vercel returns Brotli-compressed HTML and hashed JavaScript assets.
- The public proxy returns a 489,548-byte plain JSON body while retaining `Content-Encoding: br`. `frontend/lib/server-api.ts:22-65` forwards the upstream `Response` after the Next runtime has decoded the body, but does not remove representation-specific headers. This is an invalid body/header combination and can produce decoding failures.
- `api/main.py:400-413` serializes every feature-frame column. The client lap type in `frontend/components/race/types.ts:3-16` needs only 11 fields. Selecting those fields reduces this representative raw payload to 224,063 bytes (54.2% smaller) before compression.

Impact:

- Some clients can reject or mishandle proxied API responses because their encoding header does not describe the body.
- Every race view transfers fields the UI never reads and spends extra time serializing, copying, and parsing them.

Recommended fix:

- Sanitize hop-by-hop and representation-specific headers when relaying an already-decoded upstream response, then allow Vercel to encode the outgoing representation correctly.
- Limit the laps response to the fields used by the application.
- Publish compact, per-race static bundles so a page needs one compressed race-data transfer instead of many API documents.

Risks or tradeoffs:

- Removing a field is safe only after checking all consumers. The selected field list must remain covered by frontend and backend tests.
- Compression should remain the hosting platform's responsibility; adding application compression as well could cause double encoding.

Measurement:

- Compare `Content-Encoding`, raw bytes, and transferred bytes with identity, gzip, and Brotli requests.
- Verify a proxied response decodes as JSON with a client that does not automatically repair inconsistent headers.
- Record the raw and gzip size of the generated race bundle and the number of race-page requests.

### 2. Database write batching

Status: **Not found**

Severity: **Low**

Evidence:

- `api/jobs.py:54-99` performs one job insert and one status update per state transition. These are individual logical records, protected by a lock and SQLite transactions, rather than an item-at-a-time import loop.
- `rag_pipeline/vector_store.py:39-47` already upserts Pinecone vectors in batches of 100.
- `spark_processing/batch_processor.py:50-54` writes a complete partitioned Parquet result.
- `spark_processing/lap_processor.py:35-47` merges and deduplicates a micro-batch before atomically replacing the session snapshot.
- No ORM, Supabase client, N+1 record mutation loop, or sequential single-row import API was found in the application paths.

Impact:

- There is no confirmed database round-trip problem to fix. Replacing the job transitions with a bulk operation would weaken observable job-state semantics without improving a batch workload.

Recommended fix:

- Keep the current transactional job writes and bounded one-worker ingestion model.
- Re-audit if job volume grows or the job store moves from local SQLite to a remote database.

Risks or tradeoffs:

- Parallelizing ingestion writes would create race conditions around status transitions and would not solve Render cold starts.

Measurement:

- Continue asserting one insert plus bounded state updates per job in tests. If a remote database is introduced, count database round trips per submitted job.

### 3. Dependency bottleneck

Status: **Confirmed**

Severity: **Critical**

Evidence:

- `frontend/hooks/use-race-data.ts:44-59` launches ten reads and blocks on one `Promise.all`; the slowest dependency determines when any race content appears.
- `api/main.py:126-201` puts Jolpica in the calendar/driver critical path. Driver loading makes two sequential provider requests.
- `api/main.py:253-273` serializes uncached FastF1 session loads behind a global lock. Incidents, positions, and some pit-stop fallbacks depend on that load.
- `api/main.py:87-100` recomputes race features on a backend cache miss. A free-service restart loses its in-memory cache.
- Measured warm production endpoint times for one race ranged from 1.14 seconds (laps) to 3.58 seconds (incidents). The race page finishes at the slowest result. A separate direct laps sample took about 6.6 seconds with gzip.
- The free Render service sleeps after an idle interval and can take roughly a minute to accept traffic again. A 100-second frontend timeout only waits longer; it does not make this dependency faster.

Impact:

- Historical pages can be blank or fail whenever Render is sleeping, Jolpica is slow, or FastF1 performs an uncached load, despite the underlying historical files already being in the repository.
- The current design cannot meet the requirement that old races appear immediately on a free sleeping backend.

Recommended fix:

- Build a versioned static manifest and content-hashed bundle for every processed race. Serve those files from Vercel's CDN and make the browser use them first.
- Retain the backend as a fallback only for newly processed races that have not yet been exported.
- Warm Render in the background without blocking historical rendering, reducing the chance that a later AI or processing action encounters a cold service.
- Add development-only `[perf]` timing around backend proxy calls without logging queries, request bodies, credentials, or personal data.

Risks or tradeoffs:

- Newly processed data is not part of the static catalog until the export is run and deployed.
- AI generation and dynamic ingestion still require Render and third-party services; static files cannot make those computations offline.

Measurement:

- Load `/`, `/2025`, and `/2025/1` with FastAPI stopped and confirm historical content renders.
- Count historical race-page requests before and after (ten dynamic race reads before; one static race bundle after, plus cached catalog data).
- Compare first-content timing and proxy `[perf]` logs locally; inspect Render and Vercel timings after deployment.

### 4. Blocking UI updates

Status: **Confirmed**

Severity: **Medium**

Evidence:

- `frontend/hooks/use-race-data.ts:44-75` commits no race data until every source returns.
- `frontend/app/[year]/[round]/page.tsx:1459-1492` replaces the content area with a fixed-height spinner while that aggregate request is pending.
- No route-level `loading.tsx` exists for the season or race navigation, so route transitions have no framework loading shell.
- Processing and AI actions already show pending states and disable duplicate submissions. Optimistically inventing AI results or ingestion success would be incorrect.

Impact:

- A fast laps payload is invisible while the page waits for slow incident, position, pit-stop, or third-party calls. Navigation can appear unresponsive.

Recommended fix:

- Replace the ten-way blocking race fetch with the static bundle fast path.
- Add route-level loading skeletons so navigation changes state immediately.
- Preserve authoritative pending/error handling for processing and AI rather than applying unsafe optimistic updates.

Risks or tradeoffs:

- A skeleton improves perceived latency but does not replace actual dependency work. The static path is the material latency fix.

Measurement:

- Use browser performance/network tools to verify immediate navigation feedback, no duplicate mutations, correct errors, and one race-bundle request on the static path.

### 5. Rendering and caching

Status: **Confirmed**

Severity: **High**

Evidence:

- The pre-fix production build classifies `/` as static but `/{year}` and `/{year}/{round}` as dynamic.
- `frontend/app/api/data/[...path]/route.ts:3` declares `force-dynamic` and `frontend/lib/server-api.ts:26` uses `cache: "no-store"` for every forwarded read.
- Production responses from the public proxy use `Cache-Control: public, max-age=0, must-revalidate` and report Vercel cache misses.
- Historical pages contain no user-specific or private data, and the underlying completed race datasets are immutable after their `_SUCCESS` marker.
- Next's `public` folder defaults to `max-age=0`; without explicit headers even generated data files would revalidate unnecessarily.

Classification:

- **Must be dynamic/private:** AI strategy, commentary, RAG query, job submission, and job status.
- **Can be statically generated:** known season and completed-race route shells.
- **Can use cached data with targeted invalidation:** public manifest/calendar/driver metadata and newly available public backend reads.
- **Accidentally dynamic:** completed historical race data routed through the catch-all proxy.

Impact:

- Vercel cannot reliably satisfy repeated historical reads from its edge, so each visitor pays backend startup, computation, provider, serialization, and transfer costs.

Recommended fix:

- Generate static params for known years and rounds while allowing unknown future params.
- Give the frequently refreshed manifest a short shared-cache lifetime with stale-while-revalidate.
- Give content-hashed race bundles a one-year immutable cache lifetime.
- Keep all protected or mutable endpoints private and uncached.

Risks or tradeoffs:

- Long-lived caching is safe only for content-addressed filenames. The mutable manifest must retain a short cache and change when a race bundle changes.

Measurement:

- Inspect the Next production route table for pre-rendered season/race paths.
- Verify `Cache-Control`, `Age`, and CDN-cache headers after deployment.
- Reload a historical race and confirm no Render request is made and the hashed bundle is served from browser/CDN cache.

## Prioritized implementation plan

| Priority | Change | Expected improvement | User-visible impact | Risk | Effort |
| --- | --- | --- | --- | --- | --- |
| 1 | Export static manifest and per-race bundles; use them before the backend | Removes Render, Jolpica, FastF1, and ten proxy reads from historical critical path | Critical | Medium | Medium |
| 2 | Sanitize proxy response headers and reduce lap fields | Prevents invalid decoding and cuts serialization/payload size | High | Low | Low |
| 3 | Add content-aware cache headers and static params | Enables browser/CDN reuse and pre-rendered route shells | High | Low | Low |
| 4 | Add route loading skeletons and background backend warm-up | Immediate feedback; AI/backend more likely to be ready later | Medium | Low | Low |
| 5 | Add development timings, tests, and export/runbook documentation | Makes regressions observable and refreshes repeatable | Medium | Low | Medium |

No database batching rewrite is planned because the audit did not confirm that risk.
