# JurnalMap

Platform analisis jurnal ilmiah berbasis AI. Upload PDF jurnal ilmiah, lalu sistem akan merangkum, mengekstrak klaim, mencari evidence, membangun comparison matrix, menjawab pertanyaan, dan memverifikasi teks AI — semuanya menggunakan berbagai LLM (Gemini, OpenAI, Anthropic, atau model lokal via Ollama).

---

## 🏗️ Arsitektur

```
Browser (React 19) ──HTTP──▶ FastAPI (Uvicorn) ──Motor──▶ MongoDB
                                   │
                              app/services/
                              ├── pdf_parser.py    (PyMuPDF)
                              ├── llm.py           (Emergent/OpenAI/Anthropic/Local)
                              ├── summary_service.py
                              ├── evidence_service.py
                              ├── outlier_service.py
                              ├── matrix_service.py
                              ├── qa_service.py
                              └── verification_service.py
```

---

## 🚀 Cara Menjalankan dengan Docker (Production)

### Prasyarat

- [Docker](https://docs.docker.com/get-docker/) ≥ 24
- [Docker Compose](https://docs.docker.com/compose/install/) V2

### Langkah

**1. Clone repository:**
```bash
git clone https://github.com/IdhulRahman/JurnalMap1.git
cd JurnalMap1
```

**2. Siapkan file `.env`:**
```bash
cp .env.example .env
```

Edit `.env` dan isi nilai yang diperlukan:
```bash
# Wajib diisi:
MONGO_INITDB_ROOT_PASSWORD=your_strong_password_here
EMERGENT_LLM_KEY=your_emergent_api_key_here
REACT_APP_BACKEND_URL=http://localhost:8001   # atau URL domain Anda
CORS_ORIGINS=http://localhost:3000            # atau domain frontend Anda
```

**3. Build dan jalankan:**
```bash
docker compose up -d --build
```

**4. Cek status:**
```bash
docker compose ps
# Semua service harus menampilkan status "healthy"

docker compose logs -f backend   # lihat log backend
```

**5. Akses aplikasi:**
- **Frontend:** [http://localhost:3000](http://localhost:3000)
- **Backend API:** [http://localhost:8001/api/](http://localhost:8001/api/)
- **API Docs (Swagger):** [http://localhost:8001/docs](http://localhost:8001/docs)

**6. Hentikan aplikasi:**
```bash
docker compose down          # hentikan (data tetap tersimpan)
docker compose down -v       # hentikan + hapus semua data (HATI-HATI!)
```

---

## 💻 Cara Menjalankan Tanpa Docker (Development)

### Prasyarat

- Python 3.11+
- Node.js 20+
- Yarn 1.22+
- MongoDB 7.0 (lokal atau MongoDB Atlas)

### Backend

```bash
# 1. Masuk ke folder backend
cd backend

# 2. Buat virtual environment
python -m venv venv
source venv/bin/activate       # Linux/Mac
# atau
venv\Scripts\activate          # Windows

# 3. Install dependencies
pip install -r requirements.txt
pip install openai>=1.0.0      # Diperlukan untuk local LLM

# 4. Buat file .env di folder backend/
cat > .env << EOF
MONGO_URL=mongodb://localhost:27017/jurnalmap
DB_NAME=jurnalmap
EMERGENT_LLM_KEY=your_emergent_llm_key_here
CORS_ORIGINS=http://localhost:3000
UPLOAD_DIR=./uploads
EOF

# 5. Jalankan server
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

Backend berjalan di: [http://localhost:8001](http://localhost:8001)

### Frontend

```bash
# 1. Masuk ke folder frontend
cd frontend

# 2. Buat file .env di folder frontend/
cat > .env << EOF
REACT_APP_BACKEND_URL=http://localhost:8001
EOF

# 3. Install dependencies
yarn install

# 4. Jalankan development server
yarn start
```

Frontend berjalan di: [http://localhost:3000](http://localhost:3000)

---

## 🧪 Cara Menjalankan Tests

### Backend Tests

Tests memerlukan backend yang sedang berjalan dan database MongoDB.

```bash
# 1. Install test dependencies
pip install pytest pytest-xdist requests pymupdf python-dotenv

# 2. Pastikan backend berjalan (lihat di atas)

# 3. Jalankan tests
cd backend
REACT_APP_BACKEND_URL=http://localhost:8001 pytest tests/ -v

# Jalankan test spesifik:
pytest tests/test_jurnalmap_api.py -v

# Jalankan dengan lebih banyak output:
pytest tests/ -v -s --no-header
```

**Catatan:** Tests adalah end-to-end integration tests. Setiap test akan membuat data nyata di database dan memerlukan koneksi LLM yang valid.

### Frontend Tests

Belum ada frontend tests. Untuk menjalankan test runner kosong:
```bash
cd frontend
yarn test --watchAll=false
```

---

## 🌍 Environment Variables

### Backend (file `backend/.env` atau environment Docker)

| Variable | Wajib | Default | Deskripsi |
|----------|-------|---------|-----------|
| `MONGO_URL` | ✅ | — | MongoDB connection string |
| `DB_NAME` | ✅ | — | Nama database MongoDB |
| `EMERGENT_LLM_KEY` | ✅* | — | API key Emergent (*jika tidak ada user key) |
| `CORS_ORIGINS` | ✅ | `*` | Allowed origins, pisahkan dengan koma |
| `UPLOAD_DIR` | ❌ | `./uploads` | Path folder PDF uploads |
| `LLM_PROVIDER` | ❌ | `gemini` | Default LLM provider |
| `LLM_MODEL` | ❌ | `gemini-3-flash-preview` | Default LLM model |

### Frontend (baked saat build)

| Variable | Wajib | Deskripsi |
|----------|-------|-----------|
| `REACT_APP_BACKEND_URL` | ✅ | URL backend API (harus accessible dari browser) |

> **⚠️ Penting:** `REACT_APP_BACKEND_URL` di-bake ke dalam JavaScript bundle saat `yarn build`. Jika URL berubah, frontend harus di-rebuild.

---

## 📁 Struktur Project

```
JurnalMap1/
├── backend/
│   ├── app/
│   │   ├── models/
│   │   │   └── schemas.py          # Pydantic models
│   │   └── services/
│   │       ├── llm.py              # LLM adapter
│   │       ├── document_processor.py
│   │       ├── summary_service.py
│   │       ├── evidence_service.py
│   │       ├── outlier_service.py
│   │       ├── matrix_service.py
│   │       ├── qa_service.py
│   │       ├── verification_service.py
│   │       ├── pdf_parser.py
│   │       └── retrieval.py
│   ├── tests/                      # Backend integration tests
│   ├── uploads/                    # PDF files (gitignored)
│   ├── server.py                   # FastAPI entry point
│   ├── requirements.txt
│   ├── pytest.ini
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/                  # ProjectsPage, ProjectPage, etc.
│   │   ├── components/             # UI components
│   │   ├── services/api.js         # Axios API client
│   │   ├── store/settings.jsx      # Settings context
│   │   └── App.js
│   ├── public/
│   ├── package.json
│   ├── craco.config.js
│   ├── nginx.conf                  # Nginx config (production)
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 🐳 Docker — Tips Production

### Ganti URL backend setelah deploy

Jika domain backend berubah, rebuild frontend image dengan build arg baru:
```bash
docker compose build --build-arg REACT_APP_BACKEND_URL=https://api.yourdomain.com frontend
docker compose up -d frontend
```

### Lihat logs

```bash
docker compose logs -f              # semua services
docker compose logs -f backend      # backend saja
docker compose logs -f mongo        # MongoDB saja
```

### Akses MongoDB shell

```bash
docker compose exec mongo mongosh \
  -u admin -p your_password \
  --authenticationDatabase admin \
  jurnalmap
```

### Backup MongoDB

```bash
docker compose exec mongo mongodump \
  -u admin -p your_password \
  --authenticationDatabase admin \
  --db jurnalmap \
  --out /tmp/backup

docker cp jurnalmap-mongo:/tmp/backup ./backup-$(date +%Y%m%d)
```

---

## 🛡️ Catatan Keamanan

- **Autentikasi:** Aplikasi ini tidak memiliki sistem autentikasi bawaan. Untuk deployment publik, tambahkan autentikasi di layer nginx (Basic Auth) atau implementasikan JWT di backend.
- **CORS:** Pastikan `CORS_ORIGINS` diset ke domain spesifik, bukan `*`.
- **API Keys:** API keys pengguna (Gemini/OpenAI/Anthropic) disimpan di MongoDB. Untuk keamanan lebih tinggi, enkripsi keys sebelum menyimpan.
- **HTTPS:** Gunakan HTTPS di production. Konfigurasikan TLS di reverse proxy (nginx/caddy/traefik).
