# 📓 Example Notebooks

This directory contains Jupyter notebooks demonstrating how to use various epidemiological data sources.

## 📚 Available Notebooks

### 1. [01_pysus_brazilian_health_data.ipynb](notebooks/01_pysus_brazilian_health_data.ipynb)
**Brazilian Health Data with PySUS**

Demonstrates access to Brazil's public health data through DATASUS.

**Topics covered:**
- SINAN (Notifiable Diseases) - Dengue analysis
- SIM (Mortality Information System)
- SIH (Hospital Information System)
- Time series analysis
- Geographic comparisons across states
- Data export

**Data Sources:**
- Dengue cases by state and year
- Mortality statistics
- Hospitalization records

---

### 2. [02_who_global_health_data.ipynb](notebooks/02_who_global_health_data.ipynb)
**WHO Global Health Data with ghoclient**

Access World Health Organization global health indicators.

**Topics covered:**
- WHO Global Health Observatory (GHO) indicators
- Malaria incidence analysis
- Life expectancy trends
- Immunization coverage (DTP3)
- Comparative health dashboards
- Multi-indicator analysis

**Data Sources:**
- Disease burden indicators
- Health system statistics
- Risk factor data
- SDG health targets

---

### 3. [03_world_bank_health_indicators.ipynb](notebooks/03_world_bank_health_indicators.ipynb)
**World Bank Health Indicators**

Analyze health, nutrition, and population statistics from the World Bank.

**Topics covered:**
- Health expenditure analysis
- Health workforce statistics
- Disease burden indicators
- Comparative health dashboards
- Correlation analysis
- Regional comparisons

**Data Sources:**
- Health expenditure (% GDP and per capita)
- Physicians and hospital beds per capita
- Life expectancy and mortality rates
- Disease-specific indicators

---

### 4. [04_ecdc_european_surveillance.ipynb](notebooks/04_ecdc_european_surveillance.ipynb)
**ECDC European Disease Surveillance**

Access European Centre for Disease Prevention and Control data.

**Topics covered:**
- COVID-19 case surveillance
- Pandemic wave analysis
- Influenza surveillance
- Weekly case trends
- Cross-country comparisons
- Case fatality rates

**Data Sources:**
- COVID-19 cases and deaths
- Influenza-like illness (ILI) data
- European surveillance atlas

---

### 5. [05_multi_source_comparison.ipynb](notebooks/05_multi_source_comparison.ipynb)
**Multi-Source Health Data Comparison**

Combine and compare data from multiple sources.

**Topics covered:**
- Cross-validation across sources
- Data consistency checks
- Unified health index creation
- Regional comparisons
- Data quality assessment
- Composite indicators

**Use Cases:**
- Validate data across sources
- Identify discrepancies
- Create comprehensive dashboards
- Fill data gaps

---

### 6. [06_PAHO_Pan_American_Data.ipynb](notebooks/06_PAHO_Pan_American_Data.ipynb)
**PAHO (Pan American Health Organization) Data**

Access health data from the Americas (North, Central, South America and Caribbean).

**Topics covered:**
- Immunization coverage by country
- Disease surveillance (malaria, dengue, etc.)
- Mortality and demographic data
- Health system indicators
- Regional comparisons

**Data Sources:**
- PAHO Data Portal
- Country-level health statistics
- Vaccination coverage rates
- Disease burden estimates

---

### 7. [07_Eurostat_EU_Health_Data.ipynb](notebooks/07_Eurostat_EU_Health_Data.ipynb)
**Eurostat European Union Health Data**

Access European Union health statistics from Eurostat.

**Topics covered:**
- Healthcare expenditure and financing
- Mortality and causes of death
- Life expectancy trends
- Health workforce (physicians, nurses)
- Hospital beds and facilities
- Self-perceived health status

**Data Sources:**
- Eurostat Health Database
- EU member states statistics
- Healthcare system indicators

---

### 8. [08_OWID_Our_World_in_Data.ipynb](notebooks/08_OWID_Our_World_in_Data.ipynb)
**Our World in Data (OWID) Global Health Data**

Access comprehensive health datasets from Our World in Data, including COVID-19, vaccination, and excess mortality data.

**Topics covered:**
- COVID-19 cases, deaths, testing, hospitalizations
- Global vaccination progress
- Excess mortality estimates
- Test positivity rates
- Country comparisons
- Regional aggregates
- Reproduction rate (R) analysis

**Data Sources:**
- OWID COVID-19 Data (192 countries)
- GitHub: https://github.com/owid/covid-19-data
- API: https://covid.ourworldindata.org/data
- License: CC BY (Creative Commons Attribution)

---

### 9. [09_Colombia_INS_SIVIGILA_Data.ipynb](notebooks/09_Colombia_INS_SIVIGILA_Data.ipynb)
**Colombia INS (Instituto Nacional de Salud) SIVIGILA Data**

Access Colombian public health surveillance data from the National Health Institute (INS), including SIVIGILA notifiable disease surveillance.

**Topics covered:**
- SIVIGILA notifiable disease surveillance
- Vector-borne diseases (dengue, malaria, chikungunya, zika, yellow fever)
- Respiratory diseases (COVID-19, influenza)
- Department-level analysis across 33 departments
- 5 geographical regions (Andina, Caribe, Pacífica, Orinoquía, Amazonía)
- Weekly epidemiological bulletins
- Disease event groups classification

**Data Sources:**
- INS Colombia: https://www.ins.gov.co/
- SIVIGILA surveillance system
- Colombia Open Data Portal: https://www.datos.gov.co
- 33 notifiable diseases tracked

---

### 10. [10_Africa_CDC_Data.ipynb](notebooks/10_Africa_CDC_Data.ipynb)
**Africa CDC (African Centres for Disease Control and Prevention) Data**

Access African public health surveillance data from Africa CDC, covering disease outbreaks, COVID-19, vaccination coverage, and event-based surveillance across 55 African Union member states.

**Topics covered:**
- Disease outbreak surveillance and weekly outbreak briefs
- COVID-19 historical data for African countries
- Event-Based Surveillance (EBS) alerts
- Vaccination coverage tracking
- Priority diseases (Ebola, Marburg, Lassa fever, Cholera, Mpox, etc.)
- 5 Africa CDC regions (Central, Eastern, Northern, Southern, Western)
- 55 African Union member states
- Regional comparisons and country summaries

**Data Sources:**
- Africa CDC: https://africacdc.org/
- Weekly Outbreak Briefs
- IDSR (Integrated Disease Surveillance and Response)
- African Union Member State reports

---

## 🚀 Quick Start

### Installation

```bash
# Install required packages
pip install -r requirements.txt

# Or install individually
pip install pysus ghoclient wbgapi pandas matplotlib seaborn plotly requests
```

### Running the Notebooks

```bash
# Start Jupyter
jupyter notebook notebooks/

# Or use JupyterLab
jupyter lab notebooks/
```

---

## 📦 Requirements

### Core Dependencies

```
pysus>=1.0.0          # Brazilian health data
ghoclient>=1.0.0      # WHO data
wbgapi>=1.0.0         # World Bank data
pandas>=1.3.0
numpy>=1.21.0
matplotlib>=3.4.0
seaborn>=0.11.0
plotly>=5.0.0         # Optional, for interactive plots
requests>=2.25.0
```

### Optional Dependencies

```
jupyterlab>=3.0.0     # Alternative to notebook
ipywidgets>=7.6.0     # Interactive widgets
folium>=0.12.0        # Geospatial mapping
```

---

## 📊 Data Flow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────┐
│  Data Sources   │────▶│  Python Scripts  │────▶│  Analysis   │
└─────────────────┘     └──────────────────┘     └─────────────┘
        │
        ├── PySUS (Brazil)
        ├── WHO GHO (Global)
        ├── World Bank (Global)
        ├── ECDC (Europe)
        ├── PAHO (Americas)
        ├── Eurostat (EU)
        ├── OWID (Global)
        └── INS Colombia (Colombia)
```

---

## 🎯 Use Cases

### For Researchers
- **Epidemiological studies**: Track disease trends across regions
- **Health policy analysis**: Compare health system performance
- **Academic research**: Access standardized health data

### For Public Health Professionals
- **Surveillance**: Monitor disease outbreaks
- **Resource planning**: Analyze health workforce distribution
- **Policy evaluation**: Assess intervention effectiveness

### For Data Scientists
- **Training**: Learn to work with health data
- **Validation**: Cross-check data across sources
- **Modeling**: Build predictive models

---

## 🔧 Troubleshooting

### Common Issues

#### 1. PySUS Connection Error
```python
# Check internet connection
# DATASUS may be temporarily unavailable
# Try again later or use cached data
```

#### 2. WHO API Rate Limit
```python
# Add delays between requests
import time
time.sleep(1)  # Wait 1 second between API calls
```

#### 3. Missing Data
```python
# Check data availability for specific years/countries
# Some indicators may not be available for all locations
```

### Getting Help

- **PySUS**: https://pysus.readthedocs.io/
- **WHO GHO**: https://www.who.int/data/gho
- **World Bank**: https://data.worldbank.org/
- **ECDC**: https://www.ecdc.europa.eu/

---

## 📈 Output Files

Notebooks save processed data to `./output/` directory:

| File | Description | Source |
|------|-------------|--------|
| `dengue_rj_2023.csv` | Dengue cases in Rio de Janeiro | PySUS |
| `sim_sp_2022.csv` | Mortality data for São Paulo | PySUS |
| `who_malaria_data.csv` | Malaria incidence by country | WHO |
| `who_life_expectancy.csv` | Life expectancy trends | WHO |
| `wb_health_dashboard.csv` | Comprehensive health indicators | World Bank |
| `ecdc_covid_cases.csv` | COVID-19 European data | ECDC |
| `ecdc_influenza.csv` | Influenza surveillance | ECDC |
| `paho_vaccination.csv` | Vaccination coverage in Americas | PAHO |
| `eurostat_health_exp.csv` | EU healthcare expenditure | Eurostat |
| `owid_covid_global.csv` | Global COVID-19 data | OWID |
| `owid_vaccination.csv` | Global vaccination progress | OWID |
| `multi_source_comparison.csv` | Combined dataset | Multiple |
| `colombia_departments.csv` | Colombian administrative divisions | INS Colombia |
| `colombia_diseases.csv` | Colombia notifiable diseases | SIVIGILA |
| `colombia_event_groups.csv` | Colombia disease event groups | INS Colombia |
| `africa_countries.csv` | African Union member states | Africa CDC |
| `africa_regions.csv` | Africa CDC regional mapping | Africa CDC |
| `africa_priority_diseases.csv` | Africa CDC priority diseases | Africa CDC |

---

## 🤝 Contributing

Want to add a new notebook?

1. Create your notebook in `notebooks/` directory
2. Follow the existing naming convention: `XX_source_description.ipynb`
3. Include clear documentation and examples
4. Add to this README
5. Submit a pull request!

### Notebook Template

See [notebook_template.ipynb](notebooks/notebook_template.ipynb) for a starter template.

---

## 📄 License

These notebooks are provided under the same license as the main repository.

---

## 🙏 Acknowledgments

- **DATASUS** (Brazil) for making health data openly available
- **WHO** for the Global Health Observatory
- **World Bank** for open health data
- **ECDC** for European surveillance data
- **PAHO** for Pan American health statistics
- **Eurostat** for European Union health data
- **Our World in Data** for global health research and open data
- **INS Colombia** for Colombian public health surveillance data through SIVIGILA
- **Africa CDC** for African public health surveillance and outbreak data

---

## 📞 Contact

For questions or issues with these notebooks:
- Open an issue on GitHub
- Check the main repository documentation
- Contact the maintainers

---

**Last Updated:** March 2026  
**Maintained by:** Epidemiological Datasets Repository Team
