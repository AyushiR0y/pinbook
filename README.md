# Pinbook — B2B Market Intelligence Platform

> **Turn a PIN code into actionable market intelligence.**

Pinbook is an enterprise-grade B2B web application that converts a 6-digit Indian PIN/postal code into structured market intelligence. Designed for corporate sales teams, strategy teams, and business analysts.

---

## 🎯 Product Goal

Start with a PIN code → selectively explore location demographics, industry landscape, nearby businesses, and leadership insights → redirect to **KnowYourLead** for deep lead profiling.

---

## ✅ Completed Features

### Screen 1 — Landing / Entry
- Centered white card on geospatial grid background
- 6-digit PIN code input with real-time validation
- Inline error messages (non-numeric, length < 6)
- Primary CTA disabled until valid PIN entered
- Enter key triggers analysis
- Trust footer with lock indicator

### Screen 2 — Insight Selection
- 2×2 multi-select card grid (Demographics, Industry, Businesses, Leads)
- Location pill shows resolved city/district after PIN lookup
- Continue button disabled until ≥1 module selected
- "Powered by KnowYourLead" badge on lead card

### Screen 3 — Insights Dashboard
- Sticky header with breadcrumb navigation (Pinbook > PIN XXXXXX)
- Hero banner with PIN, district, state, and active module tags
- **Module A — Demographics**: 5 KPI metrics, 6 charts (gender, age, social composition, literacy, workforce, workers by gender), education funnel
- **Module B — Industry**: HHI vs Non-HHI donut chart, top subcategories bar chart, occupation distribution bar chart with worker-type filter
- **Module C — Businesses**: keyword search + quick chips, 4 summary metrics, scrollable ranked list with distance/rating/category
- **Module D — Lead Intelligence**: KnowYourLead platform banner, company search with AI-powered leadership results, LinkedIn resolution badges, KYL deep-link CTA

### Screen 4 — KYL Transition Overlay
- Modal overlay with animated icon
- Context card (source: Pinbook, PIN, location)
- Continue → opens KnowYourLead in new tab with context params
- Cancel dismisses overlay

---

## 🗂 File Structure

```
index.html          — Main single-page application (4 screens)
css/
  style.css         — Full enterprise design system & component styles
js/
  app.js            — Screen flow, API calls, chart rendering (Chart.js)
README.md
```

---

## 🌐 API Endpoints Consumed

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/search/{pincode}` | Resolves PIN → location + census demographics |
| GET | `/api/charts/demographics/{pincode}` | Gender, age, social, literacy, work charts |
| GET | `/api/charts/education?state=` | Education funnel data |
| GET | `/api/charts/industrial?state=&gender=&tru=` | HHI/Non-HHI industry breakdown |
| GET | `/api/charts/occupation?state=&gender=&worker_type=` | Occupation category data |
| GET | `/api/places?lat=&lng=&keyword=` | Nearby businesses (Google Places / OSM) |
| POST | `/api/leadership` | AI-powered leadership search with LinkedIn resolution |

---

## 🎨 Design System

| Token | Value |
|-------|-------|
| Primary Blue | `#005eac` |
| Primary Dark | `#004a8a` |
| Background | `#f0f5fb` |
| Surface | `#ffffff` |
| Text Primary | `#0d1b2e` |
| Font | Inter (Google Fonts) |
| Chart Library | Chart.js 4.4 |
| Icons | Font Awesome 6 |

---

## 🔗 KnowYourLead Integration

- Clicking "Open KnowYourLead" or individual lead "KnowYourLead" buttons opens the transition overlay
- On confirm, opens `https://knowyourlead.ai?source=pinbook&context=...` in a new tab
- Context string includes: `Pinbook – PIN XXXXXX – District State`

**Update the `KYL_URL` constant in `js/app.js`** to point to the real KnowYourLead deployment.

---

## ⚙️ Backend Requirements

This frontend expects a **FastAPI** backend running at the same origin:
- `pincode.csv` — PIN → lat/lng/district/state mapping
- `pca_demographics.xlsx` — Census district-level PCA data
- `clean_census_combined.xlsx` — Education, industrial, occupation sheets
- Google Places API key (optional, falls back to OSM Overpass)
- Azure OpenAI credentials (optional, for leadership AI search)

---

## 🚀 Deployment

To publish this frontend, go to the **Publish tab** in Genspark.

For local development, serve via FastAPI (`uvicorn app:app --reload`) which also serves `index.html` at `/`.

---

## 📋 Recommended Next Steps

1. Update `KYL_URL` in `js/app.js` to real KnowYourLead domain
2. Add `favicon.ico` with Pinbook brand icon
3. Add events module (using `/api/events` endpoint already in backend)
4. Add export-to-PDF / share report functionality
5. Add saved searches / bookmarked PINs using browser localStorage
6. Add map view for businesses using Leaflet.js
7. Integrate ContactOut credit display in the Leads module
