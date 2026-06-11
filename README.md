# DosePathSyn Web System

This repository is organized for public deployment:

```text
frontend/       Static web frontend
backend/        FastAPI inference service
model_assets/   Runtime model and data assets
generated/      Generated analysis reports
docs/           Design and API notes
```

## Local Run

Install backend dependencies:

```bash
pip install -r backend/requirements.txt
```

Start the FastAPI service from the project root:

```bash
uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

Then open:

```text
http://localhost:8000
```

## Deploy Notes

Backend deployment can use Render or Hugging Face Spaces. If the backend is deployed separately, set the frontend API base URL in:

```text
frontend/config.js
```

Example:

```js
window.API_BASE_URL = "https://your-backend.onrender.com";
```

Do not commit private keys, patient data, `.env` files, or large model checkpoints unless the hosting platform supports them.

## Research Disclaimer

The system output is for research analysis, algorithm demonstration, and experimental design support only. It is not clinical diagnosis or medication guidance.
