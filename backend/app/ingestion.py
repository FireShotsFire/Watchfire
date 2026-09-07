import os
import xml.etree.ElementTree as ET

import requests
from supabase import create_client, Client


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise ValueError("Missing Supabase credentials in environment variables.")

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY,
)


UK_XML_URL = "https://sanctionslist.fcdo.gov.uk/docs/UK-Sanctions-List.xml"


def clean_text(element):
    if element is None:
        return None

    text = "".join(element.itertext()).strip()

    return text if text else None


def local_name(tag):
    """Remove XML namespace from a tag."""
    return tag.split("}")[-1]


def ingest_uk_sanctions():
    print("Downloading full GOV.UK XML sanctions list...")

    response = requests.get(
        UK_XML_URL,
        headers={"User-Agent": "Watchfire/1.0"},
        timeout=120,
    )

    response.raise_for_status()

    print(f"Downloaded {len(response.content):,} bytes.")

    print("Parsing UK XML data...")

    root = ET.fromstring(response.content)

    records = []

    # Find every element regardless of XML namespace.
    designation_elements = [
        element
        for element in root.iter()
        if local_name(element.tag).lower() == "designation"
    ]

    print(
        f"Found {len(designation_elements)} Designation elements."
    )

    for designation in designation_elements:

        unique_id = None
        full_name = None
        entity_type = None
        regime = None
        aliases = []

        for element in designation.iter():

            tag = local_name(element.tag).lower()
            text = clean_text(element)

            if not text:
                continue

            if tag == "uniqueid" and unique_id is None:
                unique_id = text

            elif tag == "fullname" and full_name is None:
                full_name = text

            elif tag == "individualentityship" and entity_type is None:
                entity_type = text

            elif tag == "regimename" and regime is None:
                regime = text

        # Collect alternative names.
        for element in designation.iter():
            tag = local_name(element.tag).lower()

            if tag == "alias":
                alias_name = None

                for child in element.iter():
                    if local_name(child.tag).lower() == "fullname":
                        alias_name = clean_text(child)

                if alias_name and alias_name != full_name:
                    aliases.append(alias_name)

        if not unique_id or not full_name:
            continue

        records.append(
            {
                "official_id": unique_id,
                "jurisdiction": "UK",
                "entity_type": (
                    entity_type.upper()
                    if entity_type
                    else "INDIVIDUAL"
                ),
                "primary_name": full_name,
                "aliases": aliases,
                "dates_of_birth": [],
                "nationalities": [],
                "addresses": [],
                "passports_tax_ids": [],
                "regime_reasons": (
                    regime
                    if regime
                    else "UK Sanctions List"
                ),
                "official_source_url": (
                    "https://www.gov.uk/government/"
                    "publications/the-uk-sanctions-list"
                ),
                "raw_payload": {
                    "unique_id": unique_id,
                    "regime": regime,
                },
            }
        )

    print(
        f"Parsed {len(records)} UK sanction entities."
    )

    if not records:
        raise RuntimeError(
            "Parser found zero UK records. "
            "Stopping before attempting Supabase upload."
        )

    # Remove duplicate IDs.
    unique_records = {}

    for record in records:
        key = (
            record["jurisdiction"],
            record["official_id"],
        )

        unique_records[key] = record

    records = list(unique_records.values())

    print(
        f"Uploading {len(records)} unique UK records..."
    )

    batch_size = 500

    for i in range(0, len(records), batch_size):

        batch = records[i : i + batch_size]

        print(
            f"Uploading records "
            f"{i + 1}-{min(i + batch_size, len(records))}..."
        )

        supabase.table("sanctions_entities").upsert(
            batch,
            on_conflict="jurisdiction,official_id",
        ).execute()

    print(
        f"Successfully uploaded {len(records)} UK records."
    )


if __name__ == "__main__":
    ingest_uk_sanctions()
