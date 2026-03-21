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

### 11. [11_Global_Health_Linelist_Data.ipynb](notebooks/11_Global_Health_Linelist_Data.ipynb)
**Global.health Line-list Data**

Access standardized, curated line-list data for pandemics and epidemics including COVID-19 and Monkeypox with detailed case metadata.

**Topics covered:**
- COVID-19 line-list data with case details
- Monkeypox outbreak data
- Case demographics (age, sex)
- Temporal analysis of case data
- Geocoded case locations
- Outbreak comparison across diseases
- Detailed case metadata (outcomes, travel history)

**Data Sources:**
- Global.health: https://global.health/
- GitHub: https://github.com/globaldothealth/
- License: CC BY 4.0

---

### 12. [12_UKHSA_Surveillance_Data.ipynb](notebooks/12_UKHSA_Surveillance_Data.ipynb)
**UK Health Security Agency (UKHSA) Surveillance Data**

Access UK public health surveillance data including infectious diseases, immunization coverage, influenza, and antimicrobial resistance.

**Topics covered:**
- Infectious disease surveillance (Measles, TB, etc.)
- Vaccination coverage (MMR, DTP, HPV)
- Seasonal influenza surveillance
- Antimicrobial resistance (AMR) data
- COVID-19 metrics for UK
- Regional analysis (England, Wales, Scotland, Northern Ireland)
- WHO vaccination targets comparison

**Data Sources:**
- UKHSA: https://www.gov.uk/government/collections/health-protection-data
- License: Open Government Licence (OGL)

---

### 13. [13_HealthData_Gov_US_Health_System.ipynb](notebooks/13_HealthData_Gov_US_Health_System.ipynb)
**HealthData.gov - US Health System Data**

Access US health system data including hospital capacity, COVID-19 metrics, vaccination data, and testing data from HHS.

**Topics covered:**
- Hospital capacity by state
- COVID-19 patient impact and hospitalizations
- ICU bed utilization
- Vaccination progress by state
- COVID-19 testing data
- State-by-state comparisons
- Current hospital statistics
- Nursing home COVID-19 data

**Data Sources:**
- HealthData.gov: https://healthdata.gov/
- HHS Protect ecosystem
- API: Socrata Open Data API (SODA)
- License: Public Domain (US Government)

---

### 14. [14_RKI_Germany_Surveillance_Data.ipynb](notebooks/14_RKI_Germany_Surveillance_Data.ipynb)
**RKI Germany Surveillance Data**

Access German infectious disease surveillance data from the Robert Koch Institute (RKI), including COVID-19 nowcasting, hospitalizations, vaccinations, and 25+ notifiable diseases.

**Topics covered:**
- COVID-19 R value (reproduction number) and nowcasting
- COVID-19 hospitalizations by state (Bundesland)
- Vaccination coverage data
- Notifiable infectious diseases (Meldepflichtige Krankheiten)
- Influenza weekly surveillance
- State-level analysis across 16 federal states
- Epidemiological reporting

**Data Sources:**
- RKI GitHub: https://github.com/robert-koch-institut
- COVID-19 Dashboard: https://corona.rki.de/
- SurvStat: https://survstat.rki.de/
- License: CC-BY 4.0 / dl-de/by-2-0

---

### 15. [15_China_CDC_Weekly_Surveillance.ipynb](notebooks/15_China_CDC_Weekly_Surveillance.ipynb)
**China CDC Weekly Surveillance Data**

Access disease surveillance data from China CDC Weekly, covering 38 notifiable infectious diseases across 31 Chinese provinces and municipalities.

**Topics covered:**
- 38 notifiable infectious diseases (Class A, B, C)
- Influenza surveillance (ILI%)
- Weekly epidemiological reports
- Province-level analysis (31 provinces/municipalities)
- Disease classification system
- COVID-19 weekly updates
- Vaccination coverage data

**Data Sources:**
- China CDC Weekly: http://weekly.chinacdc.cn/
- CNIC (Chinese CDC): http://www.chinacdc.cn/cnic/
- License: Public health surveillance reports

---

### 16. [16_India_IDSP_Surveillance_Data.ipynb](notebooks/16_India_IDSP_Surveillance_Data.ipynb)
**India IDSP (Integrated Disease Surveillance Programme) Data**

Access disease surveillance data from India's IDSP, covering outbreak reports, vector-borne diseases, and priority diseases across 36 states and union territories.

**Topics covered:**
- Weekly outbreak surveillance reports
- Priority disease tracking (30+ diseases)
- S/P/L syndrome classification (Form S, P, L, U)
- Vector-borne diseases (Malaria, Dengue, Chikungunya, JE, Kala-azar)
- State/UT-level analysis (36 states and union territories)
- Seasonal disease patterns
- NVBDCP integration (National Vector Borne Disease Control Programme)

**Data Sources:**
- IDSP Portal: https://idsp.nic.in/
- NVBDCP: https://nvbdcp.gov.in/
- NACO: https://naco.gov.in/
- License: Government of India Open Data

---

### 17. [17_EMRO_Health_Indicators_Analysis.ipynb](notebooks/17_EMRO_Health_Indicators_Analysis.ipynb)
**WHO EMRO (Eastern Mediterranean Region) Health Indicators**

Analyze health indicators for the WHO Eastern Mediterranean Region covering 22 countries across the Middle East, North Africa, and Central Asia.

**Topics covered:**
- Healthy Life Expectancy (HALE) trends and comparisons
- Under-5 mortality and maternal mortality analysis
- Malaria burden in endemic countries (Afghanistan, Pakistan, Somalia, Sudan, Yemen)
- Multi-indicator country comparisons
- Sub-regional analysis (Middle East, Arabian Peninsula, North Africa, Central Asia)
- Health system disparities and conflict impacts
- Regional health dashboard

**Data Sources:**
- WHO Global Health Observatory (GHO): https://www.who.int/data/gho
- EMRO-specific indicators via ghoclient
- 22 EMRO member states data
- License: WHO Open Data

**Geographic Coverage:**
- Middle East (5): Jordan, Lebanon, Syria, Iraq, Iran
- Arabian Peninsula (7): Saudi Arabia, UAE, Qatar, Kuwait, Bahrain, Oman, Yemen
- North Africa (8): Egypt, Libya, Tunisia, Algeria, Morocco, Sudan, Somalia, Djibouti
- Central/South Asia (3): Afghanistan, Pakistan, Palestine

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
        ├── INS Colombia (Colombia)
        ├── Africa CDC (Africa)
        ├── Global.health (Global line-list)
        ├── UKHSA (United Kingdom)
        ├── HealthData.gov (United States)
        ├── RKI Germany (Germany)
        ├── China CDC (China)
        ├── India IDSP (India)
        └── WHO EMRO (Eastern Mediterranean)
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
| `global_health_datasets.csv` | Global.health available datasets | Global.health |
| `global_health_covid_linelist.csv` | COVID-19 line-list data | Global.health |
| `ukhsa_indicators.csv` | UKHSA surveillance indicators | UKHSA |
| `ukhsa_vaccination_coverage.csv` | UK vaccination coverage | UKHSA |
| `healthdata_datasets.csv` | HealthData.gov dataset catalog | HealthData.gov |
| `us_hospital_capacity.csv` | US hospital capacity by state | HealthData.gov |
| `us_covid_metrics.csv` | US COVID-19 hospital metrics | HealthData.gov |
| `germany_states.csv` | German federal states (Bundesländer) | RKI |
| `germany_notifiable_diseases.csv` | Germany notifiable diseases list | RKI |
| `covid_nowcast.csv` | COVID-19 R value and nowcasting | RKI |
| `covid_hospitalizations.csv` | COVID-19 hospitalizations by state | RKI |
| `china_provinces.csv` | Chinese provinces and municipalities | China CDC |
| `china_notifiable_diseases.csv` | China 38 notifiable diseases | China CDC |
| `weekly_reports.csv` | China CDC Weekly reports metadata | China CDC |
| `india_states.csv` | Indian states and union territories | India IDSP |
| `india_priority_diseases.csv` | India IDSP priority diseases | IDSP |
| `emro_countries.csv` | EMRO member states list | WHO |
| `emro_hale_data.csv` | Healthy Life Expectancy for EMRO | WHO |
| `emro_malaria_data.csv` | Malaria burden data for EMRO | WHO |

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
- **Global.health** for standardized pandemic line-list data
- **UK Health Security Agency** for UK public health surveillance data
- **HHS/HealthData.gov** for US health system open data
- **Robert Koch Institute (RKI)** for German disease surveillance data
- **China CDC** for Chinese disease surveillance and weekly reports
- **India IDSP/NVBDCP** for Indian disease surveillance data
- **WHO EMRO** for Eastern Mediterranean health indicators

---

## 📞 Contact

For questions or issues with these notebooks:
- Open an issue on GitHub
- Check the main repository documentation
- Contact the maintainers

---

**Last Updated:** March 2026 (Added RKI Germany, China CDC, India IDSP, and WHO EMRO notebooks)  
**Maintained by:** Epidemiological Datasets Repository Team
