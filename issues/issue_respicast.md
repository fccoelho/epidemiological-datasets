# 🔮 Add RespiCast accessor (European Respiratory Diseases Forecasting Hub)

## Overview

Add accessor for **RespiCast**, the European Respiratory Diseases Forecasting Hub that provides ensemble forecasts for influenza, COVID-19, and RSV.

**Data Source:** https://www.ecdc.europa.eu/en/publications-data/european-respiratory-diseases-forecasting-hub-respicast  
**Type:** Forecasting Hub / Predictive Models  
**Coverage:** EU/EEA countries  
**Update Frequency:** Weekly (every Wednesday during active season)

---

## Background

RespiCast is a collaborative forecasting hub that aggregates predictions from multiple international modeling teams. It provides ensemble forecasts for key respiratory diseases, helping public health authorities prepare for healthcare demands.

---

## Data Available

### Forecast Targets:

#### 1. Influenza
- **Indicators:**
  - ILI (Influenza-like Illness) rate
  - ARI (Acute Respiratory Infection) rate
  - Hospital admissions
  - ICU admissions
- **Horizon:** 1-4 weeks ahead

#### 2. COVID-19
- **Indicators:**
  - Case notifications
  - Hospital admissions
  - ICU admissions
  - Deaths
- **Horizon:** 1-4 weeks ahead

#### 3. Respiratory Syncytial Virus (RSV)
- **Indicators:**
  - Hospitalizations
  - Seasonal peak timing
- **Horizon:** 1-4 weeks ahead

### Model Outputs:
- **Point forecasts:** Most likely value
- **Probabilistic forecasts:** Uncertainty quantification
- **Prediction intervals:** 50%, 90%, 95% intervals
- **Ensemble forecasts:** Aggregated across all models
- **Individual model forecasts:** For comparison

### Geographic Coverage:
- 30 EU/EEA countries
- Country-level forecasts
- Regional forecasts (where available)

### Season Coverage:
- 2020-2021 season (COVID-19 pandemic)
- 2021-2022 season
- 2022-2023 season
- 2023-2024 season (ongoing)

---

## API / Data Access

### Data Repository:
- **GitHub:** https://github.com/european-modelling-hubs/RespiCast
- **Format:** CSV files (structured)
- **License:** Open data (CC-BY 4.0)
- **Access:** Public, no registration required

### File Structure:
```
├── data-truth/
│   └── truth_{country}.csv
├── model-forecasts/
│   ├── modelA/
│   ├── modelB/
│   └── ...
└── ensemble-forecasts/
    └── ensemble_{target}_{date}.csv
```

### Direct Data Access:
- Raw forecast files via GitHub API
- Truth data (observed values)
- Ensemble aggregates
- Individual model contributions

---

## Implementation Plan

### Phase 1: Data Retrieval
- [ ] Connect to RespiCast GitHub repository
- [ ] Fetch truth data (observed values)
- [ ] Fetch ensemble forecasts
- [ ] Parse forecast file formats

### Phase 2: Data Processing
- [ ] Extract point forecasts
- [ ] Extract prediction intervals
- [ ] Align forecasts with truth data
- [ ] Calculate forecast accuracy metrics

### Phase 3: Advanced Features
- [ ] Compare multiple models
- [ ] Evaluate forecast accuracy
- [ ] Generate confidence intervals
- [ ] Seasonal trend analysis

---

## Proposed Interface

```python
from epidemiological_datasets import RespiCastAccessor

respicast = RespiCastAccessor()

# Get latest ensemble forecast for Germany
forecast_de = respicast.get_ensemble_forecast(
    country="Germany",
    disease="influenza",
    target="ili_rate",
    horizon_weeks=4
)

# Get COVID-19 hospitalization forecast
hosp_forecast = respicast.get_forecast(
    country="France",
    disease="COVID-19",
    target="hospital_admissions",
    forecast_date="latest"
)

# Compare models for specific week
model_comparison = respicast.compare_models(
    country="Italy",
    disease="influenza",
    target_date="2024-03-15",
    metric="ili_rate"
)

# Get forecast accuracy (after target date passed)
accuracy = respicast.evaluate_forecast(
    country="Spain",
    disease="COVID-19",
    forecast_date="2024-01-15",
    target_date="2024-02-15"
)

# Get all available models
models = respicast.get_available_models()

# Get forecast history
history = respicast.get_forecast_history(
    country="Netherlands",
    disease="influenza",
    season="2023-2024"
)
```

---

## Data Schema

### Forecast Data:
```json
{
  "forecast_date": "2024-03-15",
  "target_date": "2024-03-22",
  "country": "Germany",
  "country_code": "DE",
  "disease": "influenza",
  "target": "ili_rate",
  "model": "ensemble",
  "point_forecast": 125.5,
  "quantile_0.025": 98.2,
  "quantile_0.25": 115.8,
  "quantile_0.5": 125.5,
  "quantile_0.75": 135.2,
  "quantile_0.975": 158.9,
  "season": "2023-2024",
  "horizon_week": 1
}
```

### Truth Data (Observed):
```json
{
  "date": "2024-03-15",
  "country": "Germany",
  "country_code": "DE",
  "disease": "influenza",
  "target": "ili_rate",
  "observed_value": 128.3,
  "data_source": "ERVISS"
}
```

---

## Related Resources

- **RespiCast Hub:** https://respicast.ecdc.europa.eu/
- **GitHub Repository:** https://github.com/european-modelling-hubs/RespiCast
- **ECDC Page:** https://www.ecdc.europa.eu/en/publications-data/european-respiratory-diseases-forecasting-hub-respicast
- **Related Hubs:**
  - COVID-19 Forecast Hub (global)
  - US FluSight (CDC)

---

## Use Cases

1. **Healthcare Planning:** Predict hospital capacity needs
2. **Resource Allocation:** Plan vaccine distribution
3. **Public Communication:** Inform public about expected trends
4. **Research:** Evaluate forecasting models
5. **Policy Making:** Early warning system activation

---

## Priority

**Medium** - Unique forecasting data valuable for predictive epidemiology. Complements surveillance data with forward-looking projections.

---

## Labels

`enhancement`, `data-source`, `europe`, `forecasting`, `predictive-models`, `help wanted`
