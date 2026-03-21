# 📓 Notebooks de Exemplos

Esta pasta contém notebooks Jupyter demonstrando o uso do `epidemiological-datasets` para análise de dados epidemiológicos.

---

## 📁 Notebooks Disponíveis

### 🌍 EMRO Health Analysis
**Arquivo:** `emro_health_analysis.ipynb`

Demonstra análise de indicadores de saúde para a região **EMRO** (Eastern Mediterranean Regional Office) da OMS.

**Conteúdo:**
- Listagem dos 22 países da região EMRO
- Análise de Expectativa de Vida Saudável (HALE)
- Tendências temporais regionais
- Dados de malária na região
- Comparação entre países
- Visualizações interativas

**Indicadores utilizados:**
- `WHOSIS_000002` - Healthy Life Expectancy (HALE)
- `MALARIA_EST_INCIDENCE` - Incidência estimada de malária
- `MDG_0000000001` - Taxa de mortalidade infantil

---

## 🚀 Como Usar

### Pré-requisitos

```bash
# Instalar o pacote
pip install -e .

# Ou se estiver no diretório do projeto
pip install -e /caminho/para/epidemiological-datasets
```

### Executar o Notebook

```bash
# Navegar até a pasta
cd notebooks/examples

# Iniciar Jupyter
jupyter notebook

# Ou JupyterLab
jupyter lab
```

---

## 📝 Estrutura dos Notebooks

Cada notebook segue uma estrutura padrão:

1. **Configuração** - Imports e inicialização
2. **Introdução** - Contexto sobre a região/fonte de dados
3. **Exploração** - Análise exploratória dos dados
4. **Visualização** - Gráficos e figuras
5. **Conclusões** - Resumo dos achados

---

## 💡 Dicas

- Execute as células em ordem (de cima para baixo)
- Algumas células podem demorar devido a chamadas de API
- Dados são armazenados em cache quando possível
- Modifique os parâmetros para explorar diferentes anos/indicadores

---

## 🔗 Recursos Adicionais

- [WHO GHO API Documentation](https://www.who.int/data/gho)
- [EMRO Countries](https://www.emro.who.int/countries.html)
- [Package Documentation](../docs/)

---

*Última atualização: 2026-03-21*
