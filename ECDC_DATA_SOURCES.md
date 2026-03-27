# ECDC Data Sources Analysis

## Fontes identificadas na página da ECDC

### 1. EpiPulse (Portal Europeu de Vigilância)
- **URL:** https://www.ecdc.europa.eu/en/publications-data/epipulse
- **Descrição:** Portal integrado de vigilância de doenças infecciosas da UE/EEA
- **Dados:** Casos de doenças infecciosas, eventos de saúde pública
- **Formato:** Dashboard interativo, downloads disponíveis
- **Status:** ✅ Requer acesso após registro

### 2. ERVISS (European Respiratory Virus Surveillance Summary)
- **URL:** https://www.ecdc.europa.eu/en/publications-data/european-respiratory-virus-surveillance-summary-erviss
- **Descrição:** Resumo epidemiológico semanal integrado
- **Dados:** Influenza, RSV, SARS-CoV-2
- **Cobertura:** UE/EEA e Região Europeia da OMS
- **Atualização:** Semanal
- **Formato:** Dashboard interativo

### 3. RespiCast (European Respiratory Diseases Forecasting Hub)
- **URL:** https://www.ecdc.europa.eu/en/publications-data/european-respiratory-diseases-forecasting-hub-respicast
- **Descrição:** Hub de previsão de doenças respiratórias
- **Dados:** Modelos preditivos para influenza, COVID-19, RSV
- **Formato:** Forecasts e projeções

### 4. ECDC Atlas of Infectious Diseases
- **URL:** https://atlas.ecdc.europa.eu/
- **Descrição:** Atlas interativo de doenças infecciosas
- **Dados:** Dados históricos e atuais de 50+ doenças
- **Formato:** Mapas, gráficos, downloads CSV

### 5. ESAC-Net (Antimicrobial Consumption)
- **URL:** https://www.ecdc.europa.eu/en/publications-data/antimicrobial-consumption-dashboard
- **Descrição:** Dados de consumo antimicrobiano na Europa
- **Dados:** Consumo de antibióticos por país
- **Relevância:** Resistência antimicrobiana (AMR)

### 6. Eurostat Health Statistics
- **URL:** https://ec.europa.eu/eurostat/web/health
- **Descrição:** Estatísticas de saúde da UE
- **Dados:** Diversos indicadores de saúde pública
- **Formato:** API REST, downloads

### 7. ECDC Geoportal
- **URL:** Dados geoespaciais de saúde pública
- **Descrição:** Dados espaciais de doenças e vetores

## Comparação com Repositório Atual

### ✅ Já Implementados:
- HealthData.gov ✅
- Africa CDC ✅
- Colombia INS ✅
- PAHO ✅
- Eurostat ✅ (já existe)
- Our World in Data ✅
- RKI Germany ✅
- China CDC ✅
- India IDSP ✅
- WHO GHO/EMRO ✅
- UKHSA ✅
- Global Health ✅

### ❌ Faltantes (Prioridade para implementação):
1. **EpiPulse** - Portal principal ECDC
2. **ERVISS** - Dados respiratórios semanais
3. **ECDC Atlas** - Dados históricos completos
4. **RespiCast** - Previsões/modelos
5. **ESAC-Net** - Consumo antimicrobiano

## Issues para Criar

1. #XX - Add EpiPulse accessor (ECDC Surveillance Portal)
2. #XX - Add ERVISS accessor (Respiratory Virus Surveillance)
3. #XX - Add ECDC Atlas accessor (Infectious Diseases Atlas)
4. #XX - Add RespiCast accessor (Forecasting Hub)
5. #XX - Add ESAC-Net accessor (Antimicrobial Consumption)
