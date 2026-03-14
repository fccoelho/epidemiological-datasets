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
        └── ECDC (Europe)
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
| `multi_source_comparison.csv` | Combined dataset | Multiple |

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

---

## 📞 Contact

For questions or issues with these notebooks:
- Open an issue on GitHub
- Check the main repository documentation
- Contact the maintainers

---

**Last Updated:** 2024  
**Maintained by:** Epidemiological Datasets Repository Team
