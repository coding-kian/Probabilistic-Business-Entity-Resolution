# Probabilistic Business Entity Resolution (Historic)
*Published: 15/02/2026*
## Introduction
This project is from early 2023, implementing a probabilistic entity resolution for noisy business data. Local businesses are discovered via the Google Maps Places API and resolved using UK Companies House Records for interpretable confidence scoring metric.


The output consists of confidence ranked structured contact and governance signals, extracted under real world API constraints, suitable for reliability monitoring and anomoly detection.

---

## Problem
Publicly available business data is highly ambiguous, the core challenge is not scraping it is resolving ambiguity and relationships
- Name variations (Ltd, Limited, LLP, abbreviations)
- Partial API matches
- Incomplete, inconsistent or dublicated websites/contact signals
- Multiple candidate companies per query

---

## Method
### 1. Geospatial Querying
Spatial coverage is achieved through
- A custom SQLite database created using UK postcodes, longitudes and latitudes (excluded from repo)
- Bounding box computation
- Google Places API queries (max radius 50km, <=60 results per cell)

### 2. Probabilistic Entity Resolution
The highest scoring candidate is selected, with overlapping ratios acting as a lightweight match confidence proxy, producing deterministic and interpretable scoring. The company hosue candidates are ranked using: 
- Name length similarity constraints
- Active company/director filtering
- Overlapping page token results


### 3. Contact Signal Extraction
Fetches the website and extracts the follow from the contact page, to produce signals under constrained extraction rules
- Emails extracted via regex & `mailto <tag>` 
- Phones extracted via pattern detection & `tel <tag>`

### 4. Governance 
For accepted probability matches, governance is able interpreted through. 
- Active directors retrieved
- Appointment dates retained
- Temporal structural is preserved
- Stability and change over time

---

## Data
### Inputs
* Google Maps Places (business discovery)
* UK Companies House (entity and director data)
* Business websites (unstructured contact signals)

### Outputs
* Business metadata
* Contact signals
* Company number
* Director list
* Match confidence score

### Suitable for
* Confidence distribution analysis
* Drift detection
* Failure rate anomaly detection
* Governance instability detection

---

## Design Principles
As a lightweight project, it is easily explainable and practical in design to support anaomoly detection.

- Probabilistic resolution system
- Multi sourced data pipeline
- Confidence ranked entity resolution with noise identification
- Deterministic and interpretable scoring
- Explicit thresholds (not hidden heuristics)
- Threading decreases runtime for bounded performance improvements under API rate constraints
- Clear structured outputs over messy data dumps

---
