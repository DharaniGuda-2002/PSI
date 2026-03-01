# PSI Data Documentation

This document explains the dataset used in this repository, how it is transformed, and what the final schema means.

## Files

- `Papers.csv`: Original raw dataset.
- `pre_processing.ipynb`: Notebook that performs cleaning and feature engineering.
- `papers_filtered.csv`: Final processed dataset used downstream.

## Dataset Summary

### Input (`Papers.csv`)

- Rows: **3,221**
- Columns: **10**

### Output (`papers_filtered.csv`)

- Rows: **3,148**
- Columns: **14**

### Columns removed from raw data

- `Unnamed: 0`
- `PMID`
- `url`
- `abstract`

### Row reduction summary

- Rows dropped due to missing values in required fields: **62**
- Additional rows dropped by quality checks (NC authors not found in authors section): **11**
- Total rows dropped: **73**

## Original Schema (`Papers.csv`)

| Column | Type (pandas) | Description |
|---|---|---|
| `Unnamed: 0` | `int64` | Row index-like column from prior export. |
| `title` | `object` | Paper title. |
| `authors` | `object` | Semicolon-separated author list (raw string). |
| `nc_state_people` | `object` | Semicolon-separated NC State entries, expected format like `Name (unityid)`. |
| `DOI` | `object` | DOI identifier. |
| `PMID` | `float64` | PubMed ID when available. |
| `year` | `int64` | Publication year. |
| `url` | `object` | Source/OpenAlex URL. |
| `topics` | `object` | Topic labels (string). |
| `abstract` | `object` | Paper abstract text. |

## Final Schema (`papers_filtered.csv`)

### Base columns retained from raw

| Column | Type (pandas) | Description |
|---|---|---|
| `title` | `object` | Paper title. |
| `authors` | `object` | Original semicolon-separated author list. |
| `nc_state_people` | `object` | Original NC State person entries. |
| `DOI` | `object` | DOI identifier. |
| `year` | `int64` | Publication year. |
| `topics` | `object` | Topic labels (string). |

### Engineered columns

| Column | Type (pandas) | Description |
|---|---|---|
| `co_author` | `object` | All authors except the first author, as a semicolon-separated string. |
| `nc_authors` | `object` | Authors from `authors` matched to entries in `nc_state_people` using normalized name/unity-id heuristics. |
| `unity_ids` | `object` | Unity IDs parsed from `nc_state_people`, semicolon-separated. |
| `count_nc_state_people` | `int64` | Number of NC State entries parsed from `nc_state_people`. |
| `count_nc_authors` | `int64` | Number of matched NC authors in `nc_authors`. |
| `count_unity_ids` | `int64` | Number of parsed unity IDs in `unity_ids`. |
| `has_invalid_nc_state_people_format` | `bool` | `True` if any `nc_state_people` entry is not in valid `Name (unityid)` format. |
| `counts_match` | `bool` | `True` when the three counts above are equal. |

## What Was Dropped

### Columns dropped from raw

- `Unnamed: 0` (index artifact)
- `PMID` (sparse/not needed in current pipeline)
- `url` (not required for this stage)
- `abstract` (large free-text field not used in this stage)

### Rows dropped from raw

- **62 rows** dropped due to nulls in required base columns (`authors` or `topics`).
- **11 rows** dropped due to count mismatch in otherwise valid-format `nc_state_people` rows.
- Total dropped from raw to final: **73 rows**.

## Known Data Notes for Future Contributors

- `co_author` can be null if only one author is present. In the final file, `co_author` has **65** null rows.
- Rows with invalid `nc_state_people` format are intentionally retained and flagged with `has_invalid_nc_state_people_format = True` for manual review/audit.
- `counts_match` is a reliability signal for author/unity-id reconciliation.

## Reproducing the Output

1. Open `pre_processing.ipynb`.
2. Run all cells in order.
3. Confirm the notebook saves `papers_filtered.csv`.

The notebook is the source of truth for transformation logic.
