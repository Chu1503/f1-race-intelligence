# F1 Race Intelligence frontend

This is the Next.js 16 frontend. Vercel serves historical race data directly from `public/data`; FastAPI/Render is needed only for AI, ingestion, live data, and a newly processed race that has not yet been exported.

## Local development

From the repository root, start FastAPI on port 8100. Then run:

```powershell
cd frontend
npm install
npm run dev
```

The historical archive also works with FastAPI stopped.

AI and processing requests are sent through protected server routes. Set the
same long random `SERVICE_API_KEY` value in both the Render service and the
Vercel project. The frontend also accepts the previous `API_SERVICE_KEY` name
during migration.

## Refresh historical data

After processing a new race, run this from the repository root:

```powershell
.\venv\Scripts\python.exe scripts\export_static_data.py
```

Existing bundles are reused. Use `--force` only when the bundle schema or derivation logic changes. Commit the new Parquet folder, the changed manifest, and the new content-hashed bundle. The weekly `Update race archive` GitHub workflow performs this automatically for the current season.

## Validation

```powershell
npm test
npm run lint
npm run build
```
