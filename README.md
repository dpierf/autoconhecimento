# 🔮 Mapa de Autoconhecimento

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://autoconhecimento.streamlit.app)

Aplicativo web para geração de mapas integrados de autoconhecimento, combinando sistemas simbólicos de múltiplas tradições a partir dos dados de nascimento de uma pessoa.

---

## ✨ Acesse o app

**[▶ Abrir no Streamlit →](https://autoconhecimento.streamlit.app)**

---

## 📖 O que é

O app recebe nome, data, hora e local de nascimento e gera um mapa completo integrando:

| Sistema | O que calcula |
|---|---|
| 🪐 Astrologia ocidental | Planetas, ângulos, casas, aspectos, sizígia, Padrão de Jones, Partes Árabes, Stellium |
| 🌙 Astrologia védica | Nakshatra (mansão lunar) |
| 🔢 Numerologia | Número da Vida, Expressão, Alma, Personalidade, Atitude, Pínáculos, Desafios |
| 🃏 Tarot | Arcanos da data, do nome, da alma e do ano |
| 🀄 Zodíaco Chinês | Animal, elemento, polaridade, Tronco Celeste, Ramo Terrestre |
| 🎴 Ba Zi (Quatro Pilares) | Pilares do ano, mês, dia e hora |
| ☯️ I Ching natal | Hexagrama e linhas mutantes pelo método de Enos Long |
| ᚠ Runas nórdicas | Runa principal, secundária, do destino e oculta |
| 💫 Biorritmos | Ciclos físico, emocional, intelectual, intuitivo, estético, de consciência e espiritual |
| 🌅 Energia do dia | Síntese numerológica, astrológica, rúnica e de Ba Zi para o dia atual |

---

## 🛠️ Tecnologias utilizadas

- [Python 3.11](https://www.python.org/)
- [Streamlit](https://streamlit.io/) — interface web
- [PySwissEph](https://github.com/astrorigin/pyswisseph) — cálculos astronômicos (Swiss Ephemeris)
- [Astral](https://astral.readthedocs.io/) — cálculo de amanhecer/pôr do sol
- [TimezoneFinder](https://timezonefinder.readthedocs.io/) — resolução de fuso horário por coordenadas
- [LunarDate](https://pypi.org/project/lunardate/) — calendário lunar chinês
- [SimpleMaps World Cities](https://simplemaps.com/data/world-cities) — base de cidades e coordenadas geográficas (geocodificação offline)
- [pandas](https://pandas.pydata.org/) — leitura e filtragem da base de cidades

---

## 🚀 Como rodar localmente

### Pré-requisitos

- Python 3.11+
- Git

### Instalação e Execução

```bash
# 1. Clone o repositório
git clone https://github.com/dpierf/autoconhecimento.git
cd autoconhecimento

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Execute a aplicação
streamlit run app.py
```

Acesse `http://localhost:8501` no navegador.

---

## 📁 Estrutura do projeto

```
.
├── app.py              # Aplicativo principal (cálculos + interface)
├── requirements.txt    # Dependências Python
├── ephe/               # Efemérides astronômicas (Swiss Ephemeris)
│   ├── seas_18.se1
│   ├── semo_18.se1
│   └── sepl_18.se1
└── worldcities.csv     # Base de cidades SimpleMaps (não versionado)
```

---

## ⚠️ Aviso

Este aplicativo é uma ferramenta de autoconhecimento e reflexão pessoal.  
Os resultados não têm caráter preditivo, diagnóstico ou terapêutico.

---

## 📜 Licença e uso

© Pier Francesco De Maria, 2026. Todos os direitos reservados.

Este repositório é público para fins de transparência e portfólio. O código **não pode ser copiado, modificado, redistribuído ou utilizado** em outros projetos sem autorização expressa do autor.

Contato: dpierf@gmail.com

---

## 🙏 Créditos

**Concepção, curadoria e decisões de produto:** Pier Francesco De Maria

**Implementação técnica:** desenvolvida com assistência de [Claude](https://claude.ai) (Anthropic), modelo de linguagem generativo utilizado para geração e refinamento de código ao longo de todo o processo.
Versão utilizada: Claude Sonnet 4.6

**Dados astronômicos:** [Swiss Ephemeris](https://www.astro.com/swisseph/) — Astrodienst AG  
**Base geográfica:** [SimpleMaps World Cities Database](https://simplemaps.com/data/world-cities)
