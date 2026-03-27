# 🗺️ Add ECDC Atlas accessor (Atlas of Infectious Diseases)

## Overview

Add accessor for the **ECDC Atlas of Infectious Diseases**, an interactive platform with historical and current data for 50+ infectious diseases across Europe.

**Data Source:** https://atlas.ecdc.europa.eu/  
**Type:** Interactive Atlas with downloadable datasets  
**Coverage:** EU/EEA + additional European countries  
**Update Frequency:** Disease-dependent (weekly to annual)

---

## Background

The ECDC Atlas provides comprehensive spatiotemporal data on infectious diseases. It's an essential resource for epidemiological research, public health planning, and educational purposes.

---

## Data Available

### Disease Categories:

#### Vaccine-Preventable Diseases:
- Measles
- Mumps
- Rubella
- Pertussis (Whooping cough)
- Diphtheria
- Tetanus
- Polio
- Haemophilus influenzae type b
- Hepatitis B

#### Food- and Waterborne Diseases:
- Campylobacteriosis
- Salmonellosis
- Shigellosis
- Verotoxigenic E. coli (VTEC)
- Listeriosis
- Yersiniosis
- Hepatitis A

#### Sexually Transmitted Infections:
- Chlamydia
- Gonorrhoea
- Syphilis
- HIV/AIDS

#### Healthcare-Associated Infections:
- MRSA
- Antimicrobial resistance data

#### Vector-Borne Diseases:
- Lyme neuroborreliosis
- Tick-borne encephalitis
- Malaria (imported)

#### Respiratory Diseases:
- Legionnaires' disease
- Meningococcal disease
- Pneumococcal disease
- Tuberculosis

#### Other Diseases:
- Q fever
- Brucellosis
- Leptospirosis
- Toxoplasmosis
- Trichinellosis

---

## API / Data Access

### Access Method:
- **Public Access:** Yes (open)
- **Interactive Dashboard:** Yes
- **Data Downloads:** CSV format available
- **API:** Not officially documented; may require web scraping

### Download Options:
- Full datasets by disease
- Filtered by country, year, age group
- Time-series data
- Map data (geographic coordinates)

---

## Implementation Plan

### Phase 1: Web Scraping / API Discovery
- [ ] Analyze Atlas website structure
- [ ] Identify data download mechanisms
- [ ] Map disease identifiers
- [ ] Test download endpoints

### Phase 2: Data Retrieval
- [ ] Implement individual disease data fetching
- [ ] Support country filtering
- [ ] Support year range queries
- [ ] Handle geographic data

### Phase 3: Advanced Features
- [ ] Bulk download multiple diseases
- [ ] Spatiotemporal analysis support
- [ ] Integration with mapping libraries
- [ ] Automated data updates

---

## Proposed Interface

```python
from epidemiological_datasets import ECDCAtlasAccessor

atlas = ECDCAtlasAccessor()

# List available diseases
diseases = atlas.get_available_diseases()

# Get measles data for all EU countries
measles_data = atlas.get_disease_data(
    disease="measles",
    years=range(2019, 2024),
    countries="EU"  # or list of country codes
)

# Get salmonellosis with age stratification
salmonella = atlas.get_disease_data(
    disease="salmonellosis",
    country="Germany",
    year=2023,
    age_stratified=True
)

# Get geographic data for mapping
lyme_data = atlas.get_spatial_data(
    disease="lyme_neuroborreliosis",
    year=2023,
    resolution="NUTS2"  # regional level
)

# Get antimicrobial resistance data
amr_data = atlas.get_amr_data(
    pathogen="E. coli",
    antibiotic="cephalosporins",
    year=2023
)
```

---

## Data Schema

```json
{
  "disease": "measles",
  "disease_code": "MEAS",
  "country": "France",
  "country_code": "FR",
  "year": 2023,
  "month": 6,
  "cases": 45,
  "cases_male": 22,
  "cases_female": 23,
  "cases_0_4": 15,
  "cases_5_14": 20,
  "cases_15_plus": 10,
  "incidence_rate": 0.67,
  "death_count": 0,
  "notification_rate": 0.68,
  "data_source": "ECDC Atlas",
  "last_updated": "2024-01-15"
}
```

---

## Related Resources

- **Main Atlas:** https://atlas.ecdc.europa.eu/
- **ECDC Data Portal:** https://www.ecdc.europa.eu/en/data
- **Surveillance Atlas App:** Available as standalone download

---

## Notes

- Data quality varies by country and disease
- Some diseases have mandatory reporting, others voluntary
- Historical data available back to 1990s for some diseases
- GDPR compliance may affect data granularity

---

## Priority

**Medium** - Comprehensive historical dataset valuable for research and trend analysis. Good complement to real-time surveillance data.

---

## Labels

`enhancement`, `data-source`, `europe`, `historical-data`, `atlas`, `help wanted`
