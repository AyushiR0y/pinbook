import os
import math
import asyncio
import requests
import pandas as pd
import uvicorn
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel
import json
from openai import AzureOpenAI
from bs4 import BeautifulSoup

# Load Environment Variables
load_dotenv()

# --- Configuration ---
MAPPLS_CLIENT_ID = os.getenv("MAPPLS_CLIENT_ID")
MAPPLS_CLIENT_SECRET = os.getenv("MAPPLS_CLIENT_SECRET")

# Azure OpenAI Configuration
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
CONTACTOUT_API_KEY = os.getenv("CONTACTOUT_API_KEY")

# --- Data Loading (Global State) ---
print("Loading data files...")
pincode_df = None
pca_df = None
education_df = None
occupation_df = None
industrial_df = None

try:
    if os.path.exists("pincode.csv"):
        pincode_df = pd.read_csv("pincode.csv")
        pincode_df.columns = pincode_df.columns.str.strip().str.lower()
        pincode_df['district'] = pincode_df['district'].astype(str).str.strip().str.upper()
        pincode_df['statename'] = pincode_df['statename'].astype(str).str.strip().str.upper()
        print("✓ Pincode CSV Loaded")
except Exception as e:
    print(f"✗ Error loading pincode.csv: {e}")

try:
    if os.path.exists("pca_demographics.xlsx"):
        pca_df = pd.read_excel("pca_demographics.xlsx")
        pca_df.columns = pca_df.columns.str.strip()
        print("✓ PCA Excel Loaded")
except Exception as e:
    print(f"✗ Error loading pca_demographics.xlsx: {e}")

try:
    if os.path.exists("clean_census_combined.xlsx"):
        xls = pd.ExcelFile("clean_census_combined.xlsx")
        # Load specific sheets as requested
        if "education_level" in xls.sheet_names:
            education_df = pd.read_excel(xls, sheet_name="education_level")
            print("✓ Census: Education Level Loaded")
        if "industrial_category" in xls.sheet_names:
            industrial_df = pd.read_excel(xls, sheet_name="industrial_category")
            print("✓ Census: Industrial Category Loaded")
        if "occupation_classification" in xls.sheet_names:
            occupation_df = pd.read_excel(xls, sheet_name="occupation_classification")
            print("✓ Census: Occupation Classification Loaded")
except Exception as e:
    print(f"✗ Error loading clean_census_combined.xlsx: {e}")

# --- FastAPI App ---
app = FastAPI(title="LeadGen Backend API")

# Serve local static assets (used for a local copy of plotly if CDN is blocked)
if os.path.isdir('static'):
    app.mount('/static', StaticFiles(directory='static'), name='static')

# Enable CORS for the HTML Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# SERVE FRONTEND
# ==========================================
@app.get("/")
async def serve_frontend():
    """Serve the index.html frontend"""
    return FileResponse("index.html")

# ==========================================
# HELPER FUNCTIONS (From your request)
# ==========================================
def safe_int(value):
    """Safely convert numpy/pandas types to Python int"""
    try:
        return int(value) if pd.notna(value) else 0
    except:
        return 0

def safe_float(value):
    """Safely convert numpy/pandas types to Python float"""
    try:
        return float(value) if pd.notna(value) else 0.0
    except:
        return 0.0


def calculate_distance_km(source_lat: float, source_lng: float, target_lat: float, target_lng: float) -> float:
    """Calculate distance between two coordinates using Haversine formula."""
    radius = 6371  # Earth radius in km
    source_lat_rad = math.radians(source_lat)
    target_lat_rad = math.radians(target_lat)
    delta_lat = math.radians(target_lat - source_lat)
    delta_lng = math.radians(target_lng - source_lng)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(source_lat_rad) * math.cos(target_lat_rad) * math.sin(delta_lng / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c


def get_overpass_filters(keyword: str) -> List[str]:
    """Map UI lead keywords to Overpass filters for OSM fallback."""
    normalized = (keyword or "").strip().lower()

    filters_map = {
        "industry": [
            '"industrial"',
            '"man_made"="works"',
            '"office"="company"',
            '"shop"="wholesale"',
            '"craft"',
        ],
        "insurance agency": [
            '"office"="insurance"',
            '"amenity"="insurance"',
        ],
        "bank": [
            '"amenity"="bank"',
            '"amenity"="atm"',
            '"office"="financial"',
        ],
        "college": [
            '"amenity"="college"',
            '"amenity"="university"',
            '"amenity"="school"',
        ],
        "club gymkhana": [
            '"leisure"="sports_centre"',
            '"leisure"="fitness_centre"',
            '"leisure"="club"',
            '"amenity"="community_centre"',
        ],
    }

    if normalized in filters_map:
        return filters_map[normalized]

    keyword_safe = normalized.replace('"', '').strip()
    if keyword_safe:
        return [f'"name"~"{keyword_safe}",i']
    return []


def get_osm_address(tags: Dict[str, Any]) -> str:
    """Build a readable address from OSM tags."""
    if not tags:
        return "Address not available"

    parts = [
        tags.get("addr:housenumber", ""),
        tags.get("addr:street", ""),
        tags.get("addr:suburb", ""),
        tags.get("addr:city", ""),
        tags.get("addr:state", ""),
    ]
    address = ", ".join([part for part in parts if part])
    return address if address else tags.get("name", "Address not available")


def build_osm_types(tags: Dict[str, Any]) -> List[str]:
    """Build a compact list of OSM category tags."""
    return [
        value
        for value in [
            tags.get("amenity"),
            tags.get("shop"),
            tags.get("office"),
            tags.get("leisure"),
            tags.get("industrial"),
            tags.get("man_made"),
            tags.get("craft"),
        ]
        if value
    ]


def search_places_via_nominatim(lat: float, lng: float, keyword: str, radius_m: int = 10000, limit: int = 60) -> List[Dict[str, Any]]:
    """Fallback search using Nominatim when Overpass is rate limited."""
    try:
        delta_lat = radius_m / 111320.0
        delta_lng = radius_m / max(111320.0 * math.cos(math.radians(lat)), 1e-6)
        left = lng - delta_lng
        right = lng + delta_lng
        top = lat + delta_lat
        bottom = lat - delta_lat

        params = {
            "q": keyword,
            "format": "jsonv2",
            "limit": limit,
            "viewbox": f"{left},{top},{right},{bottom}",
            "bounded": 1,
            "addressdetails": 1,
        }
        headers = {
            "User-Agent": "leadgenerator/1.0 (nearby-business-fallback)",
        }
        response = requests.get("https://nominatim.openstreetmap.org/search", params=params, headers=headers, timeout=20)
        response.raise_for_status()
        data = response.json()
    except Exception as error:
        print(f"Nominatim fallback failed: {str(error)}")
        return []

    places = []
    for item in data:
        place_name = str(item.get("name") or item.get("display_name") or "").strip()
        if not place_name:
            continue

        place_lat = item.get("lat")
        place_lng = item.get("lon")
        if place_lat is None or place_lng is None:
            continue

        place_lat = float(place_lat)
        place_lng = float(place_lng)
        distance = calculate_distance_km(lat, lng, place_lat, place_lng)

        places.append(
            {
                "name": place_name,
                "address": str(item.get("display_name", "Address not available")),
                "dist": float(round(distance, 2)),
                "rating": "N/A",
                "place_id": f"osm:nominatim:{item.get('place_id', '')}",
                "types": [str(item.get("type", ""))] if item.get("type") else [],
                "lat": place_lat,
                "lng": place_lng,
            }
        )

    places.sort(key=lambda item: item["dist"])
    return places[:limit]


def search_places_via_osm(lat: float, lng: float, keyword: str, radius_m: int = 10000, limit: int = 60) -> List[Dict[str, Any]]:
    """Search nearby places using OSM Overpass as fallback when Google Places fails."""
    filters = get_overpass_filters(keyword)
    if not filters:
        return []

    query_blocks = []
    for filter_expr in filters:
        query_blocks.append(f"nwr[{filter_expr}](around:{radius_m},{lat},{lng});")

    overpass_query = f"""
    [out:json][timeout:25];
    (
      {''.join(query_blocks)}
    );
    out center;
    """

    overpass_endpoints = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass.private.coffee/api/interpreter",
    ]
    headers = {
        "User-Agent": "leadgenerator/1.0 (nearby-business-fallback)",
    }

    data = None
    for endpoint in overpass_endpoints:
        try:
            response = requests.post(endpoint, data={"data": overpass_query}, headers=headers, timeout=20)

            if response.status_code == 429:
                print(f"Overpass rate limited at {endpoint}")
                continue

            response.raise_for_status()
            data = response.json()
            if data.get("elements"):
                break
        except Exception as error:
            print(f"OSM Overpass endpoint failed ({endpoint}): {str(error)}")

    if not data:
        print("OSM Overpass failed on all endpoints, trying Nominatim fallback")
        return search_places_via_nominatim(lat, lng, keyword, radius_m=radius_m, limit=limit)

    places = []
    for element in data.get("elements", []):
        tags = element.get("tags", {})
        place_name = str(tags.get("name", "")).strip()
        if not place_name:
            continue

        place_lat = element.get("lat")
        place_lng = element.get("lon")

        if place_lat is None or place_lng is None:
            center = element.get("center", {})
            place_lat = center.get("lat")
            place_lng = center.get("lon")

        if place_lat is None or place_lng is None:
            continue

        distance = calculate_distance_km(lat, lng, float(place_lat), float(place_lng))
        places.append(
            {
                "name": place_name,
                "address": get_osm_address(tags),
                "dist": float(round(distance, 2)),
                "rating": "N/A",
                "place_id": f"osm:{element.get('type', 'node')}:{element.get('id', '')}",
                "types": build_osm_types(tags),
                "lat": float(place_lat),
                "lng": float(place_lng),
            }
        )

    places.sort(key=lambda item: item["dist"])
    if places:
        return places[:limit]

    print("OSM Overpass returned no places, trying Nominatim fallback")
    return search_places_via_nominatim(lat, lng, keyword, radius_m=radius_m, limit=limit)
def get_demographics_data(district_name, state_name):
    if pca_df is None: return None, "No Data"
    pca_df_copy = pca_df.copy()
    pca_df_copy['Name'] = pca_df_copy['Name'].astype(str).str.strip().str.upper()
    pca_df_copy['Level'] = pca_df_copy['Level'].astype(str).str.strip()
    pca_df_copy['TRU'] = pca_df_copy['TRU'].astype(str).str.strip()
    district_name_upper = str(district_name).strip().upper()
    
    district_data = pca_df_copy[
        (pca_df_copy['Name'] == district_name_upper) & 
        (pca_df_copy['Level'] == 'DISTRICT') &
        (pca_df_copy['TRU'] == 'Total')
    ]
    if not district_data.empty:
        return district_data.iloc[0], f"District: {district_name}"
    
    # Simple fallback logic (omitted long fuzzy match for brevity, keeping core logic)
    return None, "No Data"

def get_education_funnel_data(state_name):
    """Get education level data for funnel chart"""
    if education_df is None: return None
    edu_df_copy = education_df.copy()
    edu_df_copy['Area Name | Area Name'] = edu_df_copy['Area Name | Area Name'].astype(str).str.strip().str.upper()
    state_name_upper = str(state_name).strip().upper()
    
    state_data = edu_df_copy[
        (edu_df_copy['Area Name | Area Name'] == state_name_upper) & 
        (edu_df_copy['Total/Urban/Rural | Total/Urban/Rural'] == 'Total')
    ]
    if state_data.empty:
        state_data = edu_df_copy[
            (edu_df_copy['Area Name | Area Name'] == 'INDIA') & 
            (edu_df_copy['Total/Urban/Rural | Total/Urban/Rural'] == 'Total')
        ]
    if state_data.empty: return None
    
    row = state_data.iloc[0]
    funnel_data = []
    education_funnel_levels = [
        (['Literate without educational level | Persons', 'Below educational level | Persons'], 'Illiterate'),
        (['Matric/Secondary | Persons'], 'Matriculation'),
        (['Higher secondary/Intermediate Pre-University/Senior secondary | Persons'], 'HSC'),
        (['Non-technical diploma or certificate not equal to degree | Persons', 'Technical diploma or certificate not equal to degree | Persons'], 'Diploma'),
        (['Graduate & above | Persons', 'Post Graduate | Persons'], 'Graduate & above')
    ]
    try:
        for col_names, label in education_funnel_levels:
            total_val = 0
            for col_name in col_names:
                if col_name in edu_df_copy.columns:
                    total_val += pd.to_numeric(row.get(col_name, 0), errors='coerce') or 0
            if total_val > 0:
                funnel_data.append({'Education Level': label, 'Count': total_val})
    except: pass
    if funnel_data: return pd.DataFrame(funnel_data)
    return None

def get_filtered_industrial_data(state_name, religion=None, age_group=None, gender=None, level=None, tru=None):
    """Get filtered industrial category data"""
    if industrial_df is None: return None
    ind_df_copy = industrial_df.copy()
    ind_df_copy['Area Name | Area Name'] = ind_df_copy['Area Name | Area Name'].astype(str).str.strip().str.upper()
    state_name_upper = str(state_name).strip().upper()
    
    if state_name_upper in ind_df_copy['Area Name | Area Name'].values:
        filtered_data = ind_df_copy[ind_df_copy['Area Name | Area Name'] == state_name_upper]
    else:
        filtered_data = ind_df_copy[ind_df_copy['Area Name | Area Name'] == 'INDIA']
    
    if religion and religion != 'All':
        filtered_data = filtered_data[filtered_data['Religon | Religon'] == religion]
    if age_group and age_group != 'All':
        filtered_data = filtered_data[filtered_data['Age group | Age group'] == age_group]
    if level and level != 'All':
        filtered_data = filtered_data[filtered_data['Level | Level'] == level]
    if tru and tru != 'All':
        filtered_data = filtered_data[filtered_data['Total/Rural/Urban | Total/Rural/Urban'] == tru]
    return filtered_data

def create_industrial_breakdown(filtered_data, gender=None):
    """Logic to breakdown industrial data into HHI vs Non-HHI"""
    if filtered_data is None or filtered_data.empty: return None
    all_cols = filtered_data.columns.tolist()
    hhi_cols = []
    non_hhi_cols = []
    
    for col in all_cols:
        col_lower = str(col).lower()
        if any(x.lower() in col_lower for x in ['Area Name', 'Religon', 'Age group', 'Level', 'Total/Rural/Urban']):
            continue
        if gender == 'Male':
            if ('males' not in col_lower) and ('male' not in col_lower): continue
        elif gender == 'Female':
            if ('females' not in col_lower) and ('female' not in col_lower): continue
        else:
            if 'persons' not in col_lower and 'person' not in col_lower and 'total' not in col_lower: continue

        if 'household' in col_lower or 'hhi' in col_lower or '| hhi' in col_lower:
            hhi_cols.append(col)
        elif 'non' in col_lower or 'non hhi' in col_lower or 'non-hhi' in col_lower:
            non_hhi_cols.append(col)
        else:
            non_hhi_cols.append(col)
            
    if not hhi_cols and not non_hhi_cols:
        for col in all_cols:
            if any(x in col for x in ['Area Name', 'Religon', 'Age group', 'Level', 'Total/Rural/Urban']): continue
            if gender == 'Male' and ('Males' in col or 'Male' in col): hhi_cols.append(col)
            elif gender == 'Female' and ('Females' in col or 'Female' in col): hhi_cols.append(col)
            elif gender != 'Male' and gender != 'Female' and 'Persons' in col: hhi_cols.append(col)

    hhi_sum = 0
    non_hhi_sum = 0
    
    for col in hhi_cols:
        try: hhi_sum += pd.to_numeric(filtered_data[col], errors='coerce').sum()
        except: pass
    for col in non_hhi_cols:
        try: non_hhi_sum += pd.to_numeric(filtered_data[col], errors='coerce').sum()
        except: pass
        
    hhi_details = {}
    non_hhi_details = {}
    
    for col in hhi_cols:
        parts = col.split(' | ')
        if len(parts) >= 2:
            if 'Males' in parts[-1] or 'Females' in parts[-1] or 'Persons' in parts[-1]: subcategory = ' | '.join(parts[1:-1])
            else: subcategory = ' | '.join(parts[1:])
            subcategory = subcategory.strip()
            if subcategory:
                if subcategory not in hhi_details: hhi_details[subcategory] = 0
                try: hhi_details[subcategory] += pd.to_numeric(filtered_data[col], errors='coerce').sum()
                except: pass
    
    for col in non_hhi_cols:
        parts = col.split(' | ')
        if len(parts) >= 2:
            if 'Males' in parts[-1] or 'Females' in parts[-1] or 'Persons' in parts[-1]: subcategory = ' | '.join(parts[1:-1])
            else: subcategory = ' | '.join(parts[1:])
            subcategory = subcategory.strip()
            if subcategory:
                if subcategory not in non_hhi_details: non_hhi_details[subcategory] = 0
                try: non_hhi_details[subcategory] += pd.to_numeric(filtered_data[col], errors='coerce').sum()
                except: pass

    return {
        'HHI_Total': int(hhi_sum),
        'Non_HHI_Total': int(non_hhi_sum),
        'HHI_Details': hhi_details,
        'Non_HHI_Details': non_hhi_details
    }

def get_occupation_data_filtered(state_name, gender=None, area_type=None):
    if occupation_df is None: return None
    occ_df_copy = occupation_df.copy()
    occ_df_copy['Area Name | Area Name'] = occ_df_copy['Area Name | Area Name'].astype(str).str.strip().str.upper()
    state_name_upper = str(state_name).strip().upper()
    
    if state_name_upper in occ_df_copy['Area Name | Area Name'].values:
        filtered_data = occ_df_copy[occ_df_copy['Area Name | Area Name'] == state_name_upper]
    else:
        filtered_data = occ_df_copy[occ_df_copy['Area Name | Area Name'] == 'INDIA']
    
    if area_type and area_type != 'All':
        filtered_data = filtered_data[filtered_data['Total/Rural/Urban | Total/Rural/Urban'] == area_type]
    
    return filtered_data
def bucket_occupation_categories(nco_name):
    if pd.isna(nco_name): return "Other"
    nco_name = str(nco_name).upper()
    if any(x in nco_name for x in ["LEGISLATORS", "SENIOR OFFICIALS", "MANAGERS"]): return "Management & Leadership"
    if any(x in nco_name for x in ["PROFESSIONALS", "ENGINEERING SCIENCE", "LIFE SCIENCE"]): return "Professional Services"
    if any(x in nco_name for x in ["TECHNICIANS", "ASSOCIATE PROFESSIONALS"]): return "Technical & Support"
    if any(x in nco_name for x in ["CLERKS", "OFFICE CLERKS", "CUSTOMER SERVICES CLERKS"]): return "Administrative & Clerical"
    if any(x in nco_name for x in ["SERVICE WORKERS", "SHOP & MARKET SALES", "PERSONAL AND PROTECTIVE"]): return "Sales & Service"
    if any(x in nco_name for x in ["SKILLED AGRICULTURAL", "FISHERY"]): return "Agriculture & Fishery"
    if any(x in nco_name for x in ["CRAFT AND RELATED TRADES", "METAL, MACHINERY", "PRECISION"]): return "Skilled Trades"
    if any(x in nco_name for x in ["PLANT AND MACHINE OPERATORS", "ASSEMBLERS", "DRIVERS"]): return "Machine Operators"
    if any(x in nco_name for x in ["ELEMENTARY OCCUPATIONS", "LABOURERS"]): return "Elementary Labor"
    if any(x in nco_name for x in ["WORKERS NOT CLASSIFIED"]): return "Unclassified"
    return "Other"

def regularize_nco_name(nco_name):
    if pd.isna(nco_name): return "Unknown"
    nco_name = str(nco_name).strip()
    # Simplified replacement for brevity
    replacements = {
        "LEGISLATORS, SENIOR OFFICIALS AND MANAGERS": "Legislators & Senior Officials",
        "Physical, Mathematical and Engineering Science Professionals": "Engineering & Science Professionals",
        "Life Science and Health Professionals": "Health & Life Science Professionals",
        "Office Clerks": "Office Clerks",
        "Market Oriented Skilled Agricultural and Fishery Workers": "Commercial Agriculture & Fishery",
        "Subsistence Agricultural and Fishery Workers": "Subsistence Agriculture & Fishery",
        "Machine Operators and Assemblers": "Machine Operators & Assemblers",
        "Sales and Services Elementary Occupations": "Sales & Service Elementary"
    }
    return replacements.get(nco_name, nco_name)

def create_occupation_visualization(filtered_data, gender, worker_type):
    if filtered_data is None or filtered_data.empty: return None, None, None
    
    if worker_type == 'Employer':
        count_col = 'Employer | Males' if gender == 'Male' else ('Employer | Females' if gender == 'Female' else 'Employer | Persons')
    elif worker_type == 'Employee':
        count_col = 'Employee | Males' if gender == 'Male' else ('Employee | Females' if gender == 'Female' else 'Employee | Persons')
    elif worker_type == 'Single worker':
        count_col = 'Single worker | Males' if gender == 'Male' else ('Single worker | Females' if gender == 'Female' else 'Single worker | Persons')
    elif worker_type == 'Family worker':
        count_col = 'Family worker | Males' if gender == 'Male' else ('Family worker | Females' if gender == 'Female' else 'Family worker | Persons')
    else:
        count_col = 'Total/Rural/Urban | Males' if gender == 'Male' else ('Total/Rural/Urban | Females' if gender == 'Female' else 'Total/Rural/Urban | Persons')

    if count_col not in filtered_data.columns: return None, None, None
    
    filtered_data = filtered_data.copy()
    filtered_data['Occupation Category'] = filtered_data['NCO name | NCO name'].apply(bucket_occupation_categories)
    filtered_data['Regularized NCO'] = filtered_data['NCO name | NCO name'].apply(regularize_nco_name)
    
    bucketed_data = filtered_data.groupby('Occupation Category')[count_col].sum().reset_index()
    bucketed_data = bucketed_data.sort_values(count_col, ascending=False)
    
    bucket_options = sorted(filtered_data['Occupation Category'].unique())
    return bucketed_data, filtered_data[['Regularized NCO', 'Occupation Category', count_col]], count_col


import requests
import re
from bs4 import BeautifulSoup

def clean_company_name_for_search(company_name: str) -> str:
    """
    Clean company name by removing branch/location info to get parent company.
    e.g. 'Bank of Baroda Andheri(West) Branch' -> 'Bank of Baroda'
    e.g. 'Bank of Maharashtra - Mumbai-Andheri, Seepz' -> 'Bank of Maharashtra'
    """
    name = company_name.strip()
    # Remove branch/location patterns (order matters - try more specific first)
    patterns = [
        r'\s+[A-Za-z]+\s*\([^)]+\)\s*Branch$',  # "Andheri(West) Branch"
        r'\s+Branch$',                            # "Branch"
        r'\s*\([^)]+\)\s*$',                      # "(anything)"
        r'\s+-\s+.+$',                            # " - anything" (dash separator)
        r',\s+.+$',                               # ", anything" (comma separator)
        r'\s+ATM$',
        r'\s+Office$',
    ]
    for pattern in patterns:
        name = re.sub(pattern, '', name, flags=re.IGNORECASE)
    # Also strip common suffixes that may remain
    suffixes = [' Ltd.', ' Ltd', ' Limited', ' Pvt. Ltd.', ' Pvt Ltd', ' (India)', ' India']
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)].strip()
    return name.strip()

def search_linkedin_url(person_name: str, company_name: str = '') -> str:
    """
    Search for a person's LinkedIn URL using web search engines.
    Uses Bing and DuckDuckGo HTML (no API timeouts).
    """
    if not person_name:
        return ''
    
    # Use multi-engine search (Bing + DuckDuckGo HTML)
    linkedin_url = search_linkedin_via_web(person_name, company_name)
    return linkedin_url

def get_web_context(company_name: str):
    """
    Gathers context from the web using Google Custom Search API.
    Falls back to Bing if Google not configured.
    """
    context_text = ""
    collected_snippets = []
    
    try:
        # Search queries for leadership info
        search_queries = [
            f"{company_name} leadership team CEO",
            f"{company_name} managing director executives",
        ]
        
        # Use Bing HTML search for web context
        import urllib.parse
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        
        for query in search_queries:
            try:
                encoded_query = urllib.parse.quote(query)
                url = f"https://www.bing.com/search?q={encoded_query}"
                response = requests.get(url, headers=headers, timeout=6)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    for result in soup.select('.b_algo')[:5]:
                        title_elem = result.select_one('h2')
                        snippet_elem = result.select_one('.b_caption p')
                        if title_elem and snippet_elem:
                            title = title_elem.get_text(strip=True)
                            snippet = snippet_elem.get_text(strip=True)
                            collected_snippets.append(f"Source: {title}\nInfo: {snippet}\n")
            except Exception as e:
                print(f"Bing search error for '{query}': {e}")
                continue
        
        if collected_snippets:
            context_text = "\n--- Search Results ---\n" + "\n".join(collected_snippets[:8])
            
        print(f"Web Search gathered {len(collected_snippets)} snippets.")
        return context_text[:3000]  # Limit tokens

    except Exception as e:
        print(f"Error getting web context: {e}")
        return ""
# ==========================================
# API ENDPOINTS
# ==========================================

@app.get("/api/search/{pincode}")
async def search_location(pincode: str):
    # Clean pincode
    pincode = pincode.strip()
    
    # Validate pincode format
    if not pincode.isdigit() or len(pincode) != 6:
        raise HTTPException(status_code=400, detail="Invalid Pincode format")
    
    
    # 1. Get Location
    geo_data = None
    if pincode_df is not None:
        result = pincode_df[pincode_df['pincode'].astype(str).str.strip() == str(pincode)]
        if not result.empty:
            row = result.iloc[0]
            geo_data = {
                "lat": safe_float(row.get('latitude', 0)), 
                "lng": safe_float(row.get('longitude', 0)),
                "district": str(row.get('district', '')).strip(), 
                "state": str(row.get('statename', '')).strip(),
                "address": f"{row.get('officename', '')}, {row.get('district', '')}, {row.get('statename', '')}"
            }
    
    if not geo_data:
        raise HTTPException(status_code=404, detail=f"Pincode {pincode} not found in database")

    # 2. Get Demographics
    demo_data = {}
    if pca_df is not None:
        row, _ = get_demographics_data(geo_data['district'], geo_data['state'])
        if row is not None:
            total_p = safe_int(row.get('TOT_P', 0))
            demo_data = {
                "total_pop": total_p,
                "households": safe_int(row.get('No_HH', 0)),
                "literacy": round((safe_int(row.get('P_LIT', 0)) / max(total_p, 1)) * 100, 1),
                "work_rate": round((safe_int(row.get('TOT_WORK_P', 0)) / max(total_p, 1)) * 100, 1),
                "male": safe_int(row.get('TOT_M', 0)),
                "female": safe_int(row.get('TOT_F', 0))
            }
    
    return {"location": geo_data, "demographics": demo_data}

@app.get("/api/places")
async def get_nearby_places(lat: float, lng: float, keyword: str):
    """Get nearby places using Google Places API"""
    print(f"Places search - Lat: {lat}, Lng: {lng}, Keyword: {keyword}")

    google_error = None

    if GOOGLE_PLACES_API_KEY:
        try:
            url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            params = {
                "location": f"{lat},{lng}",
                "radius": 10000,  # 10km radius
                "keyword": keyword,
                "key": GOOGLE_PLACES_API_KEY
            }

            print(f"Calling Google Places API with params: {params}")

            all_results = []
            page_count = 0
            max_pages = 3  # Google allows up to 3 pages (60 results)

            while page_count < max_pages:
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()

                status = data.get('status')
                print(f"Google API response status: {status}, page {page_count + 1}")

                if status not in ['OK', 'ZERO_RESULTS']:
                    google_error = data.get('error_message', status)
                    print(f"Google API error: {google_error}")
                    break

                all_results.extend(data.get('results', []))
                page_count += 1

                next_page_token = data.get('next_page_token')
                if not next_page_token:
                    break

                # Google requires a short delay before using next_page_token
                await asyncio.sleep(2)
                params = {
                    "pagetoken": next_page_token,
                    "key": GOOGLE_PLACES_API_KEY
                }

            if all_results:
                print(f"Total places fetched from Google: {len(all_results)}")

                results = []
                for place in all_results:
                    place_lat = place['geometry']['location']['lat']
                    place_lng = place['geometry']['location']['lng']
                    distance = calculate_distance_km(lat, lng, place_lat, place_lng)

                    rating = place.get('rating')
                    if rating is not None:
                        rating = float(rating)
                    else:
                        rating = 'N/A'

                    result_obj = {
                        "name": str(place.get('name', 'Unknown')),
                        "address": str(place.get('vicinity', 'Address not available')),
                        "dist": float(round(distance, 2)),
                        "rating": rating,
                        "place_id": str(place.get('place_id', '')),
                        "types": place.get('types', []),
                        "lat": float(place_lat),
                        "lng": float(place_lng)
                    }
                    results.append(result_obj)

                results.sort(key=lambda x: x['dist'])
                print(f"Returning {len(results)} places from Google")
                return results

        except requests.exceptions.Timeout:
            google_error = "Google Places API timeout"
            print(google_error)
        except requests.exceptions.RequestException as e:
            google_error = f"Google Places request error: {str(e)}"
            print(google_error)
        except Exception as e:
            google_error = f"Unexpected Google Places error: {str(e)}"
            print(google_error)
    else:
        google_error = "Google Places API key missing"
        print(google_error)

    print("Falling back to OSM Overpass for places search")
    osm_results = search_places_via_osm(lat, lng, keyword)
    if osm_results:
        print(f"Returning {len(osm_results)} places from OSM fallback")
        return osm_results

    if google_error:
        print(f"Places search failed. Last Google error: {google_error}")

    return []

# --- NEW: Chart Data Endpoints ---

@app.get("/api/charts/industrial")
async def get_industrial_charts(
    state: str,
    religion: str = "All",
    age_group: str = "All",
    gender: str = "All",
    tru: str = "All"
):
    """Returns data for HHI vs Non-HHI Donut and Subcategory Treemap"""
    if industrial_df is None: 
        raise HTTPException(status_code=404, detail="Industrial data not loaded")
    
    state_upper = str(state).upper()
    
    # Process Data
    filtered_data = get_filtered_industrial_data(state_upper, religion, age_group, gender, None, tru)
    
    if filtered_data is None or filtered_data.empty:
        return {"donut": None, "treemap": None}

    breakdown = create_industrial_breakdown(filtered_data, gender)
    if not breakdown: 
        return {"donut": None, "treemap": None}

    # Use safe_int for conversions
    hhi_total = safe_int(breakdown['HHI_Total'])
    non_hhi_total = safe_int(breakdown['Non_HHI_Total'])
    
    # Prepare Donut Data
    total = hhi_total + non_hhi_total
    hhi_pct = safe_float(round((hhi_total / total * 100), 1) if total > 0 else 0)
    
    donut_data = {
        "labels": ["HHI (Household Industry)", "Non-HHI (Formal Industry)"],
        "values": [hhi_total, non_hhi_total],
        "metrics": {
            "hhi_pct": hhi_pct
        }
    }

    # Prepare Treemap Data
    all_subcategories = {}
    for subcat, count in breakdown['HHI_Details'].items():
        if subcat.strip(): 
            all_subcategories[f"HHI: {subcat}"] = safe_int(count)
    for subcat, count in breakdown['Non_HHI_Details'].items():
        if subcat.strip(): 
            all_subcategories[f"Non-HHI: {subcat}"] = safe_int(count)
    
    sorted_subcats = sorted(all_subcategories.items(), key=lambda x: x[1], reverse=True)[:10]
    treemap_data = {
        "labels": [x[0] for x in sorted_subcats],
        "values": [safe_int(x[1]) for x in sorted_subcats]
    }

    return {"donut": donut_data, "treemap": treemap_data}

@app.get("/api/charts/occupation")
async def get_occupation_charts(
    state: str,
    area_type: str = "All",
    gender: str = "All",
    worker_type: str = "All",
    selected_category: str = None
):
    """Returns data for Occupation Distribution Bar Chart and Breakdown"""
    if occupation_df is None: 
        raise HTTPException(status_code=404, detail="Occupation data not loaded")

    state_upper = str(state).upper()
    filtered_data = get_occupation_data_filtered(state_upper, gender, area_type)
    
    if filtered_data is None or filtered_data.empty:
        return {"distribution": None, "breakdown": None, "categories": []}

    bucketed_data, detailed_data, count_col = create_occupation_visualization(filtered_data, gender, worker_type)
    
    if bucketed_data is None or bucketed_data.empty:
        return {"distribution": None, "breakdown": None, "categories": []}

    # Distribution data (bucketed categories)
    dist_data = {
        "y": bucketed_data['Occupation Category'].tolist(),
        "x": [safe_int(x) for x in bucketed_data[count_col].tolist()]
    }

    # Get all unique categories for dropdown (sorted)
    all_categories = sorted(detailed_data['Occupation Category'].unique().tolist())
    
    # Determine which category to show in breakdown
    if selected_category and selected_category in all_categories:
        category_to_show = selected_category
    else:
        # Default to the top category from distribution
        category_to_show = dist_data['y'][0] if dist_data['y'] else all_categories[0] if all_categories else "Other"
    
    # Filter and aggregate breakdown data for selected category
    bucket_filtered = detailed_data[detailed_data['Occupation Category'] == category_to_show].copy()
    bucket_filtered = bucket_filtered.groupby('Regularized NCO')[count_col].sum().reset_index()
    bucket_filtered = bucket_filtered.sort_values(count_col, ascending=False)
    
    breakdown_data = {
        "y": bucket_filtered['Regularized NCO'].tolist(),
        "x": [safe_int(x) for x in bucket_filtered[count_col].tolist()],
        "selected_category": category_to_show
    }

    return {
        "distribution": dist_data, 
        "breakdown": breakdown_data,
        "categories": all_categories  # Return sorted list of categories for dropdown
    }
@app.get("/api/charts/education")
async def get_education_charts(state: str):
    """Returns data for Education Funnel"""
    if education_df is None: raise HTTPException(status_code=404, detail="Education data not loaded")

    state_upper = str(state).upper()
    funnel_df = get_education_funnel_data(state_upper)
    
    if funnel_df is None or funnel_df.empty:
        return None

    return {
        "y": funnel_df['Education Level'].tolist(),
        "x": funnel_df['Count'].tolist()
    }
# Add after existing imports
from typing import List
@app.get("/api/events")
async def get_events_get(district: str = "", state: str = ""):
    """GET version of events endpoint"""
    if not district or not state:
        return []
    return await get_events({"district": district, "state": state})

@app.post("/api/events")
async def get_events(request: dict):
    district = request.get('district', '')
    state = request.get('state', '')
    
    print(f"Events requested for: {district}, {state}")
    
    if not district or not state:
        return []
    
    if not AZURE_OPENAI_API_KEY or not AZURE_OPENAI_ENDPOINT:
        print("Azure credentials missing!")
        return [
            {"name": "Local Festival", "date": "Next Month", "address": f"{district}", "description": "Annual cultural celebration"},
            {"name": "Community Fair", "date": "Coming Soon", "address": f"{district}", "description": "Local trade fair"}
        ]
    
    try:
        client = AzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT
        )
        
        # Update the events prompt in @app.post("/api/events")
        prompt = f"""Provide a JSON array of 5-7 upcoming cultural events (festivals, concerts, fairs, parties) in {district} district, {state} state, India.

Only include events that take place in June 2026 or later (for example June 2026 through December 2026). Prefer events occurring within the next 3-6 months when possible.

Format:
[
    {{
        "name": "Event Name",
        "date": "Date range or specific date (e.g., 'June 15-17, 2026')",
        "address": "Specific venue location",
        "description": "Brief 1-2 sentence description",
        "website": "Official event website URL (if available, otherwise null)"
    }}
]

Focus on real events in June 2026 or later. Include website links when available.
Return ONLY the JSON array, no other text."""
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT_NAME,
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Always return valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        content = response.choices[0].message.content.strip()
        
        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "").strip()
        elif content.startswith("```"):
            content = content.replace("```", "").strip()
        
        events = json.loads(content)
        
        if not isinstance(events, list):
            return []
        
        print(f"Successfully fetched {len(events)} events")
        return events
    
    except Exception as e:
        print(f"Error fetching events: {str(e)}")
        return [
            {"name": "Local Festival", "date": "June 12-14, 2026", "address": f"{district}", "description": "Annual cultural celebration"},
            {"name": "Community Fair", "date": "July 10, 2026", "address": f"{district}", "description": "Local trade fair"}
        ]
@app.get("/api/charts/demographics/{pincode}")
async def get_demographics_charts(pincode: str):
    """Returns gender, age, social composition charts data"""
    if pincode_df is None or pca_df is None:
        raise HTTPException(status_code=404, detail="Data not loaded")
    
    # Get location
    result = pincode_df[pincode_df['pincode'].astype(str).str.strip() == str(pincode)]
    if result.empty:
        raise HTTPException(status_code=404, detail="Pincode not found")
    
    row = result.iloc[0]
    district = row.get('district')
    state = row.get('statename')
    
    # Get demographics using existing function
    demo_row, _ = get_demographics_data(district, state)
    
    if demo_row is None:
        raise HTTPException(status_code=404, detail="Demographics not found")
    
    # Use safe_int for all conversions
    total_pop = safe_int(demo_row.get('TOT_P', 0))
    male_pop = safe_int(demo_row.get('TOT_M', 0))
    female_pop = safe_int(demo_row.get('TOT_F', 0))
    child_0_6 = safe_int(demo_row.get('P_06', 0))
    sc_pop = safe_int(demo_row.get('P_SC', 0))
    st_pop = safe_int(demo_row.get('P_ST', 0))
    literate = safe_int(demo_row.get('P_LIT', 0))
    illiterate = safe_int(demo_row.get('P_ILL', 0))
    working = safe_int(demo_row.get('TOT_WORK_P', 0))
    non_working = safe_int(demo_row.get('NON_WORK_P', 0))
    male_workers = safe_int(demo_row.get('TOT_WORK_M', 0))
    female_workers = safe_int(demo_row.get('TOT_WORK_F', 0))
    
    # Calculate age groups
    youth = safe_int((total_pop - child_0_6) * 0.33)
    adult = safe_int((total_pop - child_0_6) * 0.42)
    senior = safe_int(total_pop - child_0_6 - youth - adult)
    
    other_pop = safe_int(total_pop - sc_pop - st_pop)
    return {
        "gender": {
            "labels": ["Male", "Female"],
            "values": [male_pop, female_pop]
        },
        "age": {
            "labels": ["0-6 years", "7-25 years", "26-50 years", "50+ years"],
            "values": [child_0_6, youth, adult, senior]
        },
        "social": {
            "labels": ["General", "SC", "ST"],
            "values": [other_pop, sc_pop, st_pop]
        },
        "literacy": {
            "labels": ["Literate", "Illiterate"],
            "values": [literate, illiterate]
        },
        "work": {
            "labels": ["Working", "Non-Working"],
            "values": [working, non_working]
        },
        "workers_gender": {
            "labels": ["Male Workers", "Female Workers"],
            "values": [male_workers, female_workers]
        }
        }

# Replace the @app.post("/api/leadership") function
@app.post("/api/leadership")
async def search_leadership(request: dict):
    raw_company_name = request.get('company_name', '').strip()
    if not raw_company_name:
        return []

    # Clean name to get parent company
    company_name = clean_company_name_for_search(raw_company_name)
    print(f"--- Searching Leadership for: {company_name} (raw: {raw_company_name}) ---")
    leadership_profiles = []

    # ============================================================
    # STEP 1: Basic Web Search (Gather Context)
    # ============================================================
    web_context = get_web_context(company_name)

    # ============================================================
    # STEP 2: AI Extraction (Using Web Context)
    # ============================================================
    # We try AI regardless of web context, but if we have context, we give it to AI.
    try:
        if AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT:
            client = AzureOpenAI(
                api_key=AZURE_OPENAI_API_KEY,
                api_version=AZURE_OPENAI_API_VERSION,
                azure_endpoint=AZURE_OPENAI_ENDPOINT
            )
            
            system_prompt = """You are an expert business intelligence assistant with knowledge of corporate leadership.
You have accurate information about executives at major companies from your training data.
DO NOT provide LinkedIn URLs - they will be looked up separately."""
            
            user_prompt = f"""Find the current leadership team for '{company_name}'.

I need:
1. Names of key executives (CEO, MD, CFO, Managing Directors, etc.)
2. Their exact current titles
"""
            
            if web_context:
                user_prompt += f"""

WEB CONTEXT:
{web_context}
"""

            user_prompt += """

Return a JSON array. For each person:
- "name": Full name (MUST be accurate)
- "title": Current title at this company
- "linkedin": Always set to null (will be searched separately)

Example:
[
  {"name": "Satya Nadella", "title": "CEO", "linkedin": null},
  {"name": "Amy Hood", "title": "CFO", "linkedin": null}
]

RULES:
1. Return 3-5 key executives for well-known companies
2. Names and titles must be accurate from your knowledge
3. Always set linkedin to null - DO NOT generate LinkedIn URLs
"""

            response = client.chat.completions.create(
                model=AZURE_OPENAI_DEPLOYMENT_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content.strip()
            # print(f"Raw AI Output: {content}") # Debugging
            
            # Cleanup JSON markdown
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            try:
                leadership_profiles = json.loads(content)
                if isinstance(leadership_profiles, list):
                    # Filter valid entries
                    leadership_profiles = [p for p in leadership_profiles if isinstance(p, dict) and p.get('name')]
                else:
                    leadership_profiles = []
                
                if leadership_profiles:
                    print(f"Step 2 (AI) found {len(leadership_profiles)} profiles.")
                    
                    # STEP 2.5: Search for LinkedIn URLs for each person
                    print("Step 2.5: Searching LinkedIn URLs...")
                    for profile in leadership_profiles:
                        name = profile.get('name', '')
                        if name:
                            linkedin_url = search_linkedin_url(name, company_name)
                            profile['linkedin'] = linkedin_url if linkedin_url else None
                            print(f"  {name} -> {linkedin_url or 'not found'}")
                        else:
                            profile['linkedin'] = None
                    
            except json.JSONDecodeError:
                print("AI returned invalid JSON.")
                leadership_profiles = []

    except Exception as e:
        print(f"AI Error: {e}")

    # ============================================================
    # STEP 3: Fallback to ContactOut
    # ============================================================
    if not leadership_profiles and CONTACTOUT_API_KEY:
        print("Step 2 empty. Trying ContactOut...")
        try:
            leadership_profiles = await search_contactout_company(company_name)
        except Exception as e:
            print(f"ContactOut Error: {e}")

    print(f"--- Final Result: {len(leadership_profiles)} ---")
    return leadership_profiles

async def search_contactout_company(company_name: str):
    """Search ContactOut with company name cleaning (Must be async)"""
    if not CONTACTOUT_API_KEY:
        return []
    
    # Clean name logic...
    suffixes_to_remove = [" Ltd.", " Ltd", " Limited", " Pvt. Ltd.", " Pvt Ltd", " (India)"]
    clean_name = company_name
    for suffix in suffixes_to_remove:
        if clean_name.endswith(suffix):
            clean_name = clean_name[:-len(suffix)].strip()
    
    print(f"ContactOut searching for: '{clean_name}'")
    
    try:
        url = "https://api.contactout.com/v2/search"
        headers = {
            "Authorization": f"Bearer {CONTACTOUT_API_KEY}",
            "Content-Type": "application/json"
        }
        
        titles = ["CEO", "CFO", "CTO", "COO", "Managing Director", "Director", "VP"]
        all_profiles = []
        
        for title in titles:
            # Standard requests inside async function is fine for I/O bound tasks here
            response = requests.post(url, json={
                "company": clean_name,
                "title": title,
                "limit": 2
            }, headers=headers, timeout=10)
            
            if response.status_code == 200:
                for r in response.json().get('results', []):
                    if r.get('name'):
                        all_profiles.append({
                            "name": r.get('name'),
                            "title": r.get('title'),
                            "linkedin": r.get('linkedin_url', '')
                        })
            
            # Important: Async sleep to prevent rate limiting
            await asyncio.sleep(0.5)
            
        return list({v['name']:v for v in all_profiles}.values())[:10]

    except Exception as e:
        print(f"ContactOut Error: {e}")
        return []


def search_linkedin_via_web(name: str, company: str = '') -> str:
    """Search for LinkedIn profile URL using Google Custom Search API"""
    import re
    
    if not name:
        return ''
    
    def extract_linkedin_url(url_or_text):
        """Extract and clean LinkedIn profile URL"""
        pattern = r'https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9\-_%]+'
        if 'linkedin.com/in/' in url_or_text:
            matches = re.findall(pattern, url_or_text)
            for url in matches:
                url = url.split('?')[0].split('&')[0]
                if len(url) < 100:
                    return url
        return None
    
    # Build search query
    query_parts = [name]
    if company:
        query_parts.append(company)
    query_parts.append("LinkedIn")
    query = " ".join(query_parts)
    
    # Use Bing HTML search for LinkedIn profiles
    try:
        import urllib.parse
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        bing_query = urllib.parse.quote(f'site:linkedin.com/in {query}')
        bing_url = f"https://www.bing.com/search?q={bing_query}"
        response = requests.get(bing_url, headers=headers, timeout=8)
        
        if response.status_code == 200:
            linkedin_url = extract_linkedin_url(response.text)
            if linkedin_url:
                print(f"  Bing found: {linkedin_url}")
                return linkedin_url
    except Exception as e:
        print(f"  Bing search failed: {e}")
    
    return ''


def search_linkedin_via_google(name: str, company: str = '') -> str:
    """Wrapper that calls the Google search"""
    return search_linkedin_via_web(name, company)

# Add new model for credit tracking
class CreditUsage(BaseModel):
    email_credits: int = 10
    phone_credits: int = 2

# Global credit tracker (in production, use database)
user_credits = {
    "email": 10,
    "phone": 2
}

@app.get("/api/credits")
async def get_credits():
    """Get remaining credits"""
    return {
        "email_credits": user_credits["email"],
        "phone_credits": user_credits["phone"]
    }

@app.post("/api/contactout")
async def get_contact_details(request: dict):
    """Get contact details using ContactOut API (consumes credits)"""
    linkedin_url = request.get('linkedin_url', '')
    name = request.get('name', '')
    title = request.get('title', '')
    company = request.get('company', '')
    fetch_email = request.get('fetch_email', True)
    fetch_phone = request.get('fetch_phone', True)

    print(f"\n=== ContactOut Request ===")
    print(f"  linkedin_url: {linkedin_url}")
    print(f"  name: {name}")
    print(f"  title: {title}")
    print(f"  company: {company}")

    # If no linkedin_url provided, try to search Google for the profile using name/company
    if not linkedin_url:
        print("No LinkedIn URL provided, searching Google...")
        try:
            linkedin_url = search_linkedin_via_google(name, company)
            print(f"Resolved linkedin_url from Google search: {linkedin_url}")
        except Exception as e:
            print(f"Google search error: {e}")

    if not linkedin_url:
        print("ERROR: No LinkedIn URL found/resolved")
        raise HTTPException(status_code=400, detail="LinkedIn URL or person details required")
    
    # Check credits
    credits_needed = {
        "email": 1 if fetch_email else 0,
        "phone": 1 if fetch_phone else 0
    }
    
    if fetch_email and user_credits["email"] < 1:
        raise HTTPException(status_code=402, detail="Insufficient email credits")
    
    if fetch_phone and user_credits["phone"] < 1:
        raise HTTPException(status_code=402, detail="Insufficient phone credits")
    
    if not CONTACTOUT_API_KEY:
        raise HTTPException(status_code=500, detail="ContactOut API not configured")
    
    try:
        # ContactOut LinkedIn Profile API
        url = "https://api.contactout.com/v2/profiles/linkedin"
        
        headers = {
            "Authorization": f"Bearer {CONTACTOUT_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "linkedin_url": linkedin_url
        }
        
        print(f"Fetching contact for: {linkedin_url}")
        
        response = requests.post(url, json=data, headers=headers, timeout=15)
        
        if response.status_code == 200:
            result = response.json()
            
            contact_data = {
                "email": None,
                "phone": None,
                "credits_used": {}
            }
            
            # Get email if requested
            if fetch_email and result.get('email'):
                contact_data["email"] = result['email']
                user_credits["email"] -= 1
                contact_data["credits_used"]["email"] = 1
            
            # Get phone if requested
            if fetch_phone and result.get('phone'):
                contact_data["phone"] = result['phone']
                user_credits["phone"] -= 1
                contact_data["credits_used"]["phone"] = 1
            
            contact_data["remaining_credits"] = {
                "email": user_credits["email"],
                "phone": user_credits["phone"]
            }
            
            return contact_data
        
        elif response.status_code == 404:
            raise HTTPException(status_code=404, detail="Profile not found")
        else:
            print(f"ContactOut API error: {response.status_code} - {response.text}")
            raise HTTPException(status_code=500, detail="Failed to fetch contact details")
    
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="ContactOut API timeout")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching contact: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/resolve_linkedin")
async def resolve_linkedin(request: dict):
    """Resolve a person's LinkedIn URL using web search engines."""
    name = request.get('name', '').strip()
    title = request.get('title', '').strip()
    company = request.get('company', '').strip()

    if not (name or company):
        return {"linkedin": ""}

    # Use multi-engine search (Bing + DuckDuckGo HTML)
    linkedin_url = search_linkedin_via_web(name, company)
    
    # If not found, try with title
    if not linkedin_url and title:
        linkedin_url = search_linkedin_via_web(f"{name} {title}", company)
    
    return {"linkedin": linkedin_url or ""}

if __name__ == "__main__":
    print("Starting Server at http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)