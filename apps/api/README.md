# Paper Atlas API

FastAPI service for URL ingestion, PDF extraction, model classification and knowledge-base export.

## Run

```bash
cd /home/kun/Desktop/paper/apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The frontend defaults to `http://localhost:8000`. Override it with
`NEXT_PUBLIC_API_URL` when the API runs on another host or port.

## Internal Access Configuration

Set the browser origins allowed to call the API in `.env`:

```env
CORS_ORIGINS=http://localhost:3000,http://192.168.1.20:3000
```

Optional password login is enabled as soon as `AUTH_PASSWORD` is non-empty:

```env
AUTH_USERNAME=admin
AUTH_PASSWORD=change-me
AUTH_SESSION_SECRET=replace-with-a-random-secret
AUTH_SESSION_TTL_HOURS=24
AUTH_COOKIE_SECURE=false
```

When enabled, all `/api/*` routes except `/api/auth/*` require a signed
HttpOnly session cookie. Leave `AUTH_PASSWORD` empty only when the service is
restricted to a trusted LAN.

## Model Configuration

The API uses an OpenAI-compatible chat-completions endpoint:

```text
LLM_PROVIDER=openai-compatible
LLM_BASE_URL=https://your-provider.example/v1
LLM_MODEL=your-model-id
LLM_API_KEY=your-key
```

For offline pipeline tests, set `LLM_PROVIDER=mock`. This validates downloading,
extraction, classification, Markdown export and frontend loading without
claiming that a real model performed the analysis.

## Import Flow

1. Resolve and download the user-provided URL into `need_organization/`.
2. Extract PDF metadata and page-level text.
3. Ask the configured model for a category and structured metadata.
4. Ask the configured model for a bilingual interpretation with page evidence.
5. Move the PDF into `completed/<category>/`.
6. Append the structured entry to `KNOWLEDGE_BASE.md`.
7. Store the paper in SQLite and expose it through `/api/papers`.
