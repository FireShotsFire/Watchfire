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


def local_name(tag):
    """Remove an XML namespace from a tag."""
    return tag.split("}")[-1]


def clean_text(element):
    """Return all text contained in an XML element."""
    if element is None:
        return None

    text = " ".join(
        part.strip()
        for part in element.itertext()
        if part.strip()
    )

    return text if text else None


def find_first_text(element, possible_names):
    """
    Find the first descendant element whose local XML tag matches
    one of the supplied names.
    """
    possible_names = {
        name.lower()
        for name in possible_names
    }

    for child in element.iter():
        tag = local_name(child.tag).lower()

        if tag in possible_names:
            text = clean_text(child)

            if text:
                return text

    return None


def find_all_text(element, possible_names):
    """
    Find all descendant elements whose local XML tag matches
    one of the supplied names.
    """
    possible_names = {
        name.lower()
        for name in possible_names
    }

    results = []

    for child in element.iter():
        tag = local_name(child.tag).lower()

        if tag in possible_names:
            text = clean_text(child)

            if text:
                results.append(text)

    return results


def ingest_uk_sanctions():
    print("Downloading full GOV.UK XML sanctions list...")

    response = requests.get(
        UK_XML_URL,
        headers={
            "User-Agent": "Watchfire/1.0"
        },
        timeout=120,
    )

    response.raise_for_status()

    print(
        f"Downloaded {len(response.content):,} bytes."
    )

    print("Parsing UK XML data...")

    root = ET.fromstring(response.content)

    # Find Designation elements regardless of XML namespace.
    designation_elements = [
        element
        for element in root.iter()
        if local_name(element.tag).lower() == "designation"
    ]

    print(
        f"Found {len(designation_elements)} Designation elements."
    )

    # DEBUG: show the structure of the first record.
    if designation_elements:
        print("")
        print("=" * 80)
        print("DEBUG: First Designation structure")
        print("=" * 80)

        for element in designation_elements[0].iter():
            tag = local_name(element.tag)
            text = clean_text(element)

            print(
                f"TAG={tag!r} | TEXT={text!r}"
            )

        print("=" * 80)
        print("End debug output")
        print("=" * 80)
        print("")

    records = []

    for index, designation in enumerate(
        designation_elements,
        start=1,
    ):

        # Try several possible field names.
        unique_id = find_first_text(
            designation,
            [
                "UniqueID",
                "UniqueId",
                "UniqueIdentifier",
                "ID",
                "Id",
            ],
        )

        full_name = find_first_text(
            designation,
            [
                "FullName",
                "Full Name",
                "Name",
            ],
        )

        entity_type = find_first_text(
            designation,
            [
                "IndividualEntityShip",
                "EntityType",
                "Type",
            ],
        )

        regime = find_first_text(
            designation,
            [
                "RegimeName",
                "Regime",
            ],
        )

        # Find aliases.
        aliases = []

        for alias in designation.iter():

            if local_name(alias.tag).lower() != "alias":
                continue

            alias_name = find_first_text(
                alias,
                [
                    "FullName",
                    "Full Name",
                    "Name",
                ],
            )

            if (
                alias_name
                and alias_name != full_name
                and alias_name not in aliases
            ):
                aliases.append(alias_name)

        # If we don't have an ID or name, skip this record.
        if not unique_id or not full_name:

            # Print the first few skipped records to help debugging.
            if index <= 5:
                print(
                    f"WARNING: Could not extract ID/name "
                    f"from Designation #{index}"
                )

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

    print("")
    print(
        f"Parsed {len(records)} UK sanction entities."
    )

    if not records:
        raise RuntimeError(
            "Parser found zero UK records. "
            "See the DEBUG output above."
        )

    # Remove duplicate jurisdiction/official_id combinations.
    unique_records = {}

    for record in records:
        key = (
            record["jurisdiction"],
            record["official_id"],
        )

        unique_records[key] = record

    records = list(
        unique_records.values()
    )

    print(
        f"After deduplication: "
        f"{len(records)} unique UK records."
    )

    # Upload in batches.
    batch_size = 500

    for i in range(
        0,
        len(records),
        batch_size,
    ):

        batch = records[
            i : i + batch_size
        ]

        start_number = i + 1
        end_number = min(
            i + batch_size,
            len(records),
        )

        print(
            f"Uploading records "
            f"{start_number}-{end_number}..."
        )

        result = (
            supabase
            .table("sanctions_entities")
            .upsert(
                batch,
                on_conflict="jurisdiction,official_id",
            )
            .execute()
        )

        print(
            f"Uploaded records "
            f"{start_number}-{end_number}."
        )

    print("")
    print(
        f"SUCCESS: Uploaded "
        f"{len(records)} UK records to Supabase."
    )


if __name__ == "__main__":
    ingest_uk_sanctions()
