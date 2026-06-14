# LingHacks Scientific Reasoning Backend

Backend scaffold for a multi-stage scientific reasoning platform.

## Stack
- Python
- FastAPI
- PyTorch
- Transformers
- Neo4j (graph storage)

## Project Layout
- `app/main.py`: FastAPI application entrypoint
- `app/api.py`: HTTP routes and endpoints
- `app/schemas.py`: Pydantic request/response models
- `app/services/`: Domain logic for document parsing, claim extraction, multi-agent review, and graph building

## Getting Started
1. Create a Python environment
2. Install dependencies from `requirements.txt`
3. Run the app:

```bash
uvicorn app.main:app --reload --port 8000
```

## Next steps
- Implement parser integration with GROBID / Science Parse
- Add SciBERT claim extraction and LLM verification
- Build the multi-agent review orchestration layer
- Connect the knowledge graph builder to Neo4j

## To run the project:

Run Instructions

Prereqs: Ensure Node+npm and Python 3+ are installed. Optional: Neo4j if you want graph features.

Backend (Windows PowerShell):

(If needed) create venv and install deps:

python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

Start the API:
\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

Frontend:

cd frontend
npm install      # only if dependencies not installed
npm run dev

Dev server URL: http://localhost:4173/

Alternative (Docker Compose):
docker-compose up --build
