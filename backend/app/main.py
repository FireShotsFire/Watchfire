import os

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from rapidfuzz import fuzz
from dotenv import load_dotenv


load_dotenv()


app = FastAPI(
    title="Watchfire Sanctions Screening API",
    version="1.0.0",
)


# ---------------------------------------------------------
# CORS
# ---------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# SUPABASE
# ---------------------------------------------------------

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv(
    "SUPABASE_SERVICE_ROLE_KEY"
)

if not SUPABASE_URL:
    raise ValueError(
        "Missing SUPABASE_URL environment variable."
    )

if not SUPABASE_SERVICE_ROLE_KEY:
    raise ValueError(
        "Missing SUPABASE_SERVICE_ROLE_KEY environment variable."
    )


supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY,
)


# ---------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------

@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "Watchfire Sanctions Screening API",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
    }


# ---------------------------------------------------------
# DATABASE TEST
# ---------------------------------------------------------

@app.get("/api/v1/test-database")
def test_database():
    """
    Simple diagnostic endpoint.

    This confirms that the Render backend can actually
    read records from Supabase.
    """

    response = (
        supabase
        .table("sanctions_entities")
        .select(
            "official_id,jurisdiction,primary_name"
        )
        .limit(5)
        .execute()
    )

    return {
        "database_connected": True,
        "records_returned": len(response.data),
        "records": response.data,
    }


# ---------------------------------------------------------
# SCREENING
# ---------------------------------------------------------

@app.get("/api/v1/screen")
def screen_entity(
    name: str = Query(
        ...,
        description="Entity or individual name to search",
    ),
    threshold: float = Query(
        65.0,
        description="Minimum match percentage threshold",
    ),
):
    """
    Screen a name against sanctions entities.

    Uses RapidFuzz token-based matching against:
    - primary_name
    - aliases
    """

    name = name.strip()

    if not name:
        return {
            "query": name,
            "total_hits": 0,
            "results": [],
        }

    if threshold < 0:
        threshold = 0

    if threshold > 100:
        threshold = 100

    # -----------------------------------------------------
    # Retrieve records
    # -----------------------------------------------------

    response = (
        supabase
        .table("sanctions_entities")
        .select("*")
        .execute()
    )

    candidates = response.data

    results = []

    # -----------------------------------------------------
    # Fuzzy matching
    # -----------------------------------------------------

    search_name = name.lower().strip()

    for item in candidates:

        primary_name = (
            item.get("primary_name") or ""
        ).strip()

        if not primary_name:
            continue

        # Primary name score
        primary_score = fuzz.token_sort_ratio(
            search_name,
            primary_name.lower(),
        )

        # Alias scores
        aliases = item.get("aliases") or []

        alias_scores = []

        for alias in aliases:

            if not alias:
                continue

            score = fuzz.token_sort_ratio(
                search_name,
                str(alias).lower(),
            )

            alias_scores.append(
                (score, str(alias))
            )

        # Find best score
        best_score = primary_score
        matched_alias = None

        if alias_scores:

            best_alias_score, best_alias = max(
                alias_scores,
                key=lambda x: x[0],
            )

            if best_alias_score > best_score:
                best_score = best_alias_score
                matched_alias = best_alias

        # Apply threshold
        if best_score >= threshold:

            results.append(
                {
                    "match_score": round(
                        best_score,
                        2,
                    ),
                    "official_id": item.get(
                        "official_id"
                    ),
                    "jurisdiction": item.get(
                        "jurisdiction"
                    ),
                    "entity_type": item.get(
                        "entity_type"
                    ),
                    "primary_name": primary_name,
                    "matched_alias": matched_alias,
                    "dates_of_birth": item.get(
                        "dates_of_birth",
                        [],
                    ),
                    "nationalities": item.get(
                        "nationalities",
                        [],
                    ),
                    "addresses": item.get(
                        "addresses",
                        [],
                    ),
                    "regime_reasons": item.get(
                        "regime_reasons"
                    ),
                    "official_source_url": item.get(
                        "official_source_url"
                    ),
                }
            )

    # Highest matches first
    results.sort(
        key=lambda x: x["match_score"],
        reverse=True,
    )

    return {
        "query": name,
        "threshold": threshold,
        "candidates_checked": len(candidates),
        "total_hits": len(results),
        "results": results,
    }
