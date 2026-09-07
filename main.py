import os
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from rapidfuzz import fuzz
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Watchfire Sanctions Screening API", version="1.0.0")

# Enable CORS for Cloudflare Pages frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_ANON_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.get("/api/v1/screen")
def screen_entity(
    name: str = Query(..., description="Entity or individual name to search"),
    threshold: float = Query(65.0, description="Minimum match percentage threshold")
):
    first_token = name.split()[0] if name.split() else name
    query_str = f"%{first_token}%"
    
    response = supabase.table("sanctions_entities") \
        .select("*") \
        .ilike("primary_name", query_str) \
        .limit(150) \
        .execute()
    
    candidates = response.data
    results = []

    for item in candidates:
        primary_score = fuzz.token_sort_ratio(name.lower(), item["primary_name"].lower())
        
        alias_scores = [
            fuzz.token_sort_ratio(name.lower(), alias.lower())
            for alias in item.get("aliases", [])
        ]
        
        max_score = max([primary_score] + alias_scores) if alias_scores else primary_score

        if max_score >= threshold:
            results.append({
                "match_score": round(max_score, 2),
                "official_id": item["official_id"],
                "jurisdiction": item["jurisdiction"],
                "entity_type": item["entity_type"],
                "primary_name": item["primary_name"],
                "matched_alias": None if max_score == primary_score else "Matched on Alias",
                "dates_of_birth": item["dates_of_birth"],
                "regime_reasons": item["regime_reasons"],
                "official_source_url": item["official_source_url"],
            })

    results.sort(key=lambda x: x["match_score"], reverse=True)

    return {
        "query": name,
        "total_hits": len(results),
        "results": results
    }
