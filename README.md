# JurnalMap — Verifiable Literature Analysis

> **AI menulis, JurnalMap memverifikasi.**
> Alat bantu peneliti untuk mengunggah puluhan PDF jurnal ilmiah, membangun peta hubungan antar-paper, meringkas dengan sitasi bukti, mengekstrak matriks perbandingan, menjawab pertanyaan bebas, dan memeriksa teks yang ditulis AI terhadap literatur sumber — semuanya dengan **evidence-first design**: setiap klaim dapat diklik untuk menuju kalimat asalnya.

![Evidence, not verdicts](https://img.shields.io/badge/philosophy-evidence--first-black)
![Docker](https://img.shields.io/badge/deploy-docker--compose-blue)
![License](https://img.shields.io/badge/status-MVP-orange)

---

## Value Proposition

Sebagian besar tool riset AI hanya menghasilkan ringkasan yang **tampak** meyakinkan tapi sulit diverifikasi. JurnalMap membalik urutannya: ringkasan, jawaban, dan matriks perbandingan **selalu** memuat sitasi klik-ke-sumber. Anda melihat kalimat asli dengan sorotan tepat sebelum mempercayai jawaban AI. Ini penting saat literatur review dijadikan dasar keputusan penelitian atau publikasi.

---

## 🌟 Fitur Utama (6 Tab)

| Tab | Deskripsi |
|:--|:--|
| **📄 Pustaka** | Daftar dokumen dengan pill status antrean (`Menunggu 2/5…`, `Memproses 1/5…`), tombol *Proses Kembali* untuk file gagal, dan integrasi drag-and-drop multi-file. |
| **📖 Baca + Network Graph** | Reader PDF di kiri, ringkasan on-demand + klaim + evidence di kanan. Di bagian atas: **Peta Penelitian** otomatis dengan node = paper, edge = composite similarity > 0.7. |
| **📊 Matriks** | Tabel perbandingan lintas paper untuk objective / method / dataset / results / limitations. Klik sel → evidence dengan halaman PDF. |
| **💬 Tanya** | Multi-doc QA berbasis retrieval + LLM. Pilih bahasa jawaban (Indonesia / English). Setiap jawaban disertai sitasi angka yang bisa diklik. |
| **🔍 Check & Fix** | Tempel teks yang ditulis AI (misal ChatGPT) + daftar pustaka opsional. JurnalMap mendeteksi klaim tanpa sitasi, klaim yang bertentangan dengan literatur (NLI), dan menyarankan perbaikan. |
| **⚙️ Settings** | Tema (Terang/Gelap/Sistem), bahasa antarmuka, bahasa keluaran AI, konfigurasi **kunci API LLM Cloud mandiri** (Gemini, OpenAI, Anthropic), serta integrasi model lokal. |

---

## 🥇 Kelebihan dibanding Tools Lain

- **Klik-to-source evidence.** Setiap klaim, kalimat ringkasan, dan sitasi jawaban dapat diklik untuk melihat kalimat asli dari PDF, lengkap dengan nomor halaman. Bukan sekadar hyperlink — ada highlight & confidence tier (high/medium/low).
- **Deteksi kontradiksi NLI.** Modul *Check & Fix* menggunakan reasoning untuk menandai klaim yang **berlawanan** dengan literatur, bukan sekadar sitasi hilang.
- **Multi-bahasa native.** Semantic similarity via `paraphrase-multilingual-MiniLM-L12-v2` mendukung Bahasa Indonesia + English tanpa translation layer. Output ringkasan/jawaban dapat dipilih per fitur.
- **Composite similarity graph.** Peta Penelitian menggabungkan tiga sinyal (`0.5 · semantic + 0.3 · keyword_jaccard + 0.2 · topic_match`) untuk mengungkap kelompok tematik & outlier — lebih tahan noise dibanding cosine murni.
- **Keamanan Kunci API Mandiri.** API Key cloud disimpan dengan aman di database terenkripsi per pengguna, sehingga institusi tidak perlu menanggung biaya pemakaian global.
- **Opsi Model Lokal (Admin-controlled).** Administrator dapat mengaktifkan LLM lokal (seperti Ollama / vLLM) yang dapat langsung diakses oleh seluruh pengguna tanpa konfigurasi tambahan di sisi client.

---

## 🛠️ Tech Stack

| Layer | Teknologi |
|:--|:--|
| **Frontend** | React 19 (CRA), Tailwind CSS v3, shadcn/ui, D3.js (force-directed graph), Sonner (toasts), React Router v6 |
| **Backend** | FastAPI 0.110, Uvicorn, Motor (async MongoDB), Pydantic v2, PyMuPDF, rank_bm25 |
| **AI** | Google Gemini / OpenAI / Anthropic (via API key user), sentence-transformers, `openai` SDK untuk Ollama compat |
| **Storage** | MongoDB 7.0, disk volume untuk uploads + model cache |
| **Auth** | JWT (python-jose) + bcrypt, password lockout policy |
| **Deploy** | Docker Compose (frontend Nginx, backend Uvicorn, mongo, opsional ollama) |

---

## 🚀 Cara Deploy dengan Docker

### Quick Start

```bash
git clone <repo-url> jurnalmap && cd jurnalmap
cp .env.example .env
# Edit .env: isi JWT_SECRET_KEY, ADMIN_PASSWORD
# Opsional: isi LOCAL_LLM_ENABLED=true jika ada Ollama
docker compose up -d --build
open http://localhost:3000
# Login: admin / <ADMIN_PASSWORD>
# Lalu buka Settings → API Keys dan masukkan kunci LLM Anda
```

Verifikasi:

```bash
curl http://localhost:8001/api/                    # {"app":"JurnalMap","status":"ok"}
curl http://localhost:8001/api/config | jq         # konfigurasi publik & supported providers
docker compose ps                                  # semua service harus healthy
```

### Opsi Ollama (Local LLM)

```bash
docker compose --profile ollama up -d
docker compose exec ollama ollama pull llama3.1:8b
# .env: LOCAL_LLM_ENABLED=true, LOCAL_LLM_NAME=llama3.1:8b
docker compose restart backend
```

Model `llama3.1:8b (local)` akan otomatis tersedia di dropdown Ringkasan/Tanya bagi seluruh user.

Panduan deploy lengkap: lihat `DEPLOY.md` atau `docker-compose.yml`.

---

## ⚙️ Konfigurasi Environment (`.env.example`)

Variabel yang wajib diisi ditandai **WAJIB**. Sisanya punya default aman.

| Variabel | Wajib | Default | Keterangan |
|:--|:-:|:--|:--|
| `JWT_SECRET_KEY` | **✅** | — | Rahasia untuk JWT. Gunakan `openssl rand -hex 32`. |
| `ADMIN_USERNAME` | | `admin` | Akun admin yang di-seed saat startup. |
| `ADMIN_PASSWORD` | **✅** | `admin` | **Wajib ubah di production.** |
| `ADMIN_EMAIL` | | `admin@jurnalmap.local` | Email admin. |
| `LOCAL_LLM_ENABLED` | | `false` | `true` untuk mengekspos Ollama/vLLM ke dropdown model. |
| `LOCAL_LLM_NAME` | | `gemma-llm` | Nama model lokal tampil di dropdown. |
| `OPENAI_BASE_URL` | | `http://ollama:11434/v1` | Endpoint OpenAI-compatible untuk local LLM. |
| `LOCAL_LLM_MODEL` | | `llama3.1:8b` | Model yang digunakan pada endpoint lokal. |
| `EMBEDDING_ENABLED` | | `true` | `false` = fallback ke TF-cosine. |
| `EMBEDDING_MODEL` | | `paraphrase-multilingual-MiniLM-L12-v2` | Model sentence-transformers. |
| `MONGO_INITDB_ROOT_USERNAME/PASSWORD` | | `admin` / `changeme` | Kredensial root Mongo. |
| `DB_NAME` | | `jurnalmap` | Nama database. |
| `MAX_FILES_PER_UPLOAD` | | `5` | Batas file per POST upload. |
| `MAX_UPLOAD_SIZE_MB` | | `50` | Batas ukuran per file. |
| `FRONTEND_PORT` / `BACKEND_PORT` | | `3000` / `8001` | Ubah bila konflik. |
| `REACT_APP_BACKEND_URL` | **✅** | `http://localhost:8001` | Baked ke bundle saat frontend di-build. Wajib benar sebelum `docker compose build`. |
| `CORS_ORIGINS` | | `*` | Di production: batasi ke domain frontend saja. |

> **Catatan:** Kunci API LLM (Gemini, OpenAI, Anthropic) dikonfigurasi **per pengguna** melalui halaman Settings di UI — bukan melalui environment variable.

---

## 📂 Struktur Proyek

```
jurnalmap/
├── backend/
│   ├── app/
│   │   ├── api/                    # (reserved for future routers)
│   │   ├── models/
│   │   │   ├── schemas.py          # Pydantic settings models
│   │   │   └── user.py             # User models
│   │   └── services/
│   │       ├── auth_service.py
│   │       ├── document_processor.py   # parse-only (queue worker calls this)
│   │       ├── queue.py                # single-worker FIFO async loop
│   │       ├── pdf_parser.py           # PyMuPDF
│   │       ├── retrieval.py            # BM25 + TF cosine
│   │       ├── network_service.py      # composite similarity graph
│   │       ├── summary_service.py
│   │       ├── evidence_service.py
│   │       ├── matrix_service.py
│   │       ├── qa_service.py
│   │       ├── verification_service.py # Check & Fix (NLI)
│   │       ├── cache.py                # BM25 Caching
│   │       └── llm.py                  # Gemini, OpenAI, Anthropic native adapter
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.js
│   │   ├── pages/                  # LoginPage, ProjectPage, DocumentReader, SettingsPage, ...
│   │   ├── components/             # SummaryPanel, AskPanel, NetworkGraph, MatrixView, CheckFix/, ...
│   │   ├── services/api.js
│   │   ├── store/                  # auth, settings (theme, ui_language)
│   │   └── lib/                    # i18n, useT, featureLanguage
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

## 🔒 Keamanan

- Semua endpoint (kecuali `/api/`, `/api/config`, `/api/auth/*`) memerlukan JWT.
- Ownership per user pada projects & documents (admin bypass untuk moderasi).
- Password minimal 8 karakter, wajib huruf besar + digit + simbol.
- Lockout otomatis 30 detik setelah 3 percobaan login gagal.
- Bcrypt hash, JWT expiry 24 jam (dapat dikonfigurasi).
- Upload dibatasi jenis PDF + ukuran maksimal (default 50MB, 5 file per batch).

---

## 📜 Lisensi

MVP internal — belum dirilis publik. Hubungi tim untuk kolaborasi.

---

**Motto:** *Evidence, not verdicts.*
