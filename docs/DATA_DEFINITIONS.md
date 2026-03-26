# Data Definitions

This document describes the publication datasets used in this repository and the meaning of the main columns.

## Files

- `Papers.csv`: original raw publication export.
- `papers_filtered.csv`: cleaned dataset produced by `pre_processing.ipynb`.
- `pre_processing.ipynb`: notebook that contains the current transformation logic.

## Current Dataset Summary

### Raw Input: `Papers.csv`

- Rows: **3221**
- Columns: **10**

Columns:

- `Unnamed: 0`
- `title`
- `authors`
- `nc_state_people`
- `DOI`
- `PMID`
- `year`
- `url`
- `topics`
- `abstract`

### Processed Output: `papers_filtered.csv`

- Rows: **3159**
- Columns: **8**

Columns:

- `title`
- `authors`
- `nc_state_people`
- `DOI`
- `year`
- `topics`
- `nc_authors`
- `unity_ids`

## Raw Dataset Definitions

| Column | Type | Description |
|---|---|---|
| `Unnamed: 0` | `int64` | Exported index-like column from an earlier data source. |
| `title` | `object` | Publication title. |
| `authors` | `object` | Semicolon-separated author list as a raw string. |
| `nc_state_people` | `object` | NC State-affiliated people listed in `Name (unityid)` style entries. |
| `DOI` | `object` | DOI identifier for the publication. |
| `PMID` | `float64` | PubMed identifier when available. |
| `year` | `int64` | Publication year. |
| `url` | `object` | Source or OpenAlex URL. |
| `topics` | `object` | Topic labels associated with the publication. |
| `abstract` | `object` | Publication abstract text when available. |

## Processed Dataset Definitions

| Column | Type | Description |
|---|---|---|
| `title` | `object` | Publication title. |
| `authors` | `object` | Original semicolon-separated author list. |
| `nc_state_people` | `object` | Original NC State entries from the source data. |
| `DOI` | `object` | DOI identifier for the publication. |
| `year` | `int64` | Publication year. |
| `topics` | `object` | Topic labels used in downstream analysis. |
| `nc_authors` | `object` | Parsed NC State author names matched from the source author list. |
| `unity_ids` | `object` | Unity IDs extracted from `nc_state_people`. |

## Current Preprocessing Behavior

The preprocessing notebook currently:

- reads `Papers.csv`,
- drops unused columns such as `Unnamed: 0`, `PMID`, `url`, and `abstract`,
- removes rows with missing values needed for downstream processing,
- parses NC State entries into author names and Unity IDs,
- performs quality checks on parsed NC State information,
- and writes the cleaned output to `papers_filtered.csv`.
