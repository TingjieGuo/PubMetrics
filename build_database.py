from pathlib import Path
import csv
import json
import re
import time
import xml.etree.ElementTree as ET

import requests


# ============================================================
# Configuration
# ============================================================

JCR_FOLDER = Path("jcr")
DATA_FOLDER = Path("data")

OUTPUT_FILE = DATA_FOLDER / "journals.json"
UNMATCHED_FILE = DATA_FOLDER / "unmatched.json"
AMBIGUOUS_FILE = DATA_FOLDER / "ambiguous.json"

DATA_FOLDER.mkdir(exist_ok=True)

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

TOOL_NAME = "pubmed-journal-metrics"

# Replace this with your real email address
EMAIL = "your-email@example.com"

# Optional
NCBI_API_KEY = ""

SEARCH_BATCH_SIZE = 100
FETCH_BATCH_SIZE = 100

REQUEST_DELAY = 0.4 if not NCBI_API_KEY else 0.12


# ============================================================
# General helper functions
# ============================================================

def clean(value):
    if value is None:
        return ""

    return value.strip()


def clean_issn(value):
    value = clean(value)

    if value.upper() in {
        "",
        "N/A",
        "NA",
        "NONE",
        "-"
    }:
        return ""

    if not re.fullmatch(r"\d{4}-\d{3}[\dXx]", value):
        return ""

    return value.upper()


def normalize_name(value):
    return " ".join(
        clean(value).casefold().split()
    )


def chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


# ============================================================
# Read JCR files
# ============================================================

def find_header_row(path):
    with open(
        path,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        reader = csv.reader(f)

        for i, row in enumerate(reader):
            if row and row[0].strip() == "Journal name":
                return i

    raise ValueError(
        f"Could not find header row in {path}"
    )


def read_jcr_file(path):
    header_row = find_header_row(path)

    with open(
        path,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        lines = f.readlines()

    reader = csv.DictReader(
        lines[header_row:]
    )

    return list(reader)


# ============================================================
# 1. Read all JCR exports
# ============================================================

all_rows = []

for path in sorted(JCR_FOLDER.glob("*.csv")):
    rows = read_jcr_file(path)

    print(
        f"{path.name}: "
        f"{len(rows)} rows"
    )

    all_rows.extend(rows)


print()

print(
    f"Total rows before deduplication: "
    f"{len(all_rows)}"
)


# ============================================================
# 2. Merge duplicated journals
# ============================================================

journals = {}

identifier_index = {}
name_index = {}

skipped_rows = 0


for row in all_rows:

    name = clean(
        row.get("Journal name")
    )

    normalized_name = normalize_name(name)

    jcr_abbreviation = clean(
        row.get("JCR Abbreviation")
    )

    issn = clean_issn(
        row.get("ISSN")
    )

    eissn = clean_issn(
        row.get("eISSN")
    )

    category = clean(
        row.get("Category")
    )

    quartile = clean(
        row.get("JIF Quartile")
    )

    jif = clean(
        row.get("2025 JIF")
    )


    # --------------------------------------------------------
    # Skip non-journal/footer rows
    # --------------------------------------------------------

    if not issn and not eissn:
        skipped_rows += 1
        continue


    identifiers = [
        identifier
        for identifier in [issn, eissn]
        if identifier
    ]


    journal_key = None


    # --------------------------------------------------------
    # Match existing journal by ISSN/eISSN
    # --------------------------------------------------------

    for identifier in identifiers:

        if identifier in identifier_index:

            journal_key = identifier_index[
                identifier
            ]

            break


    # --------------------------------------------------------
    # Fallback: exact normalized journal name
    # --------------------------------------------------------

    if (
        journal_key is None
        and normalized_name in name_index
    ):

        journal_key = name_index[
            normalized_name
        ]


    # --------------------------------------------------------
    # Create new journal
    # --------------------------------------------------------

    if journal_key is None:

        if issn:
            journal_key = issn

        elif eissn:
            journal_key = eissn

        else:
            journal_key = f"name:{normalized_name}"


        journals[journal_key] = {
            "name": name,
            "jcr_abbreviation": jcr_abbreviation,

            # These are filled later after NLM matching
            "pubmed_abbreviation": "",
            "nlm_id": "",

            "issn": issn,
            "eissn": eissn,
            "jcr_year": 2025,
            "jif": jif if jif else None,
            "categories": [],
        }


    journal = journals[
        journal_key
    ]


    # --------------------------------------------------------
    # Register identifiers
    # --------------------------------------------------------

    for identifier in identifiers:

        identifier_index[
            identifier
        ] = journal_key


    if normalized_name:

        name_index[
            normalized_name
        ] = journal_key


    # --------------------------------------------------------
    # Fill missing identifiers
    # --------------------------------------------------------

    if not journal["issn"] and issn:
        journal["issn"] = issn


    if not journal["eissn"] and eissn:
        journal["eissn"] = eissn


    # --------------------------------------------------------
    # Preserve distinct categories
    # --------------------------------------------------------

    category_entry = {
        "name": category,
        "quartile": quartile,
    }


    if (
        category
        and category_entry
        not in journal["categories"]
    ):

        journal[
            "categories"
        ].append(
            category_entry
        )


print(
    f"Skipped rows without valid ISSN/eISSN: "
    f"{skipped_rows}"
)

print(
    f"Unique journals: "
    f"{len(journals)}"
)


multi_category_journals = [
    journal
    for journal in journals.values()
    if len(journal["categories"]) > 1
]


print(
    f"Journals with multiple categories: "
    f"{len(multi_category_journals)}"
)


# ============================================================
# 3. Collect all unique ISSNs
# ============================================================

all_issns = set()


for journal in journals.values():

    if journal["issn"]:
        all_issns.add(
            journal["issn"]
        )

    if journal["eissn"]:
        all_issns.add(
            journal["eissn"]
        )


all_issns = sorted(
    all_issns
)


print()

print(
    f"Unique ISSN/eISSN identifiers "
    f"to query: {len(all_issns)}"
)


# ============================================================
# NCBI request helper
# ============================================================

def ncbi_request(
    endpoint,
    data,
    retries=3
):

    url = (
        f"{EUTILS_BASE}/"
        f"{endpoint}"
    )


    common = {
        "tool": TOOL_NAME,
        "email": EMAIL,
    }


    if NCBI_API_KEY:
        common["api_key"] = NCBI_API_KEY


    payload = {
        **data,
        **common,
    }


    for attempt in range(
        1,
        retries + 1
    ):

        try:

            response = requests.post(
                url,
                data=payload,
                timeout=60,
            )

            response.raise_for_status()

            time.sleep(
                REQUEST_DELAY
            )

            return response.text


        except requests.RequestException as exc:

            print(
                f"Request failed "
                f"(attempt {attempt}/{retries}): "
                f"{exc}"
            )


            if attempt == retries:
                raise


            time.sleep(
                attempt * 2
            )


# ============================================================
# 4. Search NLM Catalog by ISSN in batches
# ============================================================

nlm_ids = set()


search_batches = list(
    chunks(
        all_issns,
        SEARCH_BATCH_SIZE
    )
)


print()

print(
    f"Searching NLM in "
    f"{len(search_batches)} batches..."
)


for batch_number, batch in enumerate(
    search_batches,
    start=1
):

    print(
        f"Search batch "
        f"{batch_number}/"
        f"{len(search_batches)}"
    )


    query_parts = [
        f'"{issn}"[issn]'
        for issn in batch
    ]


    query = " OR ".join(
        query_parts
    )


    xml_text = ncbi_request(
        "esearch.fcgi",
        {
            "db": "nlmcatalog",
            "term": query,
            "retmode": "xml",
            "retmax": 1000,
        }
    )


    root = ET.fromstring(
        xml_text
    )


    ids = [
        element.text
        for element
        in root.findall(
            "./IdList/Id"
        )
        if element.text
    ]


    nlm_ids.update(
        ids
    )


print()

print(
    f"NLM records found: "
    f"{len(nlm_ids)}"
)


# ============================================================
# 5. Parse NLM records
# ============================================================

def parse_nlm_record(record):

    nlm_id = clean(
        record.findtext(
            "NlmUniqueID"
        )
    )

    medline_ta = clean(
        record.findtext(
            "MedlineTA"
        )
    )

    title = clean(
        record.findtext(
            "./TitleMain/Title"
        )
    )


    valid_issns = set()

    print_issn = None
    electronic_issn = None


    for element in record.findall("ISSN"):

        if element.attrib.get("ValidYN") != "Y":
            continue


        value = clean_issn(
            element.text
        )


        if not value:
            continue


        valid_issns.add(
            value
        )


        issn_type = element.attrib.get(
            "IssnType"
        )


        if issn_type == "Print":
            print_issn = value

        elif issn_type == "Electronic":
            electronic_issn = value


    return {
        "nlm_id": nlm_id,
        "title": title,
        "pubmed_abbreviation": medline_ta,
        "print_issn": print_issn,
        "electronic_issn": electronic_issn,
        "valid_issns": sorted(
            valid_issns
        ),
    }


# ============================================================
# 6. Fetch NLM records in batches
# ============================================================

nlm_records = []


nlm_id_list = sorted(
    nlm_ids
)


fetch_batches = list(
    chunks(
        nlm_id_list,
        FETCH_BATCH_SIZE
    )
)


print()

print(
    f"Fetching NLM metadata in "
    f"{len(fetch_batches)} batches..."
)


for batch_number, batch in enumerate(
    fetch_batches,
    start=1
):

    print(
        f"Fetch batch "
        f"{batch_number}/"
        f"{len(fetch_batches)}"
    )


    xml_text = ncbi_request(
        "efetch.fcgi",
        {
            "db": "nlmcatalog",
            "id": ",".join(batch),
            "retmode": "xml",
        }
    )


    root = ET.fromstring(
        xml_text
    )


    for record in root.findall(
        ".//NLMCatalogRecord"
    ):

        parsed = parse_nlm_record(
            record
        )

        nlm_records.append(
            parsed
        )


print()

print(
    f"NLM records parsed: "
    f"{len(nlm_records)}"
)


# ============================================================
# 7. Build ISSN → NLM record index
# ============================================================

issn_to_nlm_records = {}


for record in nlm_records:

    for issn in record["valid_issns"]:

        issn_to_nlm_records.setdefault(
            issn,
            []
        ).append(
            record
        )


# ============================================================
# 8. Ambiguous-match scoring
# ============================================================

def score_nlm_candidate(
    journal,
    record
):

    jcr_identifiers = {
        identifier
        for identifier in [
            journal["issn"],
            journal["eissn"],
        ]
        if identifier
    }


    nlm_identifiers = set(
        record["valid_issns"]
    )


    matched_identifiers = (
        jcr_identifiers
        & nlm_identifiers
    )


    score = 0


    # Strongest signal
    score += (
        len(matched_identifiers)
        * 10
    )


    # Prefer an NLM record that actually has MedlineTA
    if record["pubmed_abbreviation"]:
        score += 3


    # Extra confidence if titles are an exact normalized match
    if (
        normalize_name(journal["name"])
        == normalize_name(record["title"])
    ):
        score += 5


    return score


# ============================================================
# 9. Match JCR journals to NLM records
# ============================================================

unmatched = []
ambiguous = []

matched_count = 0
auto_resolved_count = 0


for journal_key, journal in journals.items():

    candidate_records = {}


    for identifier in [
        journal["issn"],
        journal["eissn"]
    ]:

        if not identifier:
            continue


        for record in issn_to_nlm_records.get(
            identifier,
            []
        ):

            candidate_records[
                record["nlm_id"]
            ] = record


    candidates = list(
        candidate_records.values()
    )


    # --------------------------------------------------------
    # No match
    # --------------------------------------------------------

    if len(candidates) == 0:

        unmatched.append(
            {
                "name": journal["name"],
                "issn": journal["issn"],
                "eissn": journal["eissn"],
                "reason": (
                    "No NLM record matched "
                    "the JCR ISSN/eISSN"
                ),
            }
        )

        continue


    # --------------------------------------------------------
    # One clear match
    # --------------------------------------------------------

    if len(candidates) == 1:

        record = candidates[0]

        journal["pubmed_abbreviation"] = (
            record["pubmed_abbreviation"]
        )

        journal["nlm_id"] = (
            record["nlm_id"]
        )

        matched_count += 1

        continue


    # --------------------------------------------------------
    # Multiple matches
    # Score candidates conservatively
    # --------------------------------------------------------

    scored_candidates = []


    for record in candidates:

        score = score_nlm_candidate(
            journal,
            record
        )

        scored_candidates.append(
            {
                "score": score,
                "record": record,
            }
        )


    scored_candidates.sort(
        key=lambda item: item["score"],
        reverse=True,
    )


    best_score = scored_candidates[0]["score"]


    best_candidates = [
        item["record"]
        for item in scored_candidates
        if item["score"] == best_score
    ]


    # --------------------------------------------------------
    # Unique best candidate
    # --------------------------------------------------------

    if len(best_candidates) == 1:

        record = best_candidates[0]

        journal["pubmed_abbreviation"] = (
            record["pubmed_abbreviation"]
        )

        journal["nlm_id"] = (
            record["nlm_id"]
        )

        matched_count += 1
        auto_resolved_count += 1

        continue


    # --------------------------------------------------------
    # Still ambiguous
    # --------------------------------------------------------

    ambiguous.append(
        {
            "name": journal["name"],
            "issn": journal["issn"],
            "eissn": journal["eissn"],
            "candidates": candidates,
        }
    )


# ============================================================
# 10. Write journals.json
# ============================================================

with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        journals,
        f,
        ensure_ascii=False,
        indent=2,
    )


# ============================================================
# 11. Write unmatched.json
# ============================================================

with open(
    UNMATCHED_FILE,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        unmatched,
        f,
        ensure_ascii=False,
        indent=2,
    )


# ============================================================
# 12. Write ambiguous.json
# ============================================================

with open(
    AMBIGUOUS_FILE,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        ambiguous,
        f,
        ensure_ascii=False,
        indent=2,
    )


# ============================================================
# Final report
# ============================================================

print()

print("=" * 60)

print("Finished.")

print(
    f"Total JCR journals: "
    f"{len(journals)}"
)

print(
    f"Matched to NLM: "
    f"{matched_count}"
)

print(
    f"Automatically resolved ambiguous matches: "
    f"{auto_resolved_count}"
)

print(
    f"Unmatched: "
    f"{len(unmatched)}"
)

print(
    f"Still ambiguous: "
    f"{len(ambiguous)}"
)

print()

print(
    f"Created: {OUTPUT_FILE}"
)

print(
    f"Created: {UNMATCHED_FILE}"
)

print(
    f"Created: {AMBIGUOUS_FILE}"
)

print("=" * 60)