# 🫁 Add ERVISS accessor (European Respiratory Virus Surveillance Summary)

## Overview

Add accessor for **ERVISS**, the European Respiratory Virus Surveillance Summary from ECDC.

**Data Source:** https://www.ecdc.europa.eu/en/publications-data/european-respiratory-virus-surveillance-summary-erviss  
**Type:** Weekly Epidemiological Summary  
**Coverage:** EU/EEA + WHO European Region (53 countries)  
**Update Frequency:** Weekly (every Thursday)

---

## Background

ERVISS provides integrated weekly surveillance data for respiratory viruses across Europe. It's a key resource for monitoring seasonal respiratory pathogens including influenza, RSV, and SARS-CoV-2.

---

## Data Available

### Viruses Covered:
1. **Influenza**
   - Type A (subtypes H1N1, H3N2)
   - Type B (lineages Victoria, Yamagata)
   - Sentinel and non-sentinel surveillance

2. **Respiratory Syncytial Virus (RSV)**
   - Seasonal patterns
   - Age-stratified data

3. **SARS-CoV-2**
   - Variant monitoring
   - Severity indicators

### Metrics Available:
- **ILI (Influenza-like Illness) rates**
- **ARI (Acute Respiratory Infection) rates**
- **Hospital/ICU admissions**
- **Virus detections by type/subtype**
- **Vaccine effectiveness estimates**
- **Severity indicators**

### Geographic Granularity:
- Country-level (primary)
- Regional data (where available)
- EU/EEA aggregate
- WHO European Region aggregate

---

## API / Data Access

### Access Method:
- **Public Dashboard:** Yes (open access)
- **Downloads:** CSV, Excel available
- **API:** May be available via EpiPulse integration

### Data Formats:
- Weekly aggregated data
- Time-series format
- Age-stratified where available

---

## Implementation Plan

### Phase 1: Dashboard Scraping/API
- [ ] Analyze dashboard structure
- [ ] Identify data download endpoints
- [ ] Implement data fetching

### Phase 2: Data Parsing
- [ ] Parse weekly summary data
- [ ] Handle multiple viruses
- [ ] Process time-series

### Phase 3: Advanced Features
- [ ] Season-aware queries
- [ ] Comparative analysis (country vs country)
- [ ] Trend detection

---

## Proposed Interface

```python
from epidemiological_datasets import ERVISSAccessor

erviss = ERVISSAccessor()

# Get latest weekly summary
latest = erviss.get_latest_weekly_summary()

# Get influenza data for specific season
influenza_2023 = erviss.get_influenza_data(
    season="2023-2024",
    country="France"
)

# Get RSV data across Europe
rsv_europe = erviss.get_rsv_data(
    season="2023-2024"
)

# Get SARS-CoV-2 data
covid_data = erviss.get_covid_data(
    start_date="2024-01-01",
    end_date="2024-03-31",
    metric="hospital_admissions"
)

# Compare countries
comparison = erviss.compare_countries(
    virus="Influenza",
    countries=["Germany", "France", "Italy"],
    metric="ili_rate"
)
```

---

## Data Schema

```json
{
  "week": "2024-W10",
  "country": "Germany",
  "country_code": "DE",
  "virus": "Influenza",
  "subtype": "A(H3N2)",
  "ili_rate": 125.5,
  "ari_rate": 850.2,
  "specimens_tested": 1500,
  "positive_cases": 450,
  "hospital_admissions": 120,
  "icu_admissions": 15,
  "deaths": 5,
  "season": "2023-2024"
}
```

---

## Related Issues

- Related to #XX (EpiPulse) - ERVISS data may be accessible via EpiPulse API
- Complements existing WHO/Europe data

---

## Priority

**Medium-High** - Important for respiratory disease surveillance in Europe. Weekly updates make it valuable for real-time monitoring.

---

## Labels

`enhancement`, `data-source`, `europe`, `respiratory`, `weekly-data`, `help wanted`
