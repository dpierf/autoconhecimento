# ── app.py ────────────────────────────────────────────────────────────────────
# Mapa de Autoconhecimento — versão Streamlit
# Deploy: Streamlit Community Cloud
# Geocodificação: arquivo worldcities.csv
# Efemérides: arquivos .se1 na pasta /ephe
# Código desenvolvido em Python utilizando GenIA Claude
# ─────────────────────────────────────────────────────────────────────────────

# ── Imports ───────────────────────────────────────────────────────────────────

import math
import re
import urllib.request
from collections import Counter, namedtuple
from dataclasses import dataclass
from datetime import datetime as pydt, date as hoje
from pathlib import Path

import pandas as pd
import pytz
import streamlit as st
import streamlit.components.v1 as components
import swisseph as swe
from astral import LocationInfo
from astral.sun import sun
from lunardate import LunarDate
from timezonefinder import TimezoneFinder

# ── Página ────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Mapa de Autoconhecimento",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ── Efemérides (baixa uma vez, fica em cache pelo tempo de vida do processo) ──

def _init_ephe():
    base_dir = Path(__file__).resolve().parent
    ephe_dir = base_dir / "ephe"
    swe.set_ephe_path(str(ephe_dir))

_init_ephe()

# ── Cidades (SimpleMaps worldcities.csv) ──────────────────────────────────────

@st.cache_data(show_spinner=False)
def _load_cities() -> pd.DataFrame:
    """Lê o worldcities.csv uma única vez e mantém em memória."""
    path = Path("worldcities.csv")
    if not path.exists():
        st.error(
            "Arquivo worldcities.csv não encontrado na raiz do repositório. "
            "Baixe em https://simplemaps.com/data/world-cities e adicione ao repo."
        )
        st.stop()
    return pd.read_csv(
        path,
        usecols=["city_ascii", "country", "lat", "lng"],
        dtype={"city_ascii": str, "country": str, "lat": float, "lng": float},
    )

# ── Auxiliares de país / cidade ───────────────────────────────────────────────
 
@st.cache_data(show_spinner=False)
def _get_countries() -> list[str]:
    """Lista ordenada de países únicos do worldcities.csv."""
    df = _load_cities()
    return sorted(df["country"].dropna().unique().tolist())
 
 
@st.cache_data(show_spinner=False)
def _get_cities(country: str) -> list[str]:
    """Lista ordenada de cidades de um país (campo city_ascii)."""
    df = _load_cities()
    return sorted(
        df.loc[df["country"] == country, "city_ascii"]
        .dropna()
        .unique()
        .tolist()
    )



# ── Estruturas de dados ───────────────────────────────────────────────────────

GeoPos = namedtuple("GeoPos", ["lat", "lon"])


@dataclass
class Planeta:
    id: str
    lon: float
    signlon: float
    sign: str
    speed: float
    house: int = 0
    is_angle: bool = False

    def movement(self):
        if self.is_angle:
            return ""
        if abs(self.speed) < 0.0003:
            return "Stationary"
        return "Direct" if self.speed > 0 else "Retrograde"


# ── Mapeamentos ───────────────────────────────────────────────────────────────

planetas = {
    "Sun": "Sol",          "Asc": "Ascendente",     "Moon": "Lua",
    "Mercury": "Mercúrio", "Venus": "Vênus",         "Mars": "Marte",
    "Jupiter": "Júpiter",  "Saturn": "Saturno",      "Uranus": "Urano",
    "Neptune": "Netuno",   "Pluto": "Plutão",         "Chiron": "Quíron",
    "North node": "Nodo N","South node": "Nodo S",
    "Desc": "Descendente", "Mc": "Meio do Céu",       "Ic": "Fundo do Céu",
    "Lilith": "Lilith",    "Ceres": "Ceres",           "Pallas": "Pallas",
    "Juno": "Juno",        "Vesta": "Vesta",
    "Vertex": "Vértex",    "Antivertex": "Anti-Vértex",
}

signos = {
    "Aries": "Áries",        "Taurus": "Touro",      "Gemini": "Gêmeos",
    "Cancer": "Câncer",      "Leo": "Leão",          "Virgo": "Virgem",
    "Libra": "Libra",        "Scorpio": "Escorpião", "Sagittarius": "Sagitário",
    "Capricorn": "Capricórnio","Aquarius": "Aquário","Pisces": "Peixes",
}

SIGNOS_EN = list(signos.keys())
SIGNOS_PT = list(signos.values())

elementos = {
    "Áries": "Fogo",   "Leão": "Fogo",         "Sagitário": "Fogo",
    "Touro": "Terra",  "Virgem": "Terra",       "Capricórnio": "Terra",
    "Gêmeos": "Ar",    "Libra": "Ar",           "Aquário": "Ar",
    "Câncer": "Água",  "Escorpião": "Água",     "Peixes": "Água",
}

modalidades = {
    "Áries": "Cardinal",  "Câncer": "Cardinal",   "Libra": "Cardinal",    "Capricórnio": "Cardinal",
    "Touro": "Fixo",      "Leão": "Fixo",         "Escorpião": "Fixo",    "Aquário": "Fixo",
    "Gêmeos": "Mutável",  "Virgem": "Mutável",    "Sagitário": "Mutável", "Peixes": "Mutável",
}

temperamentos = {"Fogo": "Colérico", "Ar": "Sanguíneo", "Terra": "Melancólico", "Água": "Fleumático"}

graus_aspectos = {0: 1, 180: 2, 90: 3, 120: 4, 60: 6, 45: 8, 135: 8, 150: 12}
sigmas         = {0: 6.0, 180: 5.0, 90: 4.5, 120: 4.5, 60: 3.5, 45: 3.0, 135: 2.5, 150: 2.5}
alpha          = 0.9

NOMES_ASPECTOS = {
    0:   ("Conjunção",        "harmonioso"),
    180: ("Oposição",         "tenso"),
    90:  ("Quadratura",       "tenso"),
    120: ("Trígono",          "harmonioso"),
    60:  ("Sextil",           "harmonioso"),
    45:  ("Semi-Quadratura",  "tenso"),
    135: ("Sesquiquadratura", "tenso"),
    150: ("Inconjunção",      "neutro"),
}

CATEGORIAS_PLANETAS = {
    "Sol": "pessoal",   "Lua": "pessoal",     "Mercúrio": "pessoal",
    "Vênus": "pessoal", "Marte": "pessoal",
    "Júpiter": "projetos", "Saturno": "projetos",
    "Urano": "geracional", "Netuno": "geracional", "Plutão": "geracional",
}

letras = {
    **dict.fromkeys(list("AJS"), 1), **dict.fromkeys(list("BKT"), 2), **dict.fromkeys(list("CLU"), 3),
    **dict.fromkeys(list("DMV"), 4), **dict.fromkeys(list("ENW"), 5), **dict.fromkeys(list("FOX"), 6),
    **dict.fromkeys(list("GPY"), 7), **dict.fromkeys(list("HQZ"), 8), **dict.fromkeys(list("IR"),  9),
}

VOGAIS = set("AEIOU")

arcanos = {
    0:  "O Bobo",           1:  "O Mago",            2:  "A Sacerdotisa",
    3:  "A Imperatriz",     4:  "O Imperador",        5:  "O Hierofante",
    6:  "Os Amantes",       7:  "O Carro",            8:  "A Força",
    9:  "O Eremita",        10: "A Roda da Fortuna",  11: "A Justiça",
    12: "O Enforcado",      13: "A Morte",            14: "A Temperança",
    15: "O Diabo",          16: "A Torre",            17: "A Estrela",
    18: "A Lua",            19: "O Sol",              20: "O Julgamento",
    21: "O Mundo",
}

_ROMAN    = ["0","I","II","III","IV","V","VI","VII","VIII","IX","X","XI","XII","XIII","XIV","XV","XVI","XVII","XVIII","XIX","XX","XXI"]
_ARCANO_SIMB = {
    0:"✦", 1:"∞", 2:"☽", 3:"♀", 4:"♂", 5:"✝", 6:"♡", 7:"⊕",
    8:"∞", 9:"✦", 10:"☸", 11:"⚖", 12:"⊥", 13:"✗", 14:"≈", 15:"★",
    16:"✦", 17:"★", 18:"☽", 19:"☀", 20:"☆", 21:"◎",
}

_RUNA_UNICODE = {
    "Fehu":"ᚠ","Uruz":"ᚢ","Thurisaz":"ᚦ","Ansuz":"ᚨ",
    "Raidho":"ᚱ","Kenaz":"ᚲ","Gebo":"ᚷ","Wunjo":"ᚹ",
    "Hagalaz":"ᚺ","Nauthiz":"ᚾ","Isa":"ᛁ","Jera":"ᛃ",
    "Eihwaz":"ᛇ","Perthro":"ᛈ","Algiz":"ᛉ","Sowilo":"ᛊ",
    "Tiwaz":"ᛏ","Berkana":"ᛒ","Ehwaz":"ᛖ","Mannaz":"ᛗ",
    "Laguz":"ᛚ","Ingwaz":"ᛜ","Othala":"ᛟ","Dagaz":"ᛞ",
}

runas_dias = [
    ("Fehu",(6,29),(7,14)),    ("Uruz",(7,14),(7,29)),
    ("Thurisaz",(7,29),(8,13)),("Ansuz",(8,13),(8,29)),
    ("Raidho",(8,29),(9,13)),  ("Kenaz",(9,13),(9,28)),
    ("Gebo",(9,28),(10,13)),   ("Wunjo",(10,13),(10,28)),
    ("Hagalaz",(10,28),(11,13)),("Nauthiz",(11,13),(11,28)),
    ("Isa",(11,28),(12,13)),   ("Jera",(12,13),(12,28)),
    ("Eihwaz",(12,28),(1,13)), ("Perthro",(1,13),(1,28)),
    ("Algiz",(1,28),(2,13)),   ("Sowilo",(2,13),(2,27)),
    ("Tiwaz",(2,27),(3,14)),   ("Berkana",(3,14),(3,30)),
    ("Ehwaz",(3,30),(4,14)),   ("Mannaz",(4,14),(4,29)),
    ("Laguz",(4,29),(5,14)),   ("Ingwaz",(5,14),(5,29)),
    ("Othala",(5,29),(6,14)),  ("Dagaz",(6,14),(6,29)),
]

runas_hora = [
    "Jera","Eihwaz","Perthro","Algiz","Sowilo","Tiwaz","Berkana","Ehwaz",
    "Mannaz","Laguz","Ingwaz","Dagaz","Othala","Fehu","Uruz","Thurisaz",
    "Ansuz","Raidho","Kenaz","Gebo","Wunjo","Hagalaz","Nauthiz","Isa",
]

RUNAS_LISTA = [r[0] for r in runas_dias]

CORPOS_SWE = [
    ("Sun",     swe.SUN),     ("Moon",   swe.MOON),    ("Mercury", swe.MERCURY),
    ("Venus",   swe.VENUS),   ("Mars",   swe.MARS),    ("Jupiter", swe.JUPITER),
    ("Saturn",  swe.SATURN),  ("Uranus", swe.URANUS),  ("Neptune", swe.NEPTUNE),
    ("Pluto",   swe.PLUTO),   ("Chiron", swe.CHIRON),
    ("Lilith",  swe.MEAN_APOG),("Ceres", swe.CERES),   ("Pallas",  swe.PALLAS),
    ("Juno",    swe.JUNO),    ("Vesta",  swe.VESTA),   ("North node", swe.TRUE_NODE),
]

PLANETAS_ASSIN = {
    "Sol":     swe.SUN,   "Lua":   swe.MOON,    "Mercúrio": swe.MERCURY,
    "Vênus":   swe.VENUS, "Marte": swe.MARS,    "Júpiter":  swe.JUPITER,
    "Saturno": swe.SATURN,"Urano": swe.URANUS,  "Netuno":   swe.NEPTUNE,  "Plutão": swe.PLUTO,
}

DIGNIDADES = {
    "Sol":      {"domicílio":["Leão"],                 "exaltação":["Áries"],       "detrimento":["Aquário"],             "queda":["Libra"]},
    "Lua":      {"domicílio":["Câncer"],                "exaltação":["Touro"],       "detrimento":["Capricórnio"],         "queda":["Escorpião"]},
    "Mercúrio": {"domicílio":["Gêmeos","Virgem"],       "exaltação":["Virgem"],      "detrimento":["Sagitário","Peixes"],  "queda":["Peixes"]},
    "Vênus":    {"domicílio":["Touro","Libra"],         "exaltação":["Peixes"],      "detrimento":["Áries","Escorpião"],   "queda":["Virgem"]},
    "Marte":    {"domicílio":["Áries","Escorpião"],     "exaltação":["Capricórnio"], "detrimento":["Touro","Libra"],       "queda":["Câncer"]},
    "Júpiter":  {"domicílio":["Sagitário","Peixes"],    "exaltação":["Câncer"],      "detrimento":["Gêmeos","Virgem"],     "queda":["Capricórnio"]},
    "Saturno":  {"domicílio":["Capricórnio","Aquário"], "exaltação":["Libra"],       "detrimento":["Câncer","Leão"],       "queda":["Áries"]},
    "Urano":    {"domicílio":["Aquário"],  "exaltação":[], "detrimento":["Leão"],   "queda":[]},
    "Netuno":   {"domicílio":["Peixes"],   "exaltação":[], "detrimento":["Virgem"], "queda":[]},
    "Plutão":   {"domicílio":["Escorpião"],"exaltação":[], "detrimento":["Touro"],  "queda":[]},
}

_BZ_TRONCOS  = ["Jia","Yi","Bing","Ding","Wu","Ji","Geng","Xin","Ren","Gui"]
_BZ_RAMOS    = ["Zi","Chou","Yin","Mao","Chen","Si","Wu","Wei","Shen","You","Xu","Hai"]
_BZ_ANIMAIS  = ["Rato","Boi","Tigre","Coelho","Dragão","Serpente","Cavalo","Cabra","Macaco","Galo","Cão","Porco"]
_BZ_ELEM_T   = ["Madeira","Madeira","Fogo","Fogo","Terra","Terra","Metal","Metal","Água","Água"]
_BZ_POL_T    = ["Yang","Yin","Yang","Yin","Yang","Yin","Yang","Yin","Yang","Yin"]
_BZ_MES_STEM_BASE = [2, 4, 6, 8, 0, 2, 4, 6, 8, 0]
_BZ_DAY_OFFSET    = 11

_JONES_DESC = {
    "Bundle":     "Feixe: concentração intensa numa área; especialista com visão de mundo focada",
    "Bowl":       "Tigela: missão clara; busca no mundo externo o que lhe falta",
    "Bucket":     "Balde: planeta-alça define o ponto focal de toda a energia do mapa",
    "Locomotive": "Locomotiva: grande impulso e autodirecionamento; orientado a metas",
    "Seesaw":     "Gangorra: polaridades internas; habilidade de ver todos os lados",
    "Splash":     "Splash: interesses amplos e diversificados; dificuldade de foco único",
    "Splay":      "Splay: individualista e não convencional; trajetória única e irregular",
}

_NAKSHATRAS = [
    ("Ashwini",          "Ketu",     "Velocidade e cura; início de jornadas e impulso vital"),
    ("Bharani",          "Vênus",    "Transformação e criação; carrega o peso da vida e da morte"),
    ("Krittika",         "Sol",      "Purificação e determinação; fogo que refina e corta"),
    ("Rohini",           "Lua",      "Fertilidade e abundância; crescimento, beleza e sensualidade"),
    ("Mrigashira",       "Marte",    "Busca e curiosidade; mente inquieta e exploradora"),
    ("Ardra",            "Rahu",     "Tempestade e renovação; transformação que emerge da dor"),
    ("Punarvasu",        "Júpiter",  "Retorno à luz; renovação e restauração após a adversidade"),
    ("Pushya",           "Saturno",  "Nutrição e proteção; a mais auspiciosa das mansões lunares"),
    ("Ashlesha",         "Mercúrio", "Sabedoria serpentina; intuição profunda e complexidade interior"),
    ("Magha",            "Ketu",     "Poder ancestral; honra, tradição e realeza espiritual"),
    ("Purva Phalguni",   "Vênus",    "Prazer e descanso criativo; alegria, união e expressão"),
    ("Uttara Phalguni",  "Sol",      "Prosperidade e serviço; generosidade, contratos e compromisso"),
    ("Hasta",            "Lua",      "Habilidade e maestria; cura pelas mãos e artesanato preciso"),
    ("Chitra",           "Marte",    "Brilho e criação; arquitetura, beleza e ornamento"),
    ("Swati",            "Rahu",     "Independência e flexibilidade; como a brisa que dobra sem quebrar"),
    ("Vishakha",         "Júpiter",  "Propósito e foco; perseverança concentrada em direção à meta"),
    ("Anuradha",         "Saturno",  "Devoção e amizade; lealdade que supera todos os obstáculos"),
    ("Jyeshtha",         "Mercúrio", "Proteção e senioridade; liderança e responsabilidade madura"),
    ("Mula",             "Ketu",     "Raízes e dissolução; descida ao essencial e ao oculto"),
    ("Purva Ashadha",    "Vênus",    "Invencibilidade e purificação; força renovadora das águas"),
    ("Uttara Ashadha",   "Sol",      "Vitória final e conquistas duradouras; ética como pilar"),
    ("Shravana",         "Lua",      "Escuta e aprendizado; conexão com o sagrado pelo silêncio"),
    ("Dhanishtha",       "Marte",    "Abundância e ritmo; prosperidade, música e dinamismo"),
    ("Shatabhisha",      "Rahu",     "Cura oculta e solidão; mistério, medicina e introspecção"),
    ("Purva Bhadrapada", "Júpiter",  "Intensidade espiritual; transformação profunda pelo fogo interior"),
    ("Uttara Bhadrapada","Saturno",  "Profundidade e sabedoria; estabilidade das águas profundas"),
    ("Revati",           "Mercúrio", "Fim da jornada; nutrição, compaixão e transcendência"),
]

_IC_KW    = ["Qian","Dui","Li","Zhen","Xun","Kan","Gen","Kun"]
_IC_IDX   = {"Qian":0,"Zhen":1,"Kan":2,"Gen":3,"Kun":4,"Xun":5,"Li":6,"Dui":7}
_IC_LINHAS = {"Qian":(1,1,1),"Zhen":(1,0,0),"Kan":(0,1,0),"Gen":(0,0,1),
              "Kun":(0,0,0),"Xun":(0,1,1),"Li":(1,0,1),"Dui":(1,1,0)}
_IC_INFO  = {"Qian":("☰","Céu","Criativo"),"Zhen":("☳","Trovão","Movimento"),
             "Kan":("☵","Água","Abissal"),"Gen":("☶","Montanha","Imobilidade"),
             "Kun":("☷","Terra","Receptivo"),"Xun":("☴","Vento","Suave"),
             "Li":("☲","Fogo","Aderente"),"Dui":("☱","Lago","Alegria")}
_IC_PERIODOS = [((1,1),(2,15),"Qian"),((2,16),(4,1),"Kan"),((4,2),(5,17),"Gen"),((5,18),(7,2),"Zhen"),
                ((7,3),(8,16),"Xun"),((8,17),(9,30),"Li"),((10,1),(11,15),"Kun"),((11,16),(12,31),"Dui")]
_IC_HEX = [
    [1,34,5,26,11,9,14,43],[25,51,3,27,24,42,21,17],[6,40,29,4,7,59,64,47],[33,62,39,52,15,53,56,31],
    [12,16,8,23,2,20,35,45],[44,32,48,18,46,57,50,28],[13,55,63,22,36,37,30,49],[10,54,60,41,19,61,38,58],
]
_IC_NOMES = {
    1:"O Criativo",2:"O Receptivo",3:"A Dificuldade Inicial",4:"A Inexperiência",5:"A Espera",6:"O Conflito",
    7:"O Exército",8:"A União",9:"O Poder do Pequeno",10:"O Porte",11:"A Paz",12:"A Estagnação",
    13:"A Comunidade",14:"A Grande Possessão",15:"A Modéstia",16:"O Entusiasmo",17:"O Seguimento",
    18:"A Corrupção",19:"A Aproximação",20:"A Contemplação",21:"A Mordida Tajante",22:"A Elegância",
    23:"A Desintegração",24:"O Retorno",25:"A Inocência",26:"A Grande Doma",27:"As Comissuras",
    28:"O Grande Excesso",29:"O Abismo",30:"O Fogo",31:"A Influência",32:"A Duração",33:"A Retirada",
    34:"O Grande Poder",35:"O Progresso",36:"O Obscurecimento",37:"A Família",38:"O Antagonismo",
    39:"O Impedimento",40:"A Libertação",41:"A Diminuição",42:"O Aumento",43:"A Decisão",44:"O Encontro",
    45:"A Reunião",46:"A Ascensão",47:"A Opressão",48:"O Poço",49:"A Revolução",50:"O Caldeirão",
    51:"O Trovão",52:"A Montanha",53:"O Progresso Gradual",54:"A Donzela que se Casa",55:"A Abundância",
    56:"O Viajante",57:"O Suave",58:"A Alegria",59:"A Dispersão",60:"A Limitação",61:"A Verdade Interior",
    62:"O Pequeno Excesso",63:"Depois da Conclusão",64:"Antes da Conclusão",
}


# ── Funções de cálculo ────────────────────────────────────────────────────────

def _fmt_coord(value, pos, neg):
    return f"{abs(value):.4f}° {pos if value >= 0 else neg}"


def latlong(cidade: str, pais: str):
    """
    Busca lat/lon no worldcities.csv (SimpleMaps) e resolve timezone via
    TimezoneFinder. Não faz chamadas HTTP em runtime.
    """
    df = _load_cities()

    cidade_n = cidade.strip().lower()
    pais_n   = pais.strip().lower()

    # 1) Correspondência exata em cidade + país
    mask = (df["city_ascii"].str.lower() == cidade_n) & (df["country"].str.lower() == pais_n)
    match = df[mask]

    # 2) Fallback: começa com o nome da cidade, mesmo país
    if match.empty:
        mask2 = (
            df["city_ascii"].str.lower().str.startswith(cidade_n)
            & (df["country"].str.lower() == pais_n)
        )
        match = df[mask2]

    # 3) Fallback: só a cidade (qualquer país)
    if match.empty:
        match = df[df["city_ascii"].str.lower() == cidade_n]

    if match.empty:
        raise ValueError(
            f"Cidade '{cidade}' não encontrada no worldcities.csv. "
            "Verifique o nome em inglês conforme SimpleMaps."
        )

    row = match.iloc[0]
    lat, lon = float(row["lat"]), float(row["lng"])
    coords = GeoPos(lat, lon)
    zona = TimezoneFinder().timezone_at(lat=lat, lng=lon)
    if zona is None:
        raise ValueError("Timezone não encontrado para as coordenadas obtidas.")

    return None, coords, pytz.timezone(zona), zona, _fmt_coord(lat, "N", "S"), _fmt_coord(lon, "E", "W")


def datahora(dia, mes, ano, hrs, minuto, fuso):
    data         = fuso.localize(pydt(ano, mes, dia, hrs, minuto, 0), is_dst=None)
    offset_hours = data.utcoffset().total_seconds() / 3600
    return data, data.astimezone(pytz.utc), offset_hours


def amanhecer(ano, mes, dia, lat, lon, fuso):
    return sun(LocationInfo(latitude=lat, longitude=lon).observer, date=pydt(ano, mes, dia), tzinfo=fuso)["sunrise"]


def _lon_to_sign(lon):
    lon = lon % 360
    return SIGNOS_EN[int(lon // 30)], lon % 30


def _get_house(lon, cusps):
    lon  = lon % 360
    nc   = len(cusps)
    base = 1 if nc == 13 else 0
    for i in range(12):
        s = cusps[base + i] % 360
        e = cusps[base + (i + 1) % 12] % 360
        if (s < e and s <= lon < e) or (s >= e and (lon >= s or lon < e)):
            return i + 1
    return 12


def dia_juliano(ano, mes, dia, hrs, minuto, coords, fuso):
    utc = fuso.localize(pydt(ano, mes, dia, hrs, minuto)).astimezone(pytz.utc)
    return swe.julday(utc.year, utc.month, utc.day, utc.hour + utc.minute / 60)


def criar_mapa(jd, lat, lon):
    cusps, ascmc = swe.houses(jd, lat, lon, b"P")
    asc_lon, mc_lon = ascmc[0], ascmc[1]
    dsc_lon = (asc_lon + 180) % 360
    ic_lon  = (mc_lon  + 180) % 360
    vtx_lon = ascmc[3] % 360
    avx_lon = (vtx_lon + 180) % 360

    objs = []
    for nm, body in CORPOS_SWE:
        res = swe.calc_ut(jd, body)
        la  = res[0][0] % 360
        sg, sl = _lon_to_sign(la)
        objs.append(Planeta(id=nm, lon=la, signlon=sl, sign=sg, speed=res[0][3], house=_get_house(la, cusps)))

    nn     = next(p for p in objs if p.id == "North node")
    sn_lon = (nn.lon + 180) % 360
    sg, sl = _lon_to_sign(sn_lon)
    objs.append(Planeta(id="South node", lon=sn_lon, signlon=sl, sign=sg, speed=-nn.speed, house=_get_house(sn_lon, cusps)))

    angs = []
    for nm, al in [("Asc", asc_lon), ("Mc", mc_lon), ("Desc", dsc_lon), ("Ic", ic_lon),
                   ("Vertex", vtx_lon), ("Antivertex", avx_lon)]:
        sg, sl = _lon_to_sign(al)
        angs.append(Planeta(id=nm, lon=al, signlon=sl, sign=sg, speed=0, is_angle=True))

    return objs, angs, cusps, asc_lon, mc_lon, dsc_lon


def dignidade_planetaria(nome_pt, signo_pt):
    dig = DIGNIDADES.get(nome_pt, {})
    if signo_pt in dig.get("domicílio",  []): return "Domicílio"
    if signo_pt in dig.get("exaltação",  []): return "Exaltação"
    if signo_pt in dig.get("detrimento", []): return "Detrimento"
    if signo_pt in dig.get("queda",      []): return "Queda"
    return ""


def fmt_objeto(p):
    d, m  = int(p.signlon), int((p.signlon - int(p.signlon)) * 60)
    nome  = planetas.get(p.id.capitalize(), p.id)
    signo = signos.get(p.sign, p.sign)
    if p.is_angle:
        return f"{nome} em {signo} {d:02d}° {m:02d}'"
    mv = p.movement().replace("Direct","[D]").replace("Retrograde","[R]").replace("Stationary","[E]")
    dg = dignidade_planetaria(nome, signo)
    return f"{nome} {mv} em {signo} {d:02d}° {m:02d}'{' ✦'+dg if dg else ''}, Casa {p.house}"


def _reduzir(n, mestres=frozenset({11, 22})):
    while n > 9 and n not in mestres:
        n = sum(int(d) for d in str(n))
    return n


def numerologia(nome, sobrenome, dia, mes, ano):
    nc = f"{nome} {sobrenome}".upper(); nu = nome.upper()
    life        = _reduzir(sum(int(d) for d in f"{dia:02d}{mes:02d}{ano}"))
    active      = _reduzir(sum(letras.get(c, 0) for c in nu if c in letras))
    heart       = _reduzir(sum(letras.get(c, 0) for c in nc if c in VOGAIS))
    personality = _reduzir(sum(letras.get(c, 0) for c in nc if c.isalpha() and c not in VOGAIS and c in letras))
    karma       = sorted(set(range(1, 10)) - {letras[c] for c in nc if c in letras})
    return life, active, heart, personality, karma


def numero_expressao(nome, sobrenome):
    nc = f"{nome} {sobrenome}".upper()
    return _reduzir(sum(letras.get(c, 0) for c in nc if c.isalpha() and c in letras))


def ano_pessoal(dia, mes, ano_ref=None):
    if ano_ref is None: ano_ref = hoje.today().year
    return _reduzir(sum(int(d) for d in f"{dia:02d}{mes:02d}{ano_ref}"))


def mes_pessoal(dia, mes, mes_ref=None, ano_ref=None):
    if ano_ref is None: ano_ref = hoje.today().year
    if mes_ref is None: mes_ref = hoje.today().month
    return _reduzir(ano_pessoal(dia, mes, ano_ref) + mes_ref)


def pinnacles_challenges(dia, mes, ano, life):
    m = _reduzir(mes); d = _reduzir(dia); y = _reduzir(sum(int(x) for x in str(ano)))
    p1, p2 = _reduzir(m+d), _reduzir(d+y)
    p3, p4 = _reduzir(p1+p2), _reduzir(m+y)
    c1 = _reduzir(abs(m-d)) if abs(m-d) > 0 else 0
    c2 = _reduzir(abs(d-y)) if abs(d-y) > 0 else 0
    c3 = _reduzir(abs(c1-c2)) if abs(c1-c2) > 0 else 0
    c4 = _reduzir(abs(m-y)) if abs(m-y) > 0 else 0
    ls = 2 if life == 11 else (4 if life == 22 else life)
    e1 = 36 - ls; e2, e3 = e1+9, e1+18
    return {
        "pinnacles": [{"numero":p1,"periodo":f"0 – {e1}"},{"numero":p2,"periodo":f"{e1+1} – {e2}"},
                      {"numero":p3,"periodo":f"{e2+1} – {e3}"},{"numero":p4,"periodo":f"{e3+1} +"}],
        "challenges": [{"numero":c1,"periodo":f"0 – {e1}"},{"numero":c2,"periodo":f"{e1+1} – {e2}"},
                       {"numero":c3,"periodo":f"{e2+1} – {e3}"},{"numero":c4,"periodo":"Geral"}],
    }


def _reducao_tarot(n):
    while n > 22:
        n = sum(int(d) for d in str(n))
    if n in (11, 22): return n
    if n == 22: return 0
    return n


def arcano_data(dia, mes, ano):     return _reducao_tarot(sum(int(d) for d in f"{dia:02}{mes:02}{ano}"))
def arcano_nome(full_name):         return _reducao_tarot(sum(letras.get(c,0) for c in full_name.upper() if c in letras))
def arcano_alma(life):              return 0 if life == 22 else life
def arcano_ano(dia, mes, ref=None): return _reducao_tarot(ano_pessoal(dia, mes, ref))


def zodiaco_chines(dia, mes, ano):
    troncos = [("Jia","Madeira","Yang"),("Yi","Madeira","Yin"),("Bing","Fogo","Yang"),("Ding","Fogo","Yin"),
               ("Wu","Terra","Yang"),("Ji","Terra","Yin"),("Geng","Metal","Yang"),("Xin","Metal","Yin"),
               ("Ren","Água","Yang"),("Gui","Água","Yin")]
    animais = ["Rato","Boi","Tigre","Coelho","Dragão","Serpente","Cavalo","Cabra","Macaco","Galo","Cão","Porco"]
    ramos   = ["Zi","Chou","Yin","Mao","Chen","Si","Wu","Wei","Shen","You","Xu","Hai"]
    off = LunarDate.fromSolarDate(ano, mes, dia).year - 1984
    tk, el, po = troncos[off % 10]
    return animais[off % 12], el, po, tk, ramos[off % 12]


def _solar_term_idx(jd):
    return int((swe.calc_ut(jd, swe.SUN)[0][0] % 360 - 315) % 360 / 30)


def _bz_pilar(si, bi):
    return {"tronco":_BZ_TRONCOS[si],"ramo":_BZ_RAMOS[bi],"animal":_BZ_ANIMAIS[bi],
            "elemento":_BZ_ELEM_T[si],"polaridade":_BZ_POL_T[si]}


def quatro_pilares(dia, mes, ano, hrs, minuto, fuso, jd_natal):
    off_ano = LunarDate.fromSolarDate(ano, mes, dia).year - 1984
    sa, ba  = off_ano % 10, off_ano % 12
    ti      = _solar_term_idx(jd_natal)
    sm, bm  = (_BZ_MES_STEM_BASE[sa] + ti) % 10, (ti + 2) % 12
    di      = (int(jd_natal + 0.5) + _BZ_DAY_OFFSET) % 60
    sd, bd  = di % 10, di % 12
    hl      = fuso.localize(pydt(ano, mes, dia, hrs, minuto)).hour + fuso.localize(pydt(ano, mes, dia, hrs, minuto)).minute / 60
    bh      = int((hl + 1) / 2) % 12
    sh      = ([0, 2, 4, 6, 8, 0, 2, 4, 6, 8][sd] + bh) % 10
    return {"ano":_bz_pilar(sa,ba),"mes":_bz_pilar(sm,bm),"dia":_bz_pilar(sd,bd),"hora":_bz_pilar(sh,bh)}


def runa_solar1(dia, mes, ano, hrs, minuto, coords, fuso):
    bt = pydt(ano, mes, dia, hrs, minuto)
    sr = amanhecer(ano, mes, dia, coords.lat, coords.lon, fuso).replace(tzinfo=None)
    tp = (mes, dia)
    for i, (r, s, e) in enumerate(runas_dias):
        ir = (s <= tp <= e) if s <= e else (tp >= s or tp <= e)
        if ir:
            if tp == s and bt < sr: return runas_dias[i-1][0]
            return r
    return runas_dias[-1][0]


def runa_solar2(hrs, minuto):
    return runas_hora[((hrs * 60 + minuto) - (23 * 60 + 30)) % 1440 // 60]


def runa_destino(nome, sobrenome):
    total = sum(letras.get(c,0) for c in f"{nome} {sobrenome}".upper() if c in letras)
    while total > 24: total = sum(int(d) for d in str(total))
    return RUNAS_LISTA[(total or 24) - 1]


def runa_oculta(r1, r2):
    total = RUNAS_LISTA.index(r1) + 1 + RUNAS_LISTA.index(r2) + 1
    while total > 24: total = sum(int(d) for d in str(total))
    return RUNAS_LISTA[(total or 24) - 1]


def posicao(jd):
    pos = {}
    for nm, body in PLANETAS_ASSIN.items():
        lon  = swe.calc_ut(jd, body)[0][0] % 360
        sign = SIGNOS_PT[int(lon // 30)]
        pos[nm] = {"Longitude":lon,"Signo":sign,"Elemento":elementos[sign],"Modalidade":modalidades[sign]}
    return pos


def e_dominante(pos):
    c = Counter(p["Elemento"]   for p in pos.values()); return c, c.most_common(1)[0][0]


def m_dominante(pos):
    c = Counter(p["Modalidade"] for p in pos.values()); return c, c.most_common(1)[0][0]


def aspectos(pos):
    ns = list(pos.keys()); sc = {n: 0.0 for n in ns}
    for i in range(len(ns)):
        for j in range(i+1, len(ns)):
            diff = min(abs(pos[ns[i]]["Longitude"]-pos[ns[j]]["Longitude"]),
                       360-abs(pos[ns[i]]["Longitude"]-pos[ns[j]]["Longitude"]))
            for angle, harm in graus_aspectos.items():
                w = ((1/harm)**alpha) * math.exp(-(abs(diff-angle)**2)/(2*sigmas[angle]**2))
                sc[ns[i]] += w; sc[ns[j]] += w
    return sc


def normalizacao(scores, decimals=3):
    vals = list(scores.values()); mn, mx = min(vals), max(vals)
    norm = {k:0.0 for k in scores} if mx==mn else {k:(v-mn)/(mx-mn) for k,v in scores.items()}
    return {k:round(v,decimals) for k,v in sorted(norm.items(),key=lambda x:x[1],reverse=True)}


def aspectos_internos(pos, threshold=0.1):
    ns = list(pos.keys()); res = []
    for i in range(len(ns)):
        for j in range(i+1, len(ns)):
            diff = min(abs(pos[ns[i]]["Longitude"]-pos[ns[j]]["Longitude"]),
                       360-abs(pos[ns[i]]["Longitude"]-pos[ns[j]]["Longitude"]))
            for angle, harm in graus_aspectos.items():
                ow = math.exp(-(abs(diff-angle)**2)/(2*sigmas[angle]**2))
                if ow < threshold: continue
                na, nat = NOMES_ASPECTOS[angle]
                res.append({"planeta1":ns[i],"planeta2":ns[j],"aspecto":na,
                            "orb":round(abs(diff-angle),2),"peso":round(((1/harm)**alpha)*ow,3),"natureza":nat})
    return sorted(res, key=lambda x:x["peso"], reverse=True)


def assinaturas(dia, mes, ano, hrs, minuto, coords, fuso):
    jd = dia_juliano(ano, mes, dia, hrs, minuto, coords, fuso)
    pos = posicao(jd); ec, de = e_dominante(pos); mc, dm = m_dominante(pos); asp = aspectos(pos)
    return {"Elemento Dominante":de,"Modalidade Dominante":dm,"Assinatura Planetária":max(asp,key=asp.get),
            "Temperamento":temperamentos[de],"Distribuição de Elementos":ec,"Distribuição de Modalidades":mc,
            "Centralidade de Aspectos":normalizacao(asp)}


def sizigia(jd_natal):
    def elong(jd):
        return (swe.calc_ut(jd,swe.MOON)[0][0] - swe.calc_ut(jd,swe.SUN)[0][0]) % 360
    step = 2/24; jd = jd_natal; e0 = elong(jd); tipo = ""
    for _ in range(15*12):
        jd -= step; e1 = elong(jd)
        if e0 < 10 and e1 > 350:                jd_sz, tipo = jd+step/2, "Novilúnio"; break
        if e0 > 180 and e1 < 180 and (e0-e1)<5: jd_sz, tipo = jd+step/2, "Plenilúnio"; break
        e0 = e1
    if not tipo: return {"tipo":"Não encontrado","data":"—","signo":"—","grau":"—"}
    ml = swe.calc_ut(jd_sz,swe.MOON)[0][0] % 360
    sl = ml % 30; d, m = int(sl), int((sl-int(sl))*60)
    yr, mo, dy, _ = swe.revjul(jd_sz)
    return {"tipo":tipo,"data":f"{int(dy):02d}/{int(mo):02d}/{int(yr)}",
            "signo":SIGNOS_PT[int(ml//30)],"grau":f"{d:02d}° {m:02d}'"}


def transitos_atuais(jd_natal):
    t = hoje.today(); jd_h = swe.julday(t.year, t.month, t.day, 12.0)
    pn = posicao(jd_natal); pa = posicao(jd_h); res = []
    for nt, pt in pa.items():
        for nn, pn_ in pn.items():
            diff = min(abs(pt["Longitude"]-pn_["Longitude"]),360-abs(pt["Longitude"]-pn_["Longitude"]))
            for angle, harm in graus_aspectos.items():
                ow = math.exp(-(abs(diff-angle)**2)/(2*sigmas[angle]**2))
                if ow < 0.1: continue
                na, nat = NOMES_ASPECTOS[angle]
                res.append({"transitante":nt,"natal":nn,"aspecto":na,
                            "orb":round(abs(diff-angle),2),"peso":round(((1/harm)**alpha)*ow,3),"natureza":nat})
    return {"data_referencia":t.strftime("%d/%m/%Y"),"aspectos":sorted(res,key=lambda x:x["peso"],reverse=True)}


def partes_arabes(asc_lon, moon_lon, sun_lon, ven_lon, dsc_lon):
    is_diurnal = (sun_lon - asc_lon) % 360 > 180
    fortuna    = (asc_lon + (moon_lon - sun_lon if is_diurnal else sun_lon - moon_lon)) % 360
    espirito   = (asc_lon + (sun_lon - moon_lon if is_diurnal else moon_lon - sun_lon)) % 360
    casamento  = (asc_lon + dsc_lon - ven_lon) % 360
    def _fmt(lon):
        si = int(lon//30); sl = lon%30; d, m = int(sl), int((sl-int(sl))*60)
        return {"signo": SIGNOS_PT[si], "grau": f"{d:02d}° {m:02d}'"}
    return {"Fortuna":_fmt(fortuna),"Espírito":_fmt(espirito),"Casamento":_fmt(casamento),
            "tipo":"Diurno" if is_diurnal else "Noturno"}


def biorritmo(dia, mes, ano):
    from datetime import date
    days = (date.today() - date(ano, mes, dia)).days
    def _c(p): v = math.sin(2*math.pi*days/p); return {"valor":round(v,3),"critico":abs(v)<0.1}
    return {"data":hoje.today().strftime("%d/%m/%Y"),"dias":days,
            "Físico":_c(23),"Emocional":_c(28),"Intelectual":_c(33),"Intuitivo":_c(38),
            "Estético":_c(43),"Consciência":_c(48),"Espiritual":_c(53)}


def iching_natal(dia, mes, ano, hrs, minuto):
    century  = ano // 100 + 1
    year_idx = ano % 100
    is_pares = (century % 2 == 0)
    upper    = _IC_KW[(year_idx + (2 if is_pares else 0)) % 8]
    birth_md = (mes, dia); lower = "Qian"
    for start, end, tri in _IC_PERIODOS:
        if start <= birth_md <= end: lower = tri; break
    hexnum       = _IC_HEX[_IC_IDX[lower]][_IC_IDX[upper]]
    block        = (hrs * 60 + minuto) // 45
    is_odd_day   = (dia % 2 != 0)
    lin_mutantes = sorted([i+1 for i in range(5) if block & (1 << i)] + ([6] if is_odd_day else []))
    all_lines    = list(_IC_LINHAS[lower]) + list(_IC_LINHAS[upper])
    hex2num = hex2nome = None
    if lin_mutantes:
        mut = all_lines.copy()
        for l in lin_mutantes: mut[l-1] = 1 - mut[l-1]
        def _find_tri(lines):
            t = tuple(lines)
            for nm, pat in _IC_LINHAS.items():
                if pat == t: return nm
            return "Qian"
        nl, nu2 = _find_tri(mut[:3]), _find_tri(mut[3:])
        hex2num = _IC_HEX[_IC_IDX[nl]][_IC_IDX[nu2]]; hex2nome = _IC_NOMES[hex2num]
    return {"hexagrama":hexnum,"nome":_IC_NOMES[hexnum],"superior":upper,"inferior":lower,
            "linhas_mutantes":lin_mutantes,"hexagrama_mutante":hex2num,"nome_mutante":hex2nome,"linhas":all_lines}


def padrao_jones(objetos_lista):
    ids  = {"Sun","Moon","Mercury","Venus","Mars","Jupiter","Saturn","Uranus","Neptune","Pluto"}
    lons = sorted(p.lon for p in objetos_lista if p.id in ids)
    n    = len(lons)
    if n < 7: return {"padrao":"Indeterminado","descricao":"Planetas insuficientes","handle":None}
    gaps    = [(lons[(i+1)%n]-lons[i])%360 for i in range(n)]
    gs      = sorted(gaps, reverse=True)
    mg, sg2 = gs[0], gs[1]
    if   mg >= 240: padrao = "Bundle"
    elif mg >= 180: padrao = "Bucket" if (sg2 >= 60 and sg2 < 150) else "Bowl"
    elif mg >= 120: padrao = "Locomotive"
    elif sg2 >= 60 and (mg + sg2) > 180: padrao = "Seesaw"
    elif mg < 45:   padrao = "Splash"
    else:           padrao = "Splay" if sum(1 for g in gaps if g > 25) >= 3 else "Splash"
    handle = None
    if padrao == "Bucket":
        mi      = gaps.index(mg); hi = (mi+1) % n
        ordered = sorted([(p.lon, planetas.get(p.id.capitalize(), p.id)) for p in objetos_lista if p.id in ids])
        if hi < len(ordered): handle = ordered[hi][1]
    return {"padrao":padrao,"descricao":_JONES_DESC.get(padrao,""),"handle":handle,"arco":round(360-mg,1)}


def stellium(objetos_lista):
    excluir = {"North node","South node"}
    validos = [p for p in objetos_lista if not p.is_angle and p.id not in excluir]
    por_signo = Counter(p.sign  for p in validos)
    por_casa  = Counter(p.house for p in validos if p.house > 0)
    result = []
    for sign, count in por_signo.items():
        if count >= 3:
            nms = [planetas.get(p.id.capitalize(), p.id) for p in validos if p.sign == sign]
            result.append({"tipo":"signo","local":signos.get(sign, sign),"planetas":nms,"count":count})
    for house, count in por_casa.items():
        if count >= 3:
            nms = [planetas.get(p.id.capitalize(), p.id) for p in validos if p.house == house]
            result.append({"tipo":"casa","local":f"Casa {house}","planetas":nms,"count":count})
    return result


def nakshatra(lon_lua):
    lon  = lon_lua % 360
    span = 360 / 27
    idx  = int(lon / span)
    pada = int((lon % span) / (span / 4)) + 1
    nm, senhor, desc = _NAKSHATRAS[idx]
    return {"nome":nm,"senhor":senhor,"pada":pada,"descricao":desc,"indice":idx+1}


def energia_do_dia(dia_nasc, mes_nasc, jd_natal, cusps):
    t    = hoje.today()
    jd_h = swe.julday(t.year, t.month, t.day, 12.0)
    du   = _reduzir(sum(int(d) for d in f"{t.day:02d}{t.month:02d}{t.year}"))
    dp   = _reduzir(du + ano_pessoal(dia_nasc, mes_nasc))
    arc_d = arcano_data(t.day, t.month, t.year)
    lua_lon = swe.calc_ut(jd_h, swe.MOON)[0][0] % 360
    lua_si  = int(lua_lon // 30)
    lua_sl  = lua_lon % 30
    lua_d, lua_m = int(lua_sl), int((lua_sl - int(lua_sl)) * 60)
    lua_casa = _get_house(lua_lon, cusps)
    di       = (int(jd_h + 0.5) + _BZ_DAY_OFFSET) % 60
    pilar_d  = _bz_pilar(di % 10, di % 12)
    tp     = (t.month, t.day)
    runa_d = runas_dias[-1][0]
    for runa, start, end in runas_dias:
        in_range = (start <= tp <= end) if start <= end else (tp >= start or tp <= end)
        if in_range: runa_d = runa; break
    return {
        "data":          t.strftime("%d/%m/%Y"),
        "dia_universal": du,
        "dia_pessoal":   dp,
        "arcano":        arc_d,
        "lua_signo":     SIGNOS_PT[lua_si],
        "lua_grau":      f"{lua_d:02d}° {lua_m:02d}'",
        "lua_casa":      lua_casa,
        "pilar_dia":     pilar_d,
        "runa":          runa_d,
    }


# ── Função principal de cálculo ───────────────────────────────────────────────

def autoconhecimento(nome, sobrenome, cidade, pais, dia, mes, ano, hrs, minuto):
    _local, coords, fuso, zona, latitude, longitude = latlong(cidade, pais)
    local_dt, data_utc, offset_hours = datahora(dia, mes, ano, hrs, minuto, fuso)
    is_dst = bool(local_dt.dst())

    jd = dia_juliano(ano, mes, dia, hrs, minuto, coords, fuso)
    objetos_lista, angulos_lista, cusps, asc_lon, mc_lon, dsc_lon = criar_mapa(jd, coords.lat, coords.lon)

    pos   = posicao(jd)
    aspin = aspectos_internos(pos)
    sz    = sizigia(jd)
    qp    = quatro_pilares(dia, mes, ano, hrs, minuto, fuso, jd)
    trans = transitos_atuais(jd)
    jones = padrao_jones(objetos_lista)
    ic    = iching_natal(dia, mes, ano, hrs, minuto)
    stell = stellium(objetos_lista)
    ed    = energia_do_dia(dia, mes, jd, cusps)

    _moon = next((p for p in objetos_lista if p.id == "Moon"), None)
    nak   = nakshatra(_moon.lon) if _moon else None

    _sun = next((p for p in objetos_lista if p.id == "Sun"),  None)
    _ven = next((p for p in objetos_lista if p.id == "Venus"), None)
    partes = partes_arabes(asc_lon, _moon.lon, _sun.lon, _ven.lon, dsc_lon) if all([_moon,_sun,_ven]) else {}

    animal, elem, pol, tronco, ramo  = zodiaco_chines(dia, mes, ano)
    life, active, heart, pers, karma = numerologia(nome, sobrenome, dia, mes, ano)
    expressao                        = numero_expressao(nome, sobrenome)
    ap, mp                           = ano_pessoal(dia, mes), mes_pessoal(dia, mes)
    pc                               = pinnacles_challenges(dia, mes, ano, life)
    bio                              = biorritmo(dia, mes, ano)

    arcanoN, arcanoD   = arcano_nome(f"{nome} {sobrenome}"), arcano_data(dia, mes, ano)
    arcanoA, arcanoAno = arcano_alma(life), arcano_ano(dia, mes)

    runa1, runa2 = runa_solar1(dia, mes, ano, hrs, minuto, coords, fuso), runa_solar2(hrs, minuto)
    runa3, runa4 = runa_destino(nome, sobrenome), runa_oculta(runa1, runa2)

    assin = assinaturas(dia, mes, ano, hrs, minuto, coords, fuso)

    dados_gerais = f"""
      {nome.title()} {sobrenome.title()}
      Cidade: {cidade.title()}, {pais.title()}
      Coordenadas: {latitude} | {longitude}
      Fuso horário: {zona}
      Variação para UTC: {offset_hours:+.1f}h
      Horário original: {"solar" if is_dst else "legal"}
      Data-hora UTC: {data_utc.strftime("%d/%m/%Y %H:%M")}
    """.strip()

    return {
        "geral": dados_gerais,
        "astrologia": {
            "planetas":          "  \n".join(fmt_objeto(p) for p in objetos_lista),
            "angulos":           "  \n".join(fmt_objeto(p) for p in angulos_lista),
            "aspectos_internos": aspin,
            "sizigia":           sz,
            "jones":             jones,
            "partes":            partes,
            "stellium":          stell,
        },
        "numerologia": f"""
      Número da Vida: {life}
      Número da Expressão: {expressao}
      Número da Atitude: {active}
      Número da Alma: {heart}
      Número da Personalidade: {pers}
      Números Ausentes (kármicos): {karma}
      Ano Pessoal: {ap} | Mês Pessoal: {mp}
        """.strip(),
        "tarot": f"""
      Arcano da Data: {arcanoD} ({arcanos[arcanoD]})
      Arcano do Nome: {arcanoN} ({arcanos[arcanoN]})
      Arcano da Alma: {arcanoA} ({arcanos[arcanoA]})
      Arcano do Ano: {arcanoAno} ({arcanos[arcanoAno]})
        """.strip(),
        "chines": f"""
      {animal} de {elem} {pol} ({tronco} {ramo})
      Animal: {animal} | Elemento: {elem} | Polaridade: {pol}
      Tronco Celeste: {tronco} | Ramo Terrestre: {ramo}
        """.strip(),
        "runas": f"""
      Runa Principal: {runa1}
      Runa Secundária: {runa2}
      Runa do Destino: {runa3}
      Runa Oculta: {runa4}
        """.strip(),
        "tarot_raw":      {"data":arcanoD,"nome":arcanoN,"alma":arcanoA,"ano":arcanoAno},
        "runas_raw":      {"principal":runa1,"secundaria":runa2,"destino":runa3,"oculta":runa4},
        "assinaturas":    assin,
        "quatro_pilares": qp,
        "transitos":      trans,
        "pinnacles":      pc,
        "biorritmo":      bio,
        "iching":         ic,
        "nakshatra":      nak,
        "energia_do_dia": ed,
    }


# ── Funções de renderização HTML (inalteradas) ────────────────────────────────

def negrito(texto):
    texto = re.sub(r"(^|\n)\s*([^:\n]+):", r"\1<strong>\2:</strong>", texto)
    return texto.replace("\n", "<br>")

def _fmt_dist(d):
    return ", ".join(f"{k} ({v})" for k,v in d.items()) if isinstance(d,dict) else str(d)

def _cor_cat(nome):
    return {"pessoal":"#7ecf8e","projetos":"#f8d56b","geracional":"#555"}.get(
        CATEGORIAS_PLANETAS.get(nome,"geracional"),"#555")

def _h2(mt="0"):
    return f"font-size:13px;color:#555;text-transform:uppercase;letter-spacing:.08em;margin:{mt} 0 10px 0;"

def _tabela_asp_html(lista, k1, k2, l1, l2, n=10):
    def _bloco(nat, cor):
        it   = [a for a in lista if a["natureza"]==nat][:n]
        rows = "".join(
            f'<tr><td style="padding:3px 8px;color:{_cor_cat(a[k1])};font-size:13px;">{a[k1]}</td>'
            f'<td style="padding:3px 8px;color:{_cor_cat(a[k2])};font-size:13px;">{a[k2]}</td>'
            f'<td style="padding:3px 8px;color:{cor};font-size:13px;">{a["aspecto"]}</td>'
            f'<td style="padding:3px 8px;color:#888;font-size:12px;">{a["orb"]}°</td>'
            f'<td style="padding:3px 8px;color:#888;font-size:12px;">{a["peso"]:.3f}</td></tr>'
            for a in it) or '<tr><td colspan="5" style="color:#555;padding:4px 8px;font-size:12px;">—</td></tr>'
        lb = "Harmoniosos" if nat=="harmonioso" else "Tensos"
        return (f'<div><p style="color:{cor};font-size:11px;text-transform:uppercase;letter-spacing:.05em;margin:0 0 8px 0;">{lb}</p>'
                f'<table style="width:100%;border-collapse:collapse;">'
                f'<tr style="color:#555;font-size:11px;text-transform:uppercase;letter-spacing:.05em;">'
                f'<th style="text-align:left;padding:3px 8px;">{l1}</th>'
                f'<th style="text-align:left;padding:3px 8px;">{l2}</th>'
                f'<th style="text-align:left;padding:3px 8px;">Aspecto</th>'
                f'<th style="text-align:left;padding:3px 8px;">Orbe</th>'
                f'<th style="text-align:left;padding:3px 8px;">Peso</th></tr>'
                f"{rows}</table></div>")
    return f'<div class="grid-asp">{_bloco("harmonioso","#7ecf8e")}{_bloco("tenso","#f88888")}</div>'

def _secao_asp(lista, titulo, k1="planeta1", k2="planeta2", l1="Planeta", l2="Planeta", mt="32px"):
    return f'<h2 style="{_h2(mt)}">{titulo}</h2>' + _tabela_asp_html(lista, k1, k2, l1, l2)

def _html_bazi(qp):
    rows = "".join(
        f'<tr><td style="padding:4px 8px;color:#888;font-size:12px;">{lb}</td>'
        + "".join(f'<td style="padding:4px 8px;color:#e8e8e8;font-size:12px;">{p[k]}</td>'
                  for k in ["tronco","ramo","animal","elemento","polaridade"])
        + "</tr>" for lb, p in [("Ano",qp["ano"]),("Mês",qp["mes"]),("Dia",qp["dia"]),("Hora",qp["hora"])])
    return (f'<table style="width:100%;border-collapse:collapse;margin-top:8px;">'
            f'<tr style="color:#555;font-size:11px;text-transform:uppercase;letter-spacing:.05em;">'
            f'<th style="text-align:left;padding:4px 8px;">Pilar</th><th style="text-align:left;padding:4px 8px;">Tronco</th>'
            f'<th style="text-align:left;padding:4px 8px;">Ramo</th><th style="text-align:left;padding:4px 8px;">Animal</th>'
            f'<th style="text-align:left;padding:4px 8px;">Elemento</th><th style="text-align:left;padding:4px 8px;">Polaridade</th></tr>'
            f"{rows}</table>")

def _html_pc(pc):
    def _tabela(titulo, items, cor):
        rows = "".join(
            f'<tr><td style="padding:4px 8px;color:{cor};font-size:14px;font-weight:600;">{i["numero"]}</td>'
            f'<td style="padding:4px 8px;color:#888;font-size:12px;">{i["periodo"]}</td></tr>'
            for i in items)
        return (f'<div><p style="color:{cor};font-size:11px;text-transform:uppercase;letter-spacing:.05em;margin:0 0 6px 0;">{titulo}</p>'
                f'<table style="width:100%;border-collapse:collapse;">'
                f'<tr style="color:#555;font-size:11px;text-transform:uppercase;letter-spacing:.05em;">'
                f'<th style="text-align:left;padding:4px 8px;">Nº</th>'
                f'<th style="text-align:left;padding:4px 8px;">Período (idade)</th></tr>'
                f"{rows}</table></div>")
    return (f'<div class="grid-2" style="margin-top:8px;">'
            + _tabela("Pínáculos", pc["pinnacles"], "#a8d8ea")
            + _tabela("Desafios",  pc["challenges"], "#f8c47b")
            + "</div>")

def _html_partes(partes):
    if not partes: return '<p style="color:#555;font-size:12px;">Não calculado</p>'
    tipo = partes.get("tipo","")
    rows = "".join(f'<p style="margin:3px 0;font-size:13px;"><strong>{k}:</strong> {v["signo"]} {v["grau"]}</p>'
                   for k,v in partes.items() if isinstance(v, dict))
    return f'<p style="color:#555;font-size:11px;margin:0 0 6px 0;">Mapa {tipo}</p>' + rows

def _bio_chart_svg(bio, cycles, titulo):
    days_total = bio["dias"]
    W, H       = 560, 120
    ml, mr, mt, mb = 8, 8, 22, 22
    w, h       = W - ml - mr, H - mt - mb
    window     = 56
    _colors  = {"Físico":"#4fc3f7","Emocional":"#ef5350","Intelectual":"#ffee58",
                "Intuitivo":"#66bb6a","Estético":"#ab47bc","Consciência":"#ff7043","Espiritual":"#26c6da"}
    _periods = {"Físico":23,"Emocional":28,"Intelectual":33,"Intuitivo":38,
                "Estético":43,"Consciência":48,"Espiritual":53}
    zero_y  = mt + h / 2
    today_x = ml + w / 2
    grids   = (f'<line x1="{ml}" y1="{mt}" x2="{ml+w}" y2="{mt}" stroke="#1c1c1c" stroke-width="0.5"/>'
               f'<line x1="{ml}" y1="{zero_y:.1f}" x2="{ml+w}" y2="{zero_y:.1f}" stroke="#2a2a2a" stroke-width="0.8"/>'
               f'<line x1="{ml}" y1="{mt+h}" x2="{ml+w}" y2="{mt+h}" stroke="#1c1c1c" stroke-width="0.5"/>'
               f'<line x1="{today_x:.1f}" y1="{mt}" x2="{today_x:.1f}" y2="{mt+h}" '
               f'stroke="#444" stroke-width="1" stroke-dasharray="3,3"/>')
    hoje_lbl = (f'<text x="{today_x:.1f}" y="{mt-6}" text-anchor="middle" '
                f'fill="#555" font-size="9" font-family="Inter,sans-serif">hoje</text>')
    title_el = (f'<text x="{ml}" y="{mt-8}" fill="#555" font-size="9" '
                f'font-family="Inter,sans-serif">{titulo}</text>')
    path_els = []
    for c in cycles:
        p, col = _periods[c], _colors[c]
        pts = []
        for i in range(window + 1):
            d = days_total - window // 2 + i
            v = math.sin(2 * math.pi * d / p)
            x = ml + (i / window) * w
            y = mt + (1 - v) / 2 * h
            pts.append(f"{x:.1f},{y:.1f}")
        path_els.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{col}" stroke-width="1.8"/>')
    step = w / len(cycles)
    leg_els = []
    for i, c in enumerate(cycles):
        col = _colors[c]
        lx  = ml + i * step + step / 2
        leg_els.append(
            f'<circle cx="{lx:.1f}" cy="{H-8}" r="3.5" fill="{col}"/>'
            f'<text x="{lx+8:.1f}" y="{H-4}" fill="{col}" font-size="9" font-family="Inter,sans-serif">{c}</text>'
        )
    return (f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
            f'style="display:block;width:100%;max-width:{W}px;margin-top:8px;">'
            f'<rect width="{W}" height="{H}" fill="#080808" rx="4"/>'
            f"{grids}{title_el}{hoje_lbl}"
            f'{"".join(path_els)}'
            f'{"".join(leg_els)}'
            f"</svg>")

def _html_bio(bio):
    def _bar(label, val, critico):
        pct   = min(abs(val)*100, 100)
        cor   = "#f8d56b" if critico else ("#7ecf8e" if val >= 0 else "#f88888")
        lbl   = f"{label}{'  ⚠' if critico else ''}"
        side  = "left:50%" if val >= 0 else "right:50%"
        rad   = "0 3px 3px 0" if val >= 0 else "3px 0 0 3px"
        lbl_color = "#f8d56b" if critico else "#aaa"
        return (
            f'<div class="bio-row">'
            f'<span class="bio-label" style="color:{lbl_color};">{lbl}</span>'
            f'<div class="bio-track">'
            f'  <div style="position:absolute;{side};width:{pct:.1f}%;height:10px;background:{cor};border-radius:{rad};"></div>'
            f'  <div style="position:absolute;left:50%;width:1px;height:10px;background:#2a2a2a;"></div>'
            f'</div>'
            f'<span class="bio-val">{val:+.3f}</span>'
            f'</div>'
        )
 
    primarios   = ["Físico","Emocional","Intelectual","Intuitivo"]
    secundarios = ["Estético","Consciência","Espiritual"]
 
    header  = f'<p style="font-size:12px;color:#555;margin:0 0 10px 0;">Referência: {bio["data"]} ({bio["dias"]:,} dias de vida)</p>'
    bloco_p = ('<p style="font-size:11px;color:#555;text-transform:uppercase;letter-spacing:.05em;margin:0 0 6px 0;">Primários</p>'
               + "".join(_bar(f"{k} ({p}d)", bio[k]["valor"], bio[k]["critico"])
                         for k, p in zip(primarios, [23,28,33,38])))
    divisor = '<div style="border-top:1px solid #1e1e1e;margin:10px 0 8px 0;"></div>'
    bloco_s = ('<p style="font-size:11px;color:#555;text-transform:uppercase;letter-spacing:.05em;margin:0 0 6px 0;">Secundários</p>'
               + "".join(_bar(f"{k} ({p}d)", bio[k]["valor"], bio[k]["critico"])
                         for k, p in zip(secundarios, [43,48,53])))
 
    barras   = bloco_p + divisor + bloco_s
    graficos = (f'<div class="grid-asp">'
                + _bio_chart_svg(bio, primarios,   "PRIMÁRIOS")
                + _bio_chart_svg(bio, secundarios, "SECUNDÁRIOS")
                + "</div>")
 
    return (header
            + f'<div class="grid-bio">'
            + f"<div>{barras}</div>"
            + f"<div>{graficos}</div>"
            + "</div>")

def _html_iching(ic):
    def _linha(yang, mutante=False):
        cor = "#f8d56b" if mutante else "var(--color-text-primary)"; op = "1" if mutante else "0.85"
        if yang:
            return (f'<div style="display:flex;justify-content:center;height:8px;margin:3px 0;">'
                    f'<div style="width:60px;height:4px;background:{cor};opacity:{op};border-radius:2px;"></div></div>')
        return (f'<div style="display:flex;justify-content:center;gap:8px;height:8px;margin:3px 0;">'
                f'<div style="width:26px;height:4px;background:{cor};opacity:{op};border-radius:2px;"></div>'
                f'<div style="width:26px;height:4px;background:{cor};opacity:{op};border-radius:2px;"></div></div>')
    linhas   = ic["linhas"]; mutantes = set(ic["linhas_mutantes"])
    hex_svg  = "".join(_linha(linhas[i]==1,(i+1) in mutantes) for i in range(5,-1,-1))
    sup, inf = ic["superior"], ic["inferior"]
    si, ii   = _IC_INFO[sup], _IC_INFO[inf]
    mut_html = (f'<p style="margin:10px 0 2px 0;font-size:11px;color:#555;text-transform:uppercase;letter-spacing:.05em;">Hexagrama mutante</p>'
                f'<p style="margin:0;font-size:14px;color:#f8d56b;font-weight:600;">{ic["hexagrama_mutante"]} — {ic["nome_mutante"]}</p>'
                f'<p style="font-size:11px;color:#555;margin:4px 0 0 0;">Linhas mutantes: {", ".join(str(l) for l in ic["linhas_mutantes"])}</p>'
                if ic["hexagrama_mutante"] else
                '<p style="font-size:11px;color:#555;margin:10px 0 0 0;">Sem linhas mutantes</p>')
    return (f'<div style="display:flex;gap:20px;align-items:flex-start;">'
            f'<div style="text-align:center;flex-shrink:0;">{hex_svg}'
            f'<p style="margin:4px 0 0 0;font-size:10px;color:#555;">{si[0]}{ii[0]}</p></div>'
            f'<div><p style="margin:0 0 2px 0;font-size:12px;color:#888;">Hexagrama {ic["hexagrama"]}</p>'
            f'<p style="margin:0 0 6px 0;font-size:15px;font-weight:600;color:var(--color-text-primary);">{ic["nome"]}</p>'
            f'<p style="margin:0 0 2px 0;font-size:12px;color:#666;">{si[0]} {sup} — {si[1]} · {si[2]}</p>'
            f'<p style="margin:0;font-size:12px;color:#666;">{ii[0]} {inf} — {ii[1]} · {ii[2]}</p>'
            f"{mut_html}</div></div>")

def _html_nakshatra(nak):
    if not nak: return '<p style="color:#555;font-size:12px;">Não calculado</p>'
    return (f'<p style="margin:2px 0;font-size:13px;"><strong>{nak["nome"]}</strong>'
            f' <span style="color:#888;font-size:12px;">(Pada {nak["pada"]} · Mansão {nak["indice"]})</span></p>'
            f'<p style="margin:2px 0;font-size:12px;color:#888;">Senhor: {nak["senhor"]}</p>'
            f'<p style="margin:4px 0 0 0;font-size:12px;color:#666;font-style:italic;">{nak["descricao"]}</p>')

def _html_energia_dia(ed):
    p = ed["pilar_dia"]
    return (
        f'<div class="grid-3-sm" style="font-size:13px;">'
        f'<div>'
        f'<p style="color:#555;font-size:11px;text-transform:uppercase;letter-spacing:.05em;margin:0 0 8px 0;">Numerologia</p>'
        f'<p style="margin:3px 0;"><strong>Dia Universal:</strong> {ed["dia_universal"]}</p>'
        f'<p style="margin:3px 0;"><strong>Dia Pessoal:</strong> {ed["dia_pessoal"]}</p>'
        f'<p style="margin:3px 0;"><strong>Arcano do Dia:</strong> {ed["arcano"]} ({arcanos[ed["arcano"]]})</p>'
        f'</div>'
        f'<div>'
        f'<p style="color:#555;font-size:11px;text-transform:uppercase;letter-spacing:.05em;margin:0 0 8px 0;">Astrologia</p>'
        f'<p style="margin:3px 0;"><strong>Lua em:</strong> {ed["lua_signo"]} {ed["lua_grau"]}</p>'
        f'<p style="margin:3px 0;color:#888;font-size:12px;">Transita pela Casa {ed["lua_casa"]} natal</p>'
        f'</div>'
        f'<div>'
        f'<p style="color:#555;font-size:11px;text-transform:uppercase;letter-spacing:.05em;margin:0 0 8px 0;">Ba Zi · Runas</p>'
        f'<p style="margin:3px 0;"><strong>Pilar do Dia:</strong> {p["tronco"]} {p["ramo"]} ({p["animal"]})</p>'
        f'<p style="margin:3px 0;"><strong>Runa do Dia:</strong> {ed["runa"]}</p>'
        f'</div>'
        f'</div>'
    )

def _html_tarot_cards(raw):
    items = [("Data", raw["data"]), ("Nome", raw["nome"]), ("Alma", raw["alma"]), ("Ano", raw["ano"])]
    cards = []
    for label, n in items:
        roman = _ROMAN[n] if n <= 21 else str(n)
        simb  = _ARCANO_SIMB.get(n, "✦")
        nome  = arcanos[n]
        cards.append(
            f'<div style="text-align:center;">'
            f'<div style="width:64px;height:104px;background:#0d0d0d;border:1px solid #3a2f10;'
            f'border-radius:4px;display:flex;flex-direction:column;align-items:center;'
            f'justify-content:space-between;padding:7px 4px;margin:0 auto;">'
            f'<span style="font-size:12px;color:#a07830;font-weight:600;letter-spacing:.05em;">{roman}</span>'
            f'<span style="font-size:32px;color:#d4a853;line-height:1;">{simb}</span>'
            f'<span style="font-size:10px;color:#666;text-align:center;line-height:1.3;">{nome}</span>'
            f"</div>"
            f'<p style="font-size:11px;color:#555;margin:5px 0 0 0;">{label}</p>'
            f"</div>"
        )
    return f'<div style="display:flex;gap:10px;margin-top:12px;">{"".join(cards)}</div>'

def _html_runa_pedras(raw):
    items = [("Principal", raw["principal"]), ("Secundária", raw["secundaria"]),
             ("Destino", raw["destino"]), ("Oculta", raw["oculta"])]
    stones = []
    for label, nome in items:
        char = _RUNA_UNICODE.get(nome, "?")
        stones.append(
            f'<div style="text-align:center;">'
            f'<div style="width:54px;height:64px;'
            f'border-radius:50% 50% 48% 48% / 55% 55% 45% 45%;'
            f'background:#181818;border:1px solid #303030;'
            f'display:flex;align-items:center;justify-content:center;margin:0 auto;">'
            f'<span style="font-size:26px;color:#c8b47a;font-family:serif;">{char}</span>'
            f"</div>"
            f'<p style="font-size:12px;color:#888;margin:5px 0 1px 0;font-weight:600;">{nome}</p>'
            f'<p style="font-size:11px;color:#555;margin:0;">{label}</p>'
            f"</div>"
        )
    return f'<div style="display:flex;gap:12px;margin-top:12px;">{"".join(stones)}</div>'


def renderizar(nome_v, sobrenome_v, cidade_v, pais_v, dia, mes, ano, hrs, minuto):
    r      = autoconhecimento(nome_v, sobrenome_v, cidade_v, pais_v, dia, mes, ano, hrs, minuto)
    assin  = r["assinaturas"]
    sz     = r["astrologia"]["sizigia"]
    aspin  = r["astrologia"]["aspectos_internos"]
    trans  = r["transitos"]
    qp     = r["quatro_pilares"]
    jones  = r["astrologia"]["jones"]
    partes = r["astrologia"]["partes"]
    stell  = r["astrologia"]["stellium"]
    pc     = r["pinnacles"]
    bio    = r["biorritmo"]
    ic     = r["iching"]
    nak    = r["nakshatra"]
    ed     = r["energia_do_dia"]
 
    centralidade_html = (
        "<ul style='margin:8px 0 0 0;padding-left:18px;line-height:1.8;'>"
        + "".join(f"<li><strong>{p}</strong>: {v:.3f}</li>"
                  for p, v in assin["Centralidade de Aspectos"].items())
        + "</ul>")
 
    assinaturas_html = (
        f'<p><strong>Elemento Dominante:</strong> {assin["Elemento Dominante"]}</p>'
        f'<p><strong>Modalidade Dominante:</strong> {assin["Modalidade Dominante"]}</p>'
        f'<p><strong>Assinatura Planetária:</strong> {assin["Assinatura Planetária"]}</p>'
        f'<p><strong>Temperamento:</strong> {assin["Temperamento"]}</p>'
        f'<p><strong>Distribuição de Elementos:</strong> {_fmt_dist(assin["Distribuição de Elementos"])}</p>'
        f'<p><strong>Distribuição de Modalidades:</strong> {_fmt_dist(assin["Distribuição de Modalidades"])}</p>'
        f"<h4 style='margin:12px 0 4px 0;font-size:12px;color:#555;text-transform:uppercase;letter-spacing:.05em;'>⭕ Centralidade de Aspectos</h4>"
        + centralidade_html)
 
    planetas_h = "".join(f'<p style="margin:3px 0;">{l}</p>'
                         for l in r["astrologia"]["planetas"].split("\n") if l.strip())
    angulos_h  = "".join(f'<p style="margin:3px 0;">{l}</p>'
                         for l in r["astrologia"]["angulos"].split("\n")  if l.strip())
 
    stell_html = ""
    if stell:
        items = " · ".join(
            f'<strong>{s["local"]}</strong>: {", ".join(s["planetas"][:5])}{"…" if len(s["planetas"])>5 else ""}'
            for s in stell)
        stell_html = f'<p style="margin-top:10px;font-size:12px;color:#f8d56b;">★ Stellium — {items}</p>'
 
    sz_html = (
        f'<p style="margin-top:12px;font-size:12px;color:#a8d8ea;">⟐ Sizígia: <strong>{sz["tipo"]}</strong>'
        f'<br><span style="color:#555;font-size:11px;">{sz["data"]} — Lua em {sz["signo"]} {sz["grau"]}</span></p>')
    jones_html = (
        f'<p style="margin-top:12px;font-size:12px;color:#a8d8ea;">◈ Padrão de Jones: <strong>{jones["padrao"]}</strong>'
        + (f' — alça: {jones["handle"]}' if jones.get("handle") else "")
        + f'<br><span style="color:#555;font-size:11px;">{jones["descricao"]}</span></p>')
 
    # ── CSS responsivo ────────────────────────────────────────────────────────
    # Breakpoints:
    #   > 900 px  → 3 colunas (desktop)
    #   601–900 px → 2 colunas (tablet)
    #   ≤ 600 px  → 1 coluna  (celular)
    css = """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');
      * { box-sizing: border-box; }
      body { margin: 0; padding: 0; background: #0f0f0f; }
      p { margin: 4px 0; }
 
      /* ── Grids ── */
      .grid-main  { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 32px; }
      .grid-asp   { display: grid; grid-template-columns: 1fr 1fr;     gap: 32px; }
      .grid-2     { display: grid; grid-template-columns: 1fr 1fr;     gap: 16px; }
      .grid-3-sm  { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; font-size: 13px; }
      .grid-bio   { display: grid; grid-template-columns: auto 1fr;    gap: 24px; align-items: start; }
 
      /* ── Biorritmo ── */
      .bio-row   { display: flex; align-items: center; gap: 8px; margin: 3px 0; }
      .bio-label { width: 140px; font-size: 12px; text-align: right; flex-shrink: 0; }
      .bio-track { width: 220px; background: #111; border-radius: 3px; height: 10px;
                   position: relative; flex-shrink: 0; overflow: hidden; }
      .bio-val   { font-size: 11px; color: #666; width: 52px; flex-shrink: 0; }
 
      /* ── Tablet (601 – 900 px) ── */
      @media (max-width: 900px) {
        .grid-main { grid-template-columns: 1fr 1fr; }
        .grid-bio  { grid-template-columns: 1fr; }
        .bio-track { width: 160px; }
      }
 
      /* ── Celular (≤ 600 px) ── */
      @media (max-width: 600px) {
        .grid-main  { grid-template-columns: 1fr; }
        .grid-asp   { grid-template-columns: 1fr; gap: 20px; }
        .grid-2     { grid-template-columns: 1fr; }
        .grid-3-sm  { grid-template-columns: 1fr; }
        .grid-bio   { grid-template-columns: 1fr; }
 
        .bio-label  { width: auto; flex: 0 0 38%; text-align: left; font-size: 11px; }
        .bio-track  { flex: 1; width: auto; }
        .bio-val    { display: none; }   /* economiza espaço no celular */
 
        /* tabelas de aspectos: oculta colunas menos essenciais */
        table th:nth-child(4), table td:nth-child(4),
        table th:nth-child(5), table td:nth-child(5) { display: none; }
 
        /* padding menor no container geral */
        .wrap { padding: 16px !important; border-radius: 0 !important; }
      }
    </style>
    """
 
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{css}
</head>
<body>
<div class="wrap" style="font-family:'Inter',sans-serif;background:#0f0f0f;color:#e8e8e8;border-radius:12px;padding:32px;">
    <h1 style="margin:0 0 24px 0;font-size:22px;font-weight:600;">🔮 Mapa de Autoconhecimento</h1>
 
    <div class="grid-main">
        <div>
            <h2 style="{_h2()}">📍 Dados Gerais</h2>
            <div style="line-height:1.7;font-size:14px;">{negrito(r["geral"])}</div>
            <h2 style="{_h2("24px")}">🔢 Numerologia</h2>
            <div style="line-height:1.7;font-size:14px;">{negrito(r["numerologia"])}</div>
            <h2 style="{_h2("16px")}">📈 Pínáculos e Desafios</h2>
            {_html_pc(pc)}
            <h2 style="{_h2("20px")}">🀄 Zodíaco Chinês</h2>
            <div style="line-height:1.7;font-size:14px;">{negrito(r["chines"])}</div>
            <h2 style="{_h2("16px")}">🎴 Quatro Pilares (Ba Zi)</h2>
            {_html_bazi(qp)}
            <h2 style="{_h2("24px")}">☯️ I-Ching Natal</h2>
            <div style="line-height:1.7;font-size:14px;">{_html_iching(ic)}</div>
        </div>
        <div>
            <h2 style="{_h2()}">☀️ Planetas</h2>
            <div style="line-height:1.8;font-size:14px;">{planetas_h}</div>
            {stell_html}{sz_html}{jones_html}
            <h2 style="{_h2("20px")}">🔭 Ângulos</h2>
            <div style="line-height:1.8;font-size:14px;">{angulos_h}</div>
            <h2 style="{_h2("20px")}">⚜️ Partes Árabes</h2>
            <div style="line-height:1.7;font-size:14px;">{_html_partes(partes)}</div>
            <h2 style="{_h2("24px")}">🌙 Nakshatra</h2>
            <div style="line-height:1.6;font-size:14px;">{_html_nakshatra(nak)}</div>
        </div>
        <div>
            <h2 style="{_h2()}">🧬 Assinaturas</h2>
            <div style="line-height:1.6;font-size:14px;">{assinaturas_html}</div>
            <h2 style="{_h2("24px")}">🃏 Tarot</h2>
            <div style="line-height:1.7;font-size:14px;">{negrito(r["tarot"])}</div>
            {_html_tarot_cards(r["tarot_raw"])}
            <h2 style="{_h2("20px")}">🪬 Runas</h2>
            <div style="line-height:1.7;font-size:14px;">{negrito(r["runas"])}</div>
            {_html_runa_pedras(r["runas_raw"])}
        </div>
    </div>
 
    <h2 style="{_h2("32px")}">🌅 Energia do Dia
      <span style="font-weight:300;color:#555;font-size:12px;text-transform:none;letter-spacing:0;">
        ({ed["data"]})
      </span>
    </h2>
    {_html_energia_dia(ed)}
 
    {_secao_asp(aspin, "⚡ Aspectos Internos do Natal")}
    {_secao_asp(trans["aspectos"],
               f'🌐 Trânsitos Atuais ({trans["data_referencia"]})',
               k1="transitante", k2="natal", l1="Transitante", l2="Natal")}
 
    <h2 style="{_h2("32px")}">💫 Biorritmos</h2>
    {_html_bio(bio)}
</div>
</body>
</html>"""


# ── Interface Streamlit ───────────────────────────────────────────────────────

def main(): 
    st.markdown(
        """
        <style>
        max-width: 100% !important;
        .block-container {
            padding-top: 1rem;
            padding-left: 2rem;
            padding-right: 2rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
 
    st.title("🔮 Mapa de Autoconhecimento")
 
    # ── 1. Dados pessoais ─────────────────────────────────────────────────────
 
    st.markdown("#### 👤 Dados pessoais")
    col1, col2 = st.columns(2)
 
    with col1:
        nome = st.text_input(
            "Nomes próprios",
            placeholder="ex: Maria Clara",
            help=(
                    "Insira os nomes próprios constantes na sua certidão de nascimento. "
                    "Se você se identifica com outros nomes hoje, pode utilizá-los, "
                    "sem abreviações. Os cálculos vão refletir quem você é agora."
            ),
        )

        sobrenome = st.text_input(
            "Sobrenomes ao nascer",
            placeholder="ex: Silva Pereira",
            help=(
                    "Use os sobrenomes com os quais você se identifica. Se você adotou "
                    "novos sobrenomes após transição ou mudança de nome, pode usá-los aqui. "
                    "Não use sobrenomes contraídos após casamento."
            ),
        )
 
    with col2:
        data_str = st.text_input(
            "Data de nascimento (DD/MM/AAAA)",
            placeholder="18/06/1992",
            help="Informe a data exatamente como aparece na certidão de nascimento.",
        )
        hora_str = st.text_input(
            "Hora de nascimento (HH:MM)",
            placeholder="14:53",
            help=(
                "Use o horário registrado na certidão de nascimento, "
                "sem nenhuma correção de fuso ou horário de verão — "
                "o sistema faz os ajustes automaticamente."
            ),
        )
 
    st.divider()
 
    # ── 2. Local de nascimento ────────────────────────────────────────────────
 
    st.markdown("#### 🌍 Local de nascimento")
    loc_col1, loc_col2 = st.columns(2)
 
    with loc_col1:
        pais = st.selectbox(
            "País de nascimento",
            options=_get_countries(),
            index=None,
            placeholder="Digite ou selecione…",
            key="pais_select",
            help="Selecione o país onde você nasceu. Você pode digitar para filtrar a lista.",
        )
 
    with loc_col2:
        if pais:
            cidade = st.selectbox(
                "Cidade de nascimento",
                options=_get_cities(pais),
                index=None,
                placeholder="Digite ou selecione…",
                key="cidade_select",
                help=(
                    "Selecione a cidade registrada na sua certidão. "
                    "Se sua cidade não aparecer, escolha a mais próxima "
                    "ou a sede do município."
                ),
            )
        else:
            st.selectbox(
                "Cidade de nascimento",
                options=[],
                disabled=True,
                placeholder="Selecione o país primeiro",
                key="cidade_select_disabled",
                help="Primeiro selecione o país para habilitar esta lista.",
            )
            cidade = None
 
    st.divider()
 
    # ── 3. Botão — fica depois de tudo ───────────────────────────────────────
 
    if st.button("✨ Gerar Mapa", type="primary", use_container_width=True):
 
        erros = []
        if not nome.strip():      erros.append("Informe os nomes próprios.")
        if not sobrenome.strip(): erros.append("Informe os sobrenomes.")
        if not pais:              erros.append("Selecione o país de nascimento.")
        if not cidade:            erros.append("Selecione a cidade de nascimento.")
 
        try:
            dia, mes, ano = map(int, data_str.strip().split("/"))
        except Exception:
            erros.append("Data inválida. Use o formato DD/MM/AAAA.")
            dia = mes = ano = None
 
        try:
            hrs, minuto = map(int, hora_str.strip().split(":"))
        except Exception:
            erros.append("Hora inválida. Use o formato HH:MM.")
            hrs = minuto = None
 
        if erros:
            for e in erros:
                st.error(e)
            st.session_state.pop("mapa_html", None)   # limpa resultado anterior
        else:
            with st.spinner("Calculando seu mapa…"):
                try:
                    st.session_state["mapa_html"] = renderizar(
                        nome.strip(), sobrenome.strip(),
                        cidade, pais,
                        dia, mes, ano, hrs, minuto,
                    )
                except ValueError as ve:
                    st.error(str(ve))
                    st.session_state.pop("mapa_html", None)
                except Exception:
                    import traceback
                    st.error("Ocorreu um erro inesperado:")
                    st.code(traceback.format_exc())
                    st.session_state.pop("mapa_html", None)
 
    # ── 4. Resultado — persiste entre reruns via session_state ────────────────
 
    if "mapa_html" in st.session_state:
        components.html(st.session_state["mapa_html"], height=3200, scrolling=True)
 
 
if __name__ == "__main__":
    main()
