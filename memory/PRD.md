# JurnalMap — Product Requirements Document

## Original Problem Statement
JurnalMap is a web application to read, verify, and compare scientific journals.
Philosophy: AI finds evidence, not truth. AI compares, not decides. AI shows
differences, not who is wrong.

The user requested a Next.js + SQLite + LanceDB + Celery + Redis + Docling +
spaCy + GLiNER + BGE-M3 + ModernBERT stack. After clarification, the user
accepted adaptation to the Emergent runtime: React CRA + FastAPI + MongoDB +
PyMuPDF + BM25 + Gemini 3 Flash via Emergent Universal LLM Key.

## Architecture (built)
- **Backend** FastAPI (`/app/backend/server.py`) + MongoDB (Motor).
  - PDF parsing via PyMuPDF (`app/services/pdf_parser.py`) — sentences with bounding boxes.
  - Background processing via FastAPI BackgroundTasks (no Celery/Redis).
  - Retrieval: BM25 (`rank_bm25`) — fast, deterministic, no model downloads.
  - LLM: Gemini 3 Flash via `emergentintegrations` library and Emergent Universal Key.
- **Frontend** React CRA + Tailwind + shadcn/ui + lucide-react + framer-motion + d3 + react-pdf.
  - Routes: `/` (projects list), `/project/:id` (tabs Baca/Bandingkan/Tanya), `/project/:id/doc/:docId` (dual panel reader).
  - PDF highlight: react-pdf + absolute-positioned overlay rectangles with scaled coordinates.

## Personas
- Postgraduate students conducting literature reviews
- Faculty researchers verifying claims across journals
- Academic peer reviewers cross-checking citations

## Core Requirements (static)
1. Per-document summary panel — single journal, never combined
2. Tiered evidence (high/medium/low) with on-PDF highlight overlay
3. Outlier detection across the project's documents
4. Comparison matrix (objective, method, sample, key_finding, limitation)
5. Cross-document Q&A with source citations and overall evidence tier
6. Project CRUD with cascade delete

## Implemented (2026-06-30)
- [x] Backend: Project CRUD with cascade-delete
- [x] Backend: PDF upload + background processing (parse, summary, claims)
- [x] Backend: Per-document summary + claims endpoint
- [x] Backend: Tiered evidence finder via BM25 + LLM verdict
- [x] Backend: Outlier scoring (cosine similarity over TF vectors)
- [x] Backend: Comparison matrix extraction
- [x] Backend: Cross-document QA with citations + overall tier
- [x] Backend: Serve raw PDF for canvas overlay alignment
- [x] Frontend: Projects landing page (hero + Lima Pilar + project cards)
- [x] Frontend: Project page with Tabs Baca / Bandingkan / Tanya
- [x] Frontend: Upload dropzone + status polling (processing / ready / failed)
- [x] Frontend: Dual-panel DocumentReader (react-pdf + claim cards + evidence cards + overlay highlights)
- [x] Frontend: D3 OutlierMap with hover tooltip
- [x] Frontend: MatrixView with quote sidebar
- [x] Frontend: Tanya Pustaka — chat-style answer card with citation tiers
- [x] Sonner toasts, shadcn Dialog/Tabs/Input/Textarea/Button used
- [x] data-testid attributes throughout
- [x] 14/14 backend tests + full frontend flow passed by testing agent

## Known limitations / deferred (P1)
- **Title detection** falls back to longest sentence in top-third of page 1 when PDF metadata is missing — works but not always accurate.
- **No GPU embeddings** — BM25 is lexical only; semantic recall for paraphrased claims may miss. Future: ship local sentence-transformers MiniLM if disk budget permits.
- **Outlier 2D layout** uses (similarity-to-centroid, doc length) — could be MDS over the full similarity matrix.
- **Multi-worker** processing not supported (FastAPI BackgroundTasks is in-process). Fine for single-user MVP.
- **Highlight precision** uses line-level bbox; sentence-level bbox would need OCR-quality line splitting per glyph (Docling could do this, but it pulled 4GB of CUDA deps and was uninstalled).

## Backlog (P2)
- Authentication (currently single-user) — JWT or Emergent Google Auth
- Reuse matrix output across sessions (cache per document)
- Export matrix to CSV / Markdown
- Side-by-side claim ↔ evidence diff view
- Project tags / search
- Highlight color-blind alt mode (already accessible via icons)

## Next Actions
- Tune title-extraction heuristic for two-column PDFs
- Add a "preview claim card" tooltip on outlier-map hover linking to the relevant document
- Add a small fallback citation in qa_service when the model omits used_sources but excerpts exist (raised in code review)
