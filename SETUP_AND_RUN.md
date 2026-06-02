# Pinbook — Setup & Run Guide

## ✅ Changes Made

### 1. **index.html** - Fixed Static File Paths
- Changed `css/style.css` → `static/style.css`
- Changed `js/app.js` → `static/app.js`

**Why:** Frontend assets are served from the `static/` directory via FastAPI's StaticFiles mount.

### 2. **requirements.txt** - Pinned Dependency Versions
Updated all packages with specific versions for reproducibility:
```
fastapi==0.104.1
uvicorn==0.24.0
pandas==2.1.4
openpyxl==3.1.2
python-multipart==0.0.6
requests==2.31.0
python-dotenv==1.0.0
openai==1.3.0
beautifulsoup4==4.12.2
duckduckgo-search==3.9.10
```

### 3. **api.py** - No Changes Needed
- Already has all required endpoints properly defined
- Correctly mounts the `static/` directory
- CORS is enabled for development/production

---

## 🚀 Quick Start

### Windows (PowerShell)

#### 1. Create Virtual Environment
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

#### 2. Install Dependencies
```powershell
pip install -r requirements.txt
```

#### 3. Set Up Environment Variables
Create a `.env` file in the project root with:
```env
# MapmyIndia (for PIN code resolution)
MAPPLS_CLIENT_ID=your_mappls_client_id
MAPPLS_CLIENT_SECRET=your_mappls_client_secret

# Azure OpenAI (for leadership search & AI features)
AZURE_OPENAI_API_KEY=your_azure_openai_api_key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=your_deployment_name
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# Optional: Google Places (nearby businesses)
GOOGLE_PLACES_API_KEY=your_google_places_api_key

# Optional: ContactOut API (LinkedIn enrichment)
CONTACTOUT_API_KEY=your_contactout_api_key
```

#### 4. Run the Backend
```powershell
python -m uvicorn api:app --reload --host 127.0.0.1 --port 8000
```

The app will be available at: **http://127.0.0.1:8000**

---

### macOS / Linux

#### 1. Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
```

#### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

#### 3. Set Up Environment Variables
```bash
# Create .env file
cat > .env << 'EOF'
MAPPLS_CLIENT_ID=your_mappls_client_id
MAPPLS_CLIENT_SECRET=your_mappls_client_secret
AZURE_OPENAI_API_KEY=your_azure_openai_api_key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=your_deployment_name
AZURE_OPENAI_API_VERSION=2024-02-15-preview
GOOGLE_PLACES_API_KEY=your_google_places_api_key
CONTACTOUT_API_KEY=your_contactout_api_key
EOF
```

#### 4. Run the Backend
```bash
python -m uvicorn api:app --reload --host 127.0.0.1 --port 8000
```

The app will be available at: **http://127.0.0.1:8000**

---

## 📡 API Endpoints

All endpoints are consumed by the frontend (`static/app.js`):

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/` | Serves `index.html` |
| GET | `/api/search/{pincode}` | Resolve PIN → location + demographics |
| GET | `/api/charts/demographics/{pincode}` | Demographics chart data |
| GET | `/api/charts/education?state=` | Education funnel data |
| GET | `/api/charts/industrial?state=&gender=&tru=` | Industry breakdown (HHI/Non-HHI) |
| GET | `/api/charts/occupation?state=&gender=&worker_type=` | Occupation distribution |
| GET | `/api/places?lat=&lng=&keyword=` | Nearby businesses (Google Places + OSM fallback) |
| POST | `/api/leadership` | AI-powered leadership search |
| GET | `/static/*` | Static files (CSS, JS, etc.) |

---

## 🧪 Testing

### Test PIN Code
Once the backend is running, try this PIN code: `110001` (New Delhi)

1. Open http://127.0.0.1:8000
2. Enter PIN: `110001`
3. Click "Analyze Location"
4. Select modules (Demographics, Industry, Businesses, Lead Intelligence)
5. Click "Continue" to view insights

### API Test (Curl/PowerShell)
```powershell
# Test PIN resolution
curl.exe "http://127.0.0.1:8000/api/search/110001"

# Test education data
curl.exe "http://127.0.0.1:8000/api/charts/education?state=DELHI"

# Test nearby places
curl.exe "http://127.0.0.1:8000/api/places?lat=28.6139&lng=77.2090&keyword=bank"
```

---

## 📦 Data Files Required

Ensure these files exist in the project root:
- ✅ `pincode.csv` - PIN code to location mapping
- ✅ `pca_demographics.xlsx` - Census demographics data
- ✅ `clean_census_combined.xlsx` - Census data with multiple sheets:
  - `education_level`
  - `industrial_category`
  - `occupation_classification`

---

## 🌐 Production Deployment (Render)

See `DEPLOYMENT.md` for Render.com deployment instructions.

Quick steps:
1. Push to GitHub
2. Connect repo to Render (use `render.yaml`)
3. Add environment variables in Render dashboard
4. Deploy!

---

## 🐛 Troubleshooting

### **ERROR: ModuleNotFoundError: No module named 'fastapi'**
→ Make sure you activated the virtual environment and ran `pip install -r requirements.txt`

### **ERROR: Could not find pincode.csv**
→ Make sure the data files are in the same directory as `api.py`

### **Frontend shows 404 Not Found**
→ Check that `index.html` is in the project root and `static/` folder exists

### **API calls timeout**
→ Google Places or Overpass might be rate-limited; check logs. App automatically falls back to OSM/Nominatim.

### **CORS errors in browser console**
→ CORS is configured in `api.py`. If issues persist, check that you're accessing via the same origin.

---

## 📝 Configuration

### Chart.js (Frontend)
- **Version:** 4.4.0 (CDN)
- **Charts Used:** Bar, Doughnut, Line
- **No additional setup needed** - loaded from CDN in `index.html`

### Design Tokens
- **Primary Blue:** `#005eac`
- **Font:** Inter (Google Fonts)
- **Border Radius:** 8-24px (CSS variables)
- **Shadows:** SM, MD, LG (CSS variables)

---

## 📚 Reference

- **Frontend:** `index.html`, `static/app.js`, `static/style.css`
- **Backend:** `api.py` (FastAPI + Pandas + Azure OpenAI)
- **Docs:** `README.md` (feature overview), `DEPLOYMENT.md` (production)

**Questions?** Check `README.md` for the product vision and module descriptions.
