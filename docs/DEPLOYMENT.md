# Deployment

## 1. GitHub
```bash
cd helioassure
git init && git add . && git commit -m "Initial commit: HelioAssure multi-agent engineering platform"
git branch -M main
git remote add origin https://github.com/<you>/helioassure.git
git push -u origin main
```
CI (`.github/workflows/ci.yml`) runs the tests and a deterministic smoke run on every push. `.env`, `secrets.toml`, DB files and `outputs/` are git-ignored - never commit API keys.

## 2. Groq
Create a key at console.groq.com. Locally: `cp .env.example .env` and set `GROQ_API_KEY`. Model names change - verify at console.groq.com/docs/models and adjust `GROQ_MODELS` in `helioassure/config.py` or set `LLM_MODEL`.
Free tiers have low tokens-per-minute limits: the runner honours "try again in Xs" and retries; prefer `llama-3.3-70b-versatile` for JSON discipline.

## 3. Streamlit Community Cloud
1. share.streamlit.io → New app → select the repo, branch `main`, **Main file path: `app.py`**, Python 3.11 (Advanced settings).
2. Default `requirements.txt` is light → deterministic mode works immediately (no key).
3. For LLM mode: change the file used for dependencies by renaming `requirements-llm.txt` content into `requirements.txt` (CrewAI is heavy; the free tier has ~1 GB RAM - if the build fails, deploy with Docker/VM instead).
4. App settings → Secrets: `GROQ_API_KEY = "..."`.
5. Filesystem is ephemeral: download deliverables from the UI; use an external Postgres/S3 for persistence in production.
6. **Do not upload confidential project documents to a public Streamlit app.** Use a private app (viewer auth) or self-host.

## 4. Docker / VM
```bash
docker build -t helioassure . && docker run -p 8501:8501 -e GROQ_API_KEY=... helioassure
```
Local without Docker: `python -m venv .venv && . .venv/bin/activate && pip install -r requirements-llm.txt && streamlit run app.py`.

## 5. Operating it
`python run_platform.py` (deterministic), `python run_platform.py --llm --model llama-3.3-70b-versatile` (LLM agents). Outputs in `outputs/deliverables/` (61 files). Regenerate the synthetic data room: `pip install -r requirements-dev.txt && python data_room/generator/generate_data_room.py`. Score LLM runs vs seeded issues with `evaluation/score.py`.
