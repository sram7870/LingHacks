# LingHacks Scientific Reasoning: Project Instructions

This project is a multi-layered scientific reasoning application that analyzes research papers (particularly regarding Lyme Disease controversy) using SciBERT, Multi-Agent systems, and Heterogeneous Graph Neural Networks.

## Tech Stack
- **Backend:** FastAPI (Python)
- **Frontend:** React + Vite + Tailwind CSS
- **Database:** Neo4j (Graph Database)
- **ML Models:** 
  - SciBERT (`allenai/scibert_scivocab_uncased`) for claim extraction and embeddings.
  - ControversyGNN (Heterogeneous GAT) for controversy prediction.
  - Sentence Transformers for semantic evolution tracking.

## Key Features
- **Document Parsing:** Supports PDF (via GROBID), XML, HTML, and TEI.
- **Claim Extraction:** Extracts key scientific claims and assigns embeddings.
- **Multi-Agent Review:** Heuristic agents for Stance, Skepticism, Methods, and Consensus.
- **Relational Paper Analysis (RPA):** Cross-references papers using 5 metrics:
  1. **Consensus Alignment Score (CAS):** Alignment with field consensus.
  2. **Field Controversy Index (FCI):** Topic disagreement level.
  3. **Methodological Standing Score (MSS):** Quality relative to competitors.
  4. **Claim Novelty Score (CNS):** Uniqueness of findings.
  5. **Temporal Field Position (TFP):** Debate maturity and trajectory.

## Backend Architecture
- `app/main.py`: Entry point.
- `app/api.py`: REST endpoints and lazy-loaded services.
- `app/services/`: Core logic (encoder, claim extraction, agent review, graph builder, relational analysis, GNN, semantic evolution).
- `app/db/graph.py`: Neo4j interaction.

## Frontend Architecture
- `frontend/src/`: React source.
- `frontend/src/App.jsx`: Main dashboard logic.
- `frontend/src/api.js`: API client.

## Development Workflows
- **Running Backend:** `uvicorn app.main:app --reload`
- **Running Frontend:** `npm run dev` in `frontend/`
- **Grobid:** Expected at `http://localhost:8070` for PDF parsing.

## Conventions
- Use Pydantic schemas for data validation.
- Services should be lazily initialized in `app/api.py` to minimize startup overhead.
- Maintain consistency with existing RPA metric naming (CAS, FCI, MSS, CNS, TFP).
