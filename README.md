# PubMed Journal Metrics

A lightweight userscript that displays Journal Impact Factor (JIF) and JCR quartile information directly in PubMed search results.

The project also includes a Python script for building the journal database from JCR CSV exports and enriching it with PubMed/NLM journal abbreviations using the NCBI NLM Catalog.

## Features

- Displays JIF directly in PubMed search results
- Displays all JCR quartiles associated with a journal
- Preserves multiple categories, including repeated quartiles such as `Q1/Q1/Q2`
- Shows full JCR category information in a hover tooltip
- Uses PubMed/NLM journal abbreviations for reliable matching
- Loads journal data locally through the userscript resource system
- Does not make NCBI API requests during normal PubMed browsing
- Database can be rebuilt from updated JCR exports

## Repository Structure

```text
journal-metrics/
├── build_database.py
├── userscript/
│   └── pubmed-journal-metrics.user.js
├── data/
│   ├── journals.json
│   ├── unmatched.json
│   └── ambiguous.json
├── jcr/
│   └── *.csv
├── requirements.txt
├── .gitignore
└── README.md
```

The exact userscript filename or folder structure can be changed if desired.

### `build_database.py`

Builds the journal database from JCR CSV exports.

The script:

1. reads all CSV files in the `jcr/` directory
2. merges duplicate journals using ISSN/eISSN
3. preserves distinct JCR categories and quartiles
4. removes exact duplicate category entries
5. queries the NCBI NLM Catalog in batches
6. retrieves PubMed journal abbreviations (`MedlineTA`) and NLM IDs
7. resolves obvious duplicate NLM records conservatively
8. writes the generated database into `data/`

### `data/journals.json`

The main database used by the userscript.

Example:

```json
{
  "1471-0072": {
    "name": "NATURE REVIEWS MOLECULAR CELL BIOLOGY",
    "jcr_abbreviation": "NAT REV MOL CELL BIO",
    "pubmed_abbreviation": "Nat Rev Mol Cell Biol",
    "nlm_id": "100962782",
    "issn": "1471-0072",
    "eissn": "1471-0080",
    "jcr_year": 2025,
    "jif": "118",
    "categories": [
      {
        "name": "CELL BIOLOGY",
        "quartile": "Q1"
      }
    ]
  }
}
```

### `data/unmatched.json`

Contains JCR journals that could not be matched to an NLM Catalog record using their ISSN or eISSN.

Many of these journals are outside the biomedical literature and may never appear in PubMed, so an unmatched record is not necessarily a problem.

### `data/ambiguous.json`

Contains journals for which multiple NLM Catalog records remain equally plausible after automatic matching.

These records are intentionally left unresolved rather than guessed.

## Database Setup

Python 3 is required.

Create a virtual environment:

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

If `requirements.txt` has not yet been created, the current builder only requires:

```bash
python -m pip install requests
```

You can then generate `requirements.txt` with:

```bash
python -m pip freeze > requirements.txt
```

## Building the Database

Place your JCR CSV exports inside:

```text
jcr/
```

The filenames do not matter, as long as they end in `.csv`.

The script expects JCR columns including:

```text
Journal name
JCR Abbreviation
ISSN
eISSN
Category
2025 JIF
JIF Quartile
```

Before running the script, set your email address in `build_database.py`:

```python
EMAIL = "your-email@example.com"
```

NCBI recommends including an email address and tool name when using E-utilities.

Then run:

```bash
python build_database.py
```

The generated files will be written to:

```text
data/journals.json
data/unmatched.json
data/ambiguous.json
```

## Journal Matching

The database builder first merges JCR records using ISSN and eISSN.

For example, if the same journal appears in several JCR category exports, it is stored only once while retaining all distinct categories.

Exact duplicate category entries are removed:

```text
PHARMACOLOGY & PHARMACY: Q1
PHARMACOLOGY & PHARMACY: Q1
```

becomes one category entry.

Different categories with the same quartile are preserved:

```text
PHARMACOLOGY & PHARMACY: Q1
TOXICOLOGY: Q1
```

so the userscript can display:

```text
Q1/Q1
```

The builder then queries the NCBI NLM Catalog using ISSN/eISSN and retrieves:

- NLM Unique ID
- PubMed/NLM journal abbreviation (`MedlineTA`)
- valid print ISSN
- valid electronic ISSN

The PubMed abbreviation is stored in the database as:

```json
"pubmed_abbreviation": "Clin Pharmacokinet"
```

This allows the userscript to perform a direct journal lookup instead of scanning every journal in the database.

## Installing the Userscript

Install a userscript manager such as:

- Violentmonkey
- Tampermonkey

Then install or copy the PubMed Journal Metrics userscript from this repository into the userscript manager.

The userscript runs on:

```text
https://pubmed.ncbi.nlm.nih.gov/*
```

It loads the generated `journals.json` file as a userscript resource.

For each PubMed search result, it extracts the PubMed journal abbreviation from the citation and performs a direct lookup in the journal database.

A result may look like:

```text
Clin Pharmacokinet. 2025 Aug;64(8):...

JIF 4.0 · Q2

PMID: 12345678
```

Hovering over the badge displays the full JCR category information.

## Updating the Database

To update the database for a new JCR release:

1. replace or update the CSV files in `jcr/`
2. update the JCR year and JIF column name in `build_database.py` if necessary
3. run:

```bash
python build_database.py
```

4. commit the updated files in `data/`

The userscript will then use the updated database after its external resource is refreshed.

## Data Sources

Journal metrics are derived from Journal Citation Reports exports.

Journal identifiers and PubMed abbreviations are enriched using the NCBI NLM Catalog through NCBI E-utilities.

This project does not provide or redistribute raw JCR export files.

## Notes

This project is intended as a lightweight personal or research productivity tool.

JCR and Journal Impact Factor data are proprietary data products of Clarivate. Users are responsible for ensuring that their use and redistribution of derived data complies with the applicable Clarivate terms and licenses.

NCBI/NLM journal metadata is retrieved separately through NCBI E-utilities.

## License

The source code in this repository is licensed under the MIT License.

The generated journal data may incorporate information derived from third-party sources, including Journal Citation Reports (Clarivate) and the NCBI/NLM Catalog. Those data remain subject to the applicable terms and licenses of their respective providers.

The MIT License applies to the software in this repository and does not grant additional rights to third-party data.