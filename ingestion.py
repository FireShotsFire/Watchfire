import os
import requests
import xml.etree.ElementTree as ET
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY environment variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

DATA_SOURCES = {
    "UK": "https://sanctionslist.fcdo.gov.uk/docs/UK-Sanctions-List.xml",
    "US": "https://sanctionslist.ofac.treas.gov/Home/SdnList/SDN.XML"
}

def fetch_and_parse_uk():
    print("Fetching UK Sanctions Data...")
    response = requests.get(DATA_SOURCES["UK"], timeout=60)
    root = ET.fromstring(response.content)
    
    records = []
    for designation in root.findall('.//Designation'):
        official_id = designation.findtext('UniqueID', default='').strip()
        primary_name = designation.findtext('Name/Full Name', default='').strip()
        entity_type = designation.findtext('IndividualEntityShip', default='UNKNOWN').strip().upper()
        
        if not primary_name or not official_id:
            continue

        aliases = [alias.findtext('Full Name').strip() for alias in designation.findall('.//Alias') if alias.findtext('Full Name')]
        dobs = [dob.findtext('DateOfBirth').strip() for dob in designation.findall('.//DOB') if dob.findtext('DateOfBirth')]
        reasons = designation.findtext('RegimeName', default='').strip()

        records.append({
            "official_id": official_id,
            "jurisdiction": "UK",
            "entity_type": entity_type,
            "primary_name": primary_name,
            "aliases": aliases,
            "dates_of_birth": dobs,
            "nationalities": [],
            "addresses": [],
            "passports_tax_ids": [],
            "regime_reasons": reasons,
            "official_source_url": "https://www.gov.uk/government/publications/the-uk-sanctions-list",
            "raw_payload": {"id": official_id, "name": primary_name}
        })
    print(f"Parsed {len(records)} UK records.")
    return records

def fetch_and_parse_us():
    print("Fetching US OFAC Data...")
    response = requests.get(DATA_SOURCES["US"], timeout=60)
    root = ET.fromstring(response.content)
    
    # Handle XML Namespace in OFAC SDN.xml
    ns = {'sdn': root.tag.split('}')[0].strip('{')} if '}' in root.tag else {}
    prefix = 'sdn:' if ns else ''

    records = []
    for entry in root.findall(f'.//{prefix}sdnEntry', ns):
        official_id = entry.findtext(f'{prefix}uid', default='', namespaces=ns).strip()
        first_name = entry.findtext(f'{prefix}firstName', default='', namespaces=ns).strip()
        last_name = entry.findtext(f'{prefix}lastName', default='', namespaces=ns).strip()
        
        primary_name = f"{first_name} {last_name}".strip() if first_name else last_name
        entity_type = entry.findtext(f'{prefix}sdnType', default='UNKNOWN', namespaces=ns).strip().upper()

        if not primary_name or not official_id:
            continue

        aliases = []
        for aka in entry.findall(f'.//{prefix}aka', ns):
            aka_first = aka.findtext(f'{prefix}firstName', default='', namespaces=ns).strip()
            aka_last = aka.findtext(f'{prefix}lastName', default='', namespaces=ns).strip()
            aka_full = f"{aka_first} {aka_last}".strip() if aka_first else aka_last
            if aka_full:
                aliases.append(aka_full)

        records.append({
            "official_id": official_id,
            "jurisdiction": "US",
            "entity_type": entity_type,
            "primary_name": primary_name,
            "aliases": aliases,
            "dates_of_birth": [],
            "nationalities": [],
            "addresses": [],
            "passports_tax_ids": [],
            "regime_reasons": "OFAC SDN List",
            "official_source_url": "https://sanctionslist.ofac.treas.gov/Home/SdnList",
            "raw_payload": {"uid": official_id, "name": primary_name}
        })
    print(f"Parsed {len(records)} US records.")
    return records

def batch_upsert(records):
    if not records:
        return
    print(f"Upserting {len(records)} records into Supabase...")
    batch_size = 500
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        supabase.table("sanctions_entities").upsert(
            batch, 
            on_conflict="jurisdiction,official_id"
        ).execute()
    print("Batch upsert complete.")

if __name__ == "__main__":
    uk_records = fetch_and_parse_uk()
    batch_upsert(uk_records)
    
    us_records = fetch_and_parse_us()
    batch_upsert(us_records)
