# 🌍 Add EpiPulse accessor (ECDC European Surveillance Portal)

## Overview

Add accessor for **EpiPulse**, the European surveillance portal for infectious diseases from ECDC (European Centre for Disease Prevention and Control).

**Data Source:** https://www.ecdc.europa.eu/en/publications-data/epipulse  
**Type:** Official EU Surveillance Data  
**Coverage:** EU/EEA countries + WHO European Region  
**Update Frequency:** Daily/Weekly (disease-dependent)

---

## Background

EpiPulse was launched in June 2021 and integrates several surveillance systems:
- TESSy (The European Surveillance System)
- EPIS platforms (Epidemic Intelligence Information System)
- Event and Threat Management System

It provides the most comprehensive infectious disease surveillance data for Europe.

---

## Data Available

### Core Datasets:
- **Indicator-based surveillance:** Case data for 50+ diseases
- **Event-based surveillance:** Public health events and threats
- **Molecular typing data:** Pathogen genomic surveillance
- **Whole-genome sequencing:** For selected pathogens

### Priority Diseases:
- COVID-19
- Influenza
- RSV
- Mpox
- Measles
- Legionnaires' disease
- Antimicrobial resistance

### Geographic Coverage:
- 27 EU Member States
- 3 EEA countries (Iceland, Liechtenstein, Norway)
- WHO European Region (53 countries total)

---

## API / Data Access

### Access Method:
- **Registration Required:** Yes (free for public health professionals/researchers)
- **API:** Available via EpiPulse portal
- **Downloads:** CSV, Excel, JSON formats

### Authentication:
- ECDC account required
- API keys provided after registration

### Endpoint Structure (estimated):
```
https://epipulse.ecdc.europa.eu/api/v1/
  - /cases
  - /events
  - /threats
  - /diseases
  - /countries
```

---

## Implementation Plan

### Phase 1: Basic Access
- [ ] Implement authentication with EpiPulse API
- [ ] Create `EpiPulseAccessor` class
- [ ] Add method to list available diseases
- [ ] Add method to fetch case data by disease

### Phase 2: Data Retrieval
- [ ] Fetch time-series data
- [ ] Support country filtering
- [ ] Support date range queries
- [ ] Handle pagination for large datasets

### Phase 3: Advanced Features
- [ ] Event-based surveillance data
- [ ] Molecular typing access
- [ ] Genomic surveillance data
- [ ] Automated data quality checks

---

## Proposed Interface

```python
from epidemiological_datasets import EpiPulseAccessor

# Initialize
epipulse = EpiPulseAccessor(api_key="your_api_key")

# List available diseases
diseases = epipulse.get_available_diseases()

# Fetch COVID-19 data for Germany
covid_data = epipulse.get_cases(
    disease="COVID-19",
    country="Germany",
    start_date="2024-01-01",
    end_date="2024-12-31"
)

# Get all EU countries data for influenza
influenza_eu = epipulse.get_cases(
    disease="Influenza",
    region="EU",
    season="2023-2024"
)

# Get public health events
events = epipulse.get_events(
    category="outbreak",
    country="France",
    timeframe="last_30_days"
)
```

---

## Data Schema

### Case Data Structure:
```json
{
  "disease": "COVID-19",
  "country": "Germany",
  "country_code": "DE",
  "date": "2024-03-15",
  "cases": 1250,
  "deaths": 15,
  "hospitalizations": 120,
  "icu_admissions": 15,
  "source": "EpiPulse",
  "data_quality": "confirmed"
}
```

---

## Related Resources

- **Portal:** https://epipulse.ecdc.europa.eu/
- **Documentation:** https://www.ecdc.europa.eu/en/publications-data/epipulse
- **Data Description:** Available in portal after registration
- **Terms of Use:** ECDC data disclaimer applies

---

## Priority

**High** - This is the primary European surveillance system and would provide comprehensive EU coverage currently missing from the library.

---

## Labels

`enhancement`, `data-source`, `europe`, `ecdc`, `help wanted`
