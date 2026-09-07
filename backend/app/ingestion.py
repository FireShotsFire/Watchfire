import os
import xml.etree.ElementTree as ET
import requests
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise ValueError("Missing Supabase credentials in environment variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def ingest_uk_sanctions():
    print("Downloading full GOV.UK XML sanctions list...")
    url = "https://sanctionslist.fcdo.gov.uk/docs/UK-Sanctions-List.xml"
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    
    print("Parsing UK XML data...")
    root = ET.fromstring(response.content)
    
    records = []
    for des in root.findall(".//Designation"):
        uid_elem = des.find(".//UniqueID")
        name_elem = des.find(".//Name/Full Name")
        type_elem = des.find(".//IndividualEntityShip")
        regime_elem = des.find(".//RegimeName")
        
        if uid_elem is not None and name_elem is not None and uid_elem.text and name_elem.text:
            uid = uid_elem.text.strip()
            name = name_elem.text.strip()
            entity_type = type_elem.text.strip().upper() if type_elem is not None and type_elem.text else "INDIVIDUAL"
            regime = regime_elem.text.strip() if regime_elem is not None and regime_elem.text else "UK Sanctions List"
            
            aliases = [a.text.strip() for a in des.findall(".//Alias/Full Name") if a.text]
            
            records.append({
                "official_id": uid,
                "jurisdiction": "UK",
                "entity_type": entity_type,
                "primary_name": name,
                "aliases": aliases,
                "dates_of_birth": [],
                "nationalities": [],
                "addresses": [],
                "passports_tax_ids": [],
                "regime_reasons": regime,
                "official_source_url": "https://www.gov.uk/government/publications/the-uk-sanctions-list",
                "raw_payload": {"unique_id": uid, "regime": regime}
            })
            
    print(f"Parsed {len(records)} total unique UK sanction entities.")
    
    # Upsert in batches of 500
    batch_size = 500
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        supabase.table("sanctions_entities").upsert(
            batch, on_conflict="jurisdiction,official_id"
        ).execute()
        print(f"Uploaded {min(i + batch_size, len(records))} / {len(records)} records...")

if __name__ == "__main__":
    ingest_uk_sanctions()
