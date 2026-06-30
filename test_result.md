#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================
# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
# Main agent should send test plans, and the testing agent should return results.

# Testing Protocol:
# 1. Always test BACKEND first using `deep_testing_backend_v2`
# 2. After backend testing, ask user before frontend testing using ask_human tool
# 3. Only test frontend if user explicitly requests

# Incorporate User Feedback:
# - Read user feedback carefully and prioritize bug fixes mentioned by user
# - Address issues reported by testing agents before adding new features

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

user_problem_statement: |
  Major refactor: REPLACE Workspace tab with new "Check & Fix" tab.
  - Tab renames: Baca -> Pustaka (now also hosts OutlierMap), Bandingkan -> Matriks
    (Matrix only), keep Tanya, NEW tab "Check & Fix" (data-testid="tab-check-fix").
  - Check & Fix: user pastes text from another AI (ChatGPT/Claude/...). Backend
    slices it into meaningful units (paragraph or list items; if a paragraph has
    >5 sentences split into sub-units of 2-3 sentences), then runs BM25 over the
    project's documents and classifies each unit as:
      * supported (>=1.0 normalized score) -> green + auto citation badge
      * similar   (>=0.35) -> yellow
      * unsupported (<0.35) -> red + "did you mean ..." suggestions if any score
        >= 0.15 was found.
  - Optional bibliography textarea boosts confidence via lexical overlap.
  - Reference Manager + Evidence Detector panels reused.
  - Export Markdown / Plain Text of the verification report.
  - Quality indicator on each document in Pustaka (score, label, tables/figures).
  - Removed: all Workspace endpoints + service + frontend folder, all
    "Sisipkan ke Workspace" buttons.

backend:
  - task: "POST /api/projects/{id}/check + GET /api/projects/{id}/check"
    implemented: true
    working: "NA"
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: |
          New endpoint runs verification_service.check_text and persists a single
          per-project run in collection check_runs. GET returns the last run with
          exists flag. Removed all workspace_* endpoints.
  - task: "verification_service.split_into_units paragraph + list slicing"
    implemented: true
    working: "NA"
    file: "/app/backend/app/services/verification_service.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: |
          Splits by double-newline paragraphs. List-detect via "- " "* " or "N." prefix.
          For paragraphs with >5 sentences, slices into sub-units of MIN 2 sentences
          (3 if 6+ remaining). Returns [{kind, text, list_kind}].
  - task: "verification_service.check_text BM25 thresholds + bibliography boost"
    implemented: true
    working: "NA"
    file: "/app/backend/app/services/verification_service.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: |
          BM25 score / num_query_tokens; thresholds 1.0 (supported) and 0.35
          (similar). Bibliography overlap multiplicative boost (1 + ratio).
          Creates citation badge for supported and similar units. Provides
          suggestions for unsupported when any retrieved hit had score_ratio
          >= 0.15.
  - task: "Sentence detail returns full sentence (regression)"
    implemented: true
    working: "NA"
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "medium"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Kept GET /api/documents/{id}/sentence/{sentence_id} unchanged."
  - task: "PDF quality metrics in document parsing"
    implemented: true
    working: "NA"
    file: "/app/backend/app/services/pdf_parser.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: |
          parse_pdf now returns 'quality' = {score (0-100), pages_with_text,
          total_pages, tables_count, figures_count, label}. Label is
          good (>=80), fair (>=50), poor (<50). figures_count counts image
          blocks per PyMuPDF; tables_count counts pages that contain a
          "Table N" caption. Persisted into documents.quality during processing.
  - task: "POST /api/settings/test-api-key (regression)"
    implemented: true
    working: "NA"
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "medium"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Unchanged from prior round."
  - task: "Cascade-delete check_runs on project delete"
    implemented: true
    working: "NA"
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "low"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "DELETE /projects/{id} now also clears check_runs."

frontend:
  - task: "Check & Fix tab + 3-panel UI"
    implemented: true
    working: "NA"
    file: "/app/frontend/src/components/CheckFix/CheckFix.jsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: |
          Tab data-testid="tab-check-fix". CheckFixEditor textarea + bibliography
          textarea + Periksa Sekarang button + summary stats + annotated HTML
          (color-coded supported/similar/unsupported). Right panels: ReferenceManager
          + EvidenceDetector with badge clicking.
  - task: "Quality indicator in Pustaka list"
    implemented: true
    working: "NA"
    file: "/app/frontend/src/pages/ProjectPage.jsx"
    stuck_count: 0
    priority: "medium"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: |
          QualityIndicator component renders below each ready document with score
          bar (green/amber/rose), label, tables/figures count, and a warning icon
          when label=='poor'. data-testid="doc-quality-<id>".
  - task: "Removed all Sisipkan ke Workspace buttons"
    implemented: true
    working: "NA"
    file: "/app/frontend/src/components/SummaryPanel.jsx /app/frontend/src/components/MatrixView.jsx /app/frontend/src/components/AskPanel.jsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "No more references to Workspace anywhere in frontend."

metadata:
  created_by: "main_agent"
  version: "4.0"
  test_sequence: 4
  run_ui: false

test_plan:
  current_focus:
    - "POST /api/projects/{id}/check + GET /api/projects/{id}/check"
    - "verification_service.split_into_units paragraph + list slicing"
    - "verification_service.check_text BM25 thresholds + bibliography boost"
    - "PDF quality metrics in document parsing"
  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
  - agent: "main"
    message: |
      Major refactor delivered:
      1) DELETED all Workspace endpoints + synthesis_service.py + frontend folder
         + "Sisipkan ke Workspace" buttons. No regression to existing
         /documents, /projects, /qa, /matrix endpoints.
      2) NEW endpoint POST /api/projects/{id}/check accepts
         {text, bibliography?, document_ids?, citation_format?} -> returns
         {units[], summary{total,supported,similar,unsupported},
          annotated_html, badges[], references_used[]}.
         Persists last run to collection check_runs.
      3) GET /api/projects/{id}/check returns last run with exists flag.
      4) split_into_units logic (Revision B):
         - paragraphs split by \n\n
         - paragraph with >5 sentences => sub-units of 2-3 sentences (min 2)
         - list lines ("- " or "* " or "N. ") each become a list_item unit
         - short paragraphs untouched
      5) BM25 thresholds 1.0 / 0.35 for supported / similar. Bibliography
         lexical overlap boosts effective score multiplicatively.
      6) Sentence detail endpoint preserved (full sentence text).
      7) PDF quality metrics computed at parse time and stored under
         documents.quality = {score, pages_with_text, total_pages,
         tables_count, figures_count, label}.
      8) check_runs cleared on DELETE /projects/{id}.

      Please verify backend end-to-end. To test /check meaningfully you need at
      least 1 ready PDF; create one with PyMuPDF as in prior rounds.
