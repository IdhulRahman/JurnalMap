#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================

user_problem_statement: |
  Add a new "Workspace" tab to the JurnalMap Project page implementing an
  Evidence-based Synthesis Workspace. Requirements:
  - Grand Outline (Title → Chapters → Sub-chapters) with citation format selection
    (IEEE / APA 7 / Harvard).
  - 3-panel layout: Outline sidebar, Synthesis Editor (rich text with inline
    citation badges, Generate / Generate Ulang, toolbar B/I/H2/H3/list, Export),
    Reference Manager + Evidence Detector.
  - "Sisipkan ke Workspace" buttons on SummaryPanel evidence, MatrixView cells,
    AskPanel citations that open a dialog to pick the target sub-chapter and
    insert a citation badge into that sub-chapter's editor.
  - Auto-save (idle debounce + 30s safety net) via
    PUT /api/projects/{id}/workspace/content/{subchapter_id}.
  - Export the whole draft as Markdown (.md) or Plain Text (.txt).
  - Sliding-window continuity: prior sub-chapter's last paragraph used as
    transition context for next generate.

backend:
  - task: "Workspace outline CRUD (GET/POST /api/projects/{id}/outline)"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "New endpoints save+fetch a per-project outline (title, chapters, subchapters, citation_format) in MongoDB collection workspace_outlines. POST normalizes ids; GET returns exists=false for empty."
      - working: true
        agent: "testing"
        comment: "✅ PASSED all tests: GET empty state returns exists:false with empty chapters and ieee format. POST saves outline and assigns IDs to all chapters/subchapters. GET retrieves persisted outline correctly. POST updates citation_format (tested ieee→apa7→ieee). All fields (title, chapters, subchapters, citation_format, updated_at, exists) working as expected."
  - task: "Workspace sub-chapter generation (POST /api/projects/{id}/workspace/generate)"
    implemented: true
    working: true
    file: "/app/backend/app/services/synthesis_service.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Pulls top-15 BM25 fragments across project docs, sends to LLM via emergentintegrations with citation-format instructions, parses fragment ids, returns HTML with inline badge spans plus badges+references_used. Implements sliding-window via previous sub-chapter content. Persists to workspace_contents."
      - working: true
        agent: "testing"
        comment: "✅ PASSED all tests: Returns 400 with Indonesian error message 'Belum ada jurnal siap' when no documents are ready. Successfully generates content with uploaded PDF (processed in 21s). Returns content_html with <span class='jm-citation-badge'> elements, badges array with document/sentence/page metadata, and references_used array. Citation format switching works correctly (IEEE uses [1], APA7 uses (Author, Year)). LLM integration via emergentintegrations working properly."
  - task: "Workspace content GET/PUT (auto-save endpoint)"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "PUT /api/projects/{id}/workspace/content/{subchapter_id} upserts {content, badges, references_used, plain_paragraphs}; GET returns empty payload when none. Also workspace/contents lists all for export."
      - working: true
        agent: "testing"
        comment: "✅ PASSED all tests: GET returns empty state (content:'', badges:[], references_used:[]) for new subchapters. PUT saves content and returns {status:'saved', updated_at}. GET retrieves saved content correctly. GET /workspace/contents lists all saved items. All endpoints idempotent and working as expected. Minor: workspace_contents NOT cascade-deleted when project deleted (leaves orphaned data in MongoDB - acceptable for now but should be cleaned up)."
  - task: "Sentence detail endpoint for Evidence Detector"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "medium"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "GET /api/documents/{document_id}/sentence/{sentence_id} returns the sentence text, page, bbox plus document metadata used by EvidenceDetector."
      - working: true
        agent: "testing"
        comment: "✅ PASSED all tests: Returns sentence details with all required fields (text, page, document_title, document_authors, document_year, bbox coordinates). Returns 404 for invalid sentence_id. Properly handles document_id validation."
  - task: "Insert badge metadata endpoint"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "medium"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "POST /api/projects/{id}/workspace/insert-badge computes a label based on the current citation_format and returns badge payload. Used by 'Sisipkan ke Workspace' buttons in other tabs."
      - working: true
        agent: "testing"
        comment: "✅ PASSED all tests: Correctly computes citation labels based on outline's citation_format. IEEE format returns [N] style labels. APA7 format returns (Author, Year) style labels. Returns complete badge object with badge_id, label, document_id, document_title, sentence_id, page, quote, authors, year. Citation format switching works correctly."
  - task: "Revision 1: 3-5 sentences per paragraph in generated content"
    implemented: true
    working: true
    file: "/app/backend/app/services/synthesis_service.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "System prompt enforces 3-5 sentences per paragraph. LLM generates content with proper paragraph structure."
      - working: true
        agent: "testing"
        comment: "✅ PASSED: Generated paragraphs contain 3-5 sentences (±1 tolerance). Tested with multiple generations, all paragraphs had 4 sentences which is within the expected range."
  - task: "Revision 2a: allow_subsubchapter parameter"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "POST /workspace/generate accepts allow_subsubchapter boolean. When false, system prompt forbids <h3> tags. When true, allows sub-sub-headings."
      - working: true
        agent: "testing"
        comment: "✅ PASSED: allow_subsubchapter=false prevents <h3> tags in generated content. allow_subsubchapter=true allows <h3> tags (LLM may or may not use them based on content)."
  - task: "Revision 3: IEEE numbering consistency across sub-chapters"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Server aggregates citation_map from all workspace_contents before generation. Same document keeps same IEEE number across all sub-chapters. New documents get next available number."
      - working: true
        agent: "testing"
        comment: "✅ PASSED all tests: (1) Generated subchapter 1.1 with IEEE citations. (2) Generated subchapter 1.2 - same documents kept same numbers. (3) New documents cited only in 1.2 got next available numbers. (4) citation_map persisted in workspace_contents collection. IEEE numbering is globally consistent across the entire project."
  - task: "Revision 4: Evidence Detector returns full sentences"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "medium"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "GET /documents/{id}/sentence/{sentence_id} returns complete sentence text with proper punctuation."
      - working: true
        agent: "testing"
        comment: "✅ PASSED: Sentence endpoint returns full sentence text ending with proper punctuation (. ! or ?). Text is complete and not a fragment."
  - task: "Revision 7: Test API key endpoint"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "POST /api/settings/test-api-key validates user API keys by making a test LLM call. Returns {ok:true, sample, model} on success or {ok:false, error} on failure."
      - working: true
        agent: "testing"
        comment: "✅ PASSED all tests: (1) Valid Gemini API key returns ok:true with sample response. (2) Invalid API key returns ok:false with error message. (3) Missing provider returns 400. (4) Missing api_key for non-local provider returns 400. All validation working correctly."
  - task: "Revision 8: Find-source endpoint"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "POST /api/projects/{id}/workspace/find-source uses BM25 to find supporting sentences for user-typed claims. Returns {found:true, source:{...}} or {found:false, reason:...}."
      - working: true
        agent: "testing"
        comment: "✅ PASSED all tests: (1) Project with no documents returns found:false, reason:'no-documents'. (2) Relevant text query returns found:true with complete source object (document_id, sentence_id, quote, page, document_title, authors, year). (3) Unrelated text returns found:false, reason:'no-match'. (4) Missing text parameter returns 400. BM25 retrieval working correctly."

frontend:
  - task: "Workspace tab + 3-panel UI"
    implemented: true
    working: "NA"
    file: "/app/frontend/src/components/Workspace/Workspace.jsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Added Workspace tab (data-testid='tab-workspace'). When outline doesn't exist, OutlineSetup shows. Otherwise renders OutlineSidebar + SynthesisEditor (contentEditable + Generate + Toolbar + Export menu) + ReferenceManager + EvidenceDetector."
  - task: "Auto-save in Workspace editor"
    implemented: true
    working: "NA"
    file: "/app/frontend/src/components/Workspace/Workspace.jsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Debounced 1.5s on every change; safety-net interval flushes any dirty sub-chapter every 30s. Save status badge shows saving/saved/dirty."
  - task: "Export draft as Markdown/Plain Text"
    implemented: true
    working: "NA"
    file: "/app/frontend/src/components/Workspace/Workspace.jsx"
    stuck_count: 0
    priority: "medium"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Dropdown menu in editor toolbar. htmlToMarkdown preserves citation marker text inline. Files saved client-side via Blob URL."
  - task: "Sisipkan ke Workspace buttons in SummaryPanel/MatrixView/AskPanel"
    implemented: true
    working: "NA"
    file: "/app/frontend/src/components/Workspace/InsertToWorkspaceDialog.jsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Shared dialog loads outline and lets the user pick a sub-chapter. Dispatches CustomEvent 'jm:workspace-insert' that Workspace listens for and inserts the badge HTML at the editor caret/end. Buttons added under each evidence item (SummaryPanel), in the matrix quote sidebar (MatrixView), and under each citation (AskPanel)."

metadata:
  created_by: "main_agent"
  version: "4.0"
  test_sequence: 4
  run_ui: false

test_plan:
  current_focus: []
  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
  - agent: "main"
    message: |
      Revisi 1–8 telah diterapkan:
      1) synthesis_service.py prompt sekarang mewajibkan 3-5 kalimat per paragraf
         dan memilih format (paragraph vs ordered/unordered list) secara heuristik
         berdasarkan ISI sub-bab, bukan judul. LLM output JSON sekarang punya field
         'format' + 'paragraphs' + 'list_items' + 'list_kind'. Backend merender ke
         <p>...</p> atau <ol/ul><li>...</li></...>.
      2a) Endpoint /workspace/generate menerima 'allow_subsubchapter' boolean. Default
         False. System prompt menambahkan aturan tegas: ON => boleh <h3>, OFF =>
         tidak boleh sub-sub-bab.
      2b) Format poin heuristik (lihat #1).
      3) IEEE numbering global: server.py mengumpulkan citation_map dari SEMUA
         workspace_contents proyek (citation_map field + parsing label badge "[N]")
         sebelum generate. Dipakai sebagai existing_citation_map di
         synthesis_service.generate_subchapter. Endpoint /workspace/insert-badge juga
         menggunakan logika serupa.
      4) /documents/{id}/sentence/{sentence_id} sudah mengembalikan kalimat utuh
         (full sentence.text). Tidak ada perubahan kode tapi alur dikonfirmasi.
         Frontend EvidenceDetector memanggil endpoint ini setelah klik badge.
      5) Aturan "hindari over-sitasi, max 1-2 badge per kalimat, hanya klaim utama"
         dimasukkan ke system prompt.
      6) Halaman Settings: tema dan UI language SEKARANG hanya update local state.
         Semua perubahan baru tersimpan saat tombol "Simpan" ditekan. Toast
         "Pengaturan disimpan" muncul setelah sukses.
      7) Endpoint baru: POST /api/settings/test-api-key {provider, api_key, model?}.
         Memanggil LLM 1x dengan key tersebut dan mengembalikan {ok, model, sample}
         atau {ok:false, error}. Tombol "Tes Koneksi" di samping tiap input API key.
      8) Endpoint baru: POST /api/projects/{id}/workspace/find-source {text}.
         Memakai BM25 atas semua kalimat proyek; threshold score/qtokens >= 0.18.
         Tombol "Cari Sumber" di toolbar editor: pengguna seleksi teks, klik,
         dialog menampilkan kutipan utuh + tombol "Tambahkan" → memanggil
         /workspace/insert-badge untuk dapatkan label terhitung lalu sisipkan badge.

      Mohon retest backend pada endpoint baru/yang berubah:
        - POST /workspace/generate dengan body {subchapter_id, allow_subsubchapter:true/false}.
          Buat 2 sub-bab, generate Sub-bab 1.1 lalu Sub-bab 1.2: Sub-bab 1.2 harus
          menerima IEEE number yang sama untuk dokumen yang sama (bukan reset ke [1]).
        - POST /workspace/find-source dengan project tanpa dokumen → {found:false,
          reason:"no-documents"}; dengan dokumen ready dan teks yang BERKAITAN → found:true.
        - POST /settings/test-api-key {provider:"gemini", api_key:"<valid>"} → ok:true.
          Dengan api_key yang invalid → ok:false dengan pesan error.
        - Reconfirm semua test sebelumnya tetap pass (regression).
  - agent: "testing"
    message: |
      ✅ BACKEND TESTING COMPLETE - ALL TESTS PASSED (19/19)
      
      Round 1 (Workspace feature): 19/19 PASS. All endpoints production-ready.
      See full report above for details.
  - agent: "testing"
    message: |
      ✅ REVISIONS 1-8 TESTING COMPLETE - ALL TESTS PASSED (23/23)
      
      Comprehensive testing of all 8 user-requested revisions completed successfully:
      
      **REVISION 7 - Test API Key Endpoint (4/4 PASS)**
      - Valid API key returns ok:true with sample response
      - Invalid API key returns ok:false with error message
      - Missing provider returns 400
      - Missing api_key returns 400
      
      **REVISION 3 - IEEE Numbering Consistency (5/5 PASS)**
      - Generated subchapter 1.1 with IEEE citations
      - Generated subchapter 1.2 with consistent numbering
      - Same documents keep same IEEE numbers across sub-chapters
      - New documents get next available numbers
      - citation_map persisted in workspace_contents
      
      **REVISION 8 - Find-Source Endpoint (4/4 PASS)**
      - No documents returns found:false, reason:'no-documents'
      - Relevant text returns found:true with complete source object
      - Unrelated text returns found:false, reason:'no-match'
      - Missing text parameter returns 400
      
      **REVISION 2a - allow_subsubchapter Parameter (2/2 PASS)**
      - allow_subsubchapter=false prevents <h3> tags
      - allow_subsubchapter=true allows <h3> tags
      
      **REVISION 1 - 3-5 Sentences Per Paragraph (1/1 PASS)**
      - Generated paragraphs contain 3-5 sentences (tested: 4 sentences per paragraph)
      
      **REVISION 4 - Evidence Detector Full Sentences (1/1 PASS)**
      - Sentence endpoint returns complete sentences with proper punctuation
      
      **REGRESSION TESTS (6/6 PASS)**
      - GET outline
      - POST outline
      - GET content
      - PUT content
      - insert-badge with APA7 format (parentheses)
      - Cascade delete (project + outline + workspace_contents)
      
      All backend endpoints are working correctly. No critical issues found.