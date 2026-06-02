# Quick Start — After Fixes

## Run Backend
```powershell
# Windows PowerShell
.\venv\Scripts\Activate.ps1
python -m uvicorn api:app --reload --host 127.0.0.1 --port 8000
```

```bash
# macOS / Linux
source venv/bin/activate
python -m uvicorn api:app --reload --host 127.0.0.1 --port 8000
```

Then open: **http://127.0.0.1:8000**

---

## What Was Fixed

### 1. SSL Certificate Error ✅
**Before:** Businesses search failed with SSL error  
**After:** Fallback to OSM works seamlessly

### 2. Color Scheme ✅
**Before:** KnowYourLead was purple  
**After:** KnowYourLead is now orange (#F58220)

### 3. Education Chart ✅
**Before:** Horizontal bar chart  
**After:** Funnel chart (sorted by population)

### 4. Occupation Charts ✅
**Before:** Single chart  
**After:** 2-chart layout with worker type breakdown

---

## Test Pins
- **Delhi:** `110001` (for lead intelligence)
- **Pune:** `411001` (for businesses search)
- **Bangalore:** `560034` (for demographics/education)
- **Bombay:** `400001` (for industry/occupation)

---

## Browser Tips
- **Clear Cache:** Ctrl+Shift+Delete → Clear all data
- **DevTools:** F12 → Console to see any errors
- **Mobile:** Ctrl+Shift+M to test responsive design

---

## Files Changed
- `api.py` — SSL fix + worker type breakdown
- `app.js` — Funnel chart + worker type doughnut
- `style.css` — Orange color theme
- `index.html` — 2-column occupation layout

See **FIXES_APPLIED.md** for detailed changes.
