# 💊 Add ESAC-Net accessor (European Antimicrobial Consumption Network)

## Overview

Add accessor for **ESAC-Net** (European Surveillance of Antimicrobial Consumption Network), which provides standardized data on antimicrobial consumption in Europe.

**Data Source:** https://www.ecdc.europa.eu/en/publications-data/antimicrobial-consumption-dashboard  
**Type:** Drug Consumption Surveillance  
**Coverage:** EU/EEA countries  
**Update Frequency:** Annual (with some quarterly data)

---

## Background

ESAC-Net is the largest publicly funded system for surveillance of antimicrobial consumption in the world. It provides comparable and validated data on antibiotic use across European countries, essential for monitoring antimicrobial resistance (AMR) and stewardship programs.

---

## Data Available

### Antimicrobial Categories:

#### By Anatomical Therapeutic Chemical (ATC) Classification:
- **J01:** Antibacterials for systemic use
  - J01A: Tetracyclines
  - J01B: Amphenicols
  - J01C: Beta-lactam antibacterials, penicillins
  - J01D: Other beta-lactam antibacterials
  - J01E: Sulfonamides and trimethoprim
  - J01F: Macrolides, lincosamides and streptogramins
  - J01G: Aminoglycosides
  - J01M: Quinolones
  - J01X: Other antibacterials

- **J02:** Antimycotics for systemic use
- **J04:** Antimycobacterials
- **J05:** Antivirals for systemic use

### Healthcare Settings:
- **Community (primary care)**
- **Hospital sector**
- **Total consumption**

### Metrics:
- **DDD (Defined Daily Dose):** Standardized consumption measure
- **DID (DDD per 1,000 inhabitants per day):** Population-adjusted
- **PD (Packages/1,000 inhabitants/day):** Alternative measure
- **Euros:** Cost data (where available)

### Time Coverage:
- Historical data: 1997 onwards
- Most countries: 2005 onwards
- Latest data: Previous year (with 6-12 month delay)

---

## API / Data Access

### Access Methods:

#### 1. Interactive Dashboard
- **URL:** https://www.ecdc.europa.eu/en/publications-data/antimicrobial-consumption-dashboard
- **Access:** Public, open
- **Features:** Interactive visualizations, country comparisons

#### 2. Data Downloads
- **Format:** CSV, Excel
- **Granularity:** By country, year, ATC code
- **Access:** Direct download from dashboard

#### 3. ECDC Data Portal
- **Access:** Via EpiPulse (for detailed data)
- **API:** May be available through EpiPulse API

### Data Quality:
- Validated data (quality checks applied)
- Comparable across countries (standardized methodology)
- Missing data flagged with explanations

---

## Implementation Plan

### Phase 1: Dashboard Data Extraction
- [ ] Analyze dashboard structure
- [ ] Identify data download endpoints
- [ ] Implement CSV data fetching
- [ ] Parse ATC classification system

### Phase 2: Data Processing
- [ ] Normalize DDD calculations
- [ ] Handle country-specific variations
- [ ] Process time-series data
- [ ] Calculate derived metrics

### Phase 3: Advanced Features
- [ ] Compare consumption patterns across countries
- [ ] Analyze trends over time
- [ ] Correlate with AMR data (if available)
- [ ] Generate stewardship reports

---

## Proposed Interface

```python
from epidemiological_datasets import ESACNetAccessor

esac = ESACNetAccessor()

# Get total antibiotic consumption for a country
germany_consumption = esac.get_consumption(
    country="Germany",
    year=2022,
    setting="community"  # or "hospital", "total"
)

# Get consumption by antibiotic class
penicillins = esac.get_consumption_by_atc(
    country="France",
    atc_code="J01C",  # Penicillins
    years=range(2018, 2023)
)

# Compare multiple countries
comparison = esac.compare_countries(
    countries=["Germany", "France", "Italy", "Spain"],
    year=2022,
    metric="DID"  # DDD per 1,000 inhabitants per day
)

# Get trend analysis
trend = esac.get_trend(
    country="Netherlands",
    atc_code="J01M",  # Quinolones
    start_year=2015,
    end_year=2022
)

# Get all available countries
countries = esac.get_available_countries()

# Get data for specific antibiotic
macrolides = esac.get_antibiotic_data(
    country="Belgium",
    antibiotic_class="macrolides",
    year=2022,
    setting="total"
)

# Calculate consumption ranking
ranking = esac.get_ranking(
    year=2022,
    atc_code="J01",  # All antibacterials
    metric="DID"
)
```

---

## Data Schema

```json
{
  "country": "Germany",
  "country_code": "DE",
  "year": 2022,
  "setting": "community",
  "atc_code": "J01C",
  "atc_name": "Beta-lactam antibacterials, penicillins",
  "DDD_total": 1250000,
  "DID": 15.2,
  "PD": 4.8,
  "population": 83000000,
  "data_quality": "validated",
  "last_updated": "2023-11-15"
}
```

---

## Related Resources

- **Dashboard:** https://www.ecdc.europa.eu/en/publications-data/antimicrobial-consumption-dashboard
- **ESAC-Net Website:** https://www.ecdc.europa.eu/en/about-us/partnerships-and-networks/disease-and-laboratory-networks/esac-net
- **Methodology:** ECDC technical reports on antimicrobial consumption
- **Related Data:** EARS-Net (Antimicrobial Resistance Surveillance)

---

## Use Cases

1. **Antimicrobial Stewardship:** Monitor antibiotic use patterns
2. **Policy Evaluation:** Assess impact of stewardship programs
3. **Research:** Study drivers of antimicrobial resistance
4. **International Comparisons:** Benchmark against EU averages
5. **Trend Monitoring:** Identify increasing/decreasing consumption
6. **Target Setting:** Define reduction targets for antibiotic use

---

## Correlation with Other Datasets

### ESAC-Net + EARS-Net:
- ESAC-Net: Antibiotic consumption
- EARS-Net: Antimicrobial resistance
- **Combined:** Analyze consumption-resistance relationships

### ESAC-Net + Disease Surveillance:
- Compare antibiotic use with disease burden
- Assess appropriate prescribing

---

## Priority

**Medium** - Important for AMR research and policy, but more specialized than general disease surveillance. Complements other ECDC datasets well.

---

## Labels

`enhancement`, `data-source`, `europe`, `antimicrobials`, `AMR`, `pharmaceutical`, `help wanted`
