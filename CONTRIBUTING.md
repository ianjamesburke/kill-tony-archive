# Contributing

## Prerequisites

- Python 3.12+
- Node 22+
- ffmpeg
- A [Google AI Studio](https://aistudio.google.com/) API key (free tier works for individual episodes)

## Setup

```bash
git clone https://github.com/ianjamesburke/kill-tony-archive
cd kill-tony-archive

# Copy env template and fill in your keys
cp .env.example .env
```

**Backend:**
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-pipeline.txt
uvicorn main:app --reload
```

**Frontend** (separate terminal):
```bash
cd frontend
npm install
npm run dev
```

Add a `frontend/.env.local` with:
```
VITE_API_BASE=http://localhost:8000/api
```

## Processing an Episode

```bash
python3 backend/batch_processor.py "https://www.youtube.com/watch?v=EPISODE_URL"
```

This runs the full two-pass pipeline: download → transcribe → analyze → store. Expect ~5–10 minutes per episode depending on length. The Pass 1 transcript is cached in `data/transcripts/` so you can re-run Pass 2 cheaply with `reprocess_pass2.py`.

## Free Tier Limits

Gemini free tier allows roughly 1 episode per day with the default models. For bulk processing a paid API key is needed. See `backend/batch_processor.py` for model configuration.
