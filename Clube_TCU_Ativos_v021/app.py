
import re
import unicodedata
from datetime import date, timedelta, datetime

import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="Clube TCU Ativos",
    page_icon="🏃",
    layout="wide",
)


# -----------------------------
# Funções de apoio
# -----------------------------
MESES_PT = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3,
    "abril": 4, "maio": 5, "junho": 6, "julho": 7,
    "agosto": 8, "setembro": 9, "outubro": 10,
    "novembro": 11, "dezembro": 12,
}

MESES_EN = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}

MARCADORES = {
    "distância", "distance", "tempo", "time", "ritmo", "pace",
    "velocidade", "speed", "fc méd", "avg hr", "cal",
    "ganho de elev.", "elev gain", "passos", "sets",
}


def sem_acentos(s):
    return "".join(
        c for c in unicodedata.normalize("NFKD", str(s))
        if not unicodedata.combining(c)
    )


def chave_nome(nome):
    """
    Cria chave estável para cruzamento com a tabela de equipes.
    Remove emojis/pontuação, ignora acentos e diferença entre maiúsculas/minúsculas.
    """
    s = sem_acentos(str(nome)).casefold()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_data_linha(linha, data_referencia):
    s = linha.strip()

    if re.search(r"^Hoje\s+às\s+\d{1,2}:\d{2}", s, flags=re.I):
        return data_referencia

    if re.search(r"^Ontem\s+às\s+\d{1,2}:\d{2}", s, flags=re.I):
        return data_referencia - timedelta(days=1)

    m = re.search(
        r"(\d{1,2})\s+de\s+([A-Za-zÀ-ÿ]+)\s+de\s+(\d{4})\s+às\s+\d{1,2}:\d{2}",
        s,
        flags=re.I,
    )
    if m:
        dia = int(m.group(1))
        mes_txt = sem_acentos(m.group(2)).lower()
        ano = int(m.group(3))
        mes = MESES_PT.get(mes_txt)
        if mes:
            return date(ano, mes, dia)

    m = re.search(
        r"([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})\s+at\s+\d{1,2}:\d{2}\s*(AM|PM)?",
        s,
        flags=re.I,
    )
    if m:
        mes = MESES_EN.get(m.group(1).lower())
        if mes:
            return date(int(m.group(3)), mes, int(m.group(2)))

    return None


def duracao_para_segundos(txt):
    """
    Aceita, entre outros:
    48min 40s | 1h 9min | 46m 32s | 1h 0m | 34min 0s
    """
    s = str(txt).strip().lower()
    horas = minutos = segundos = 0

    mh = re.search(r"(\d+)\s*h", s)
    if mh:
        horas = int(mh.group(1))

    # "min" e "m" são aceitos, desde que não seja o "m" de km/métrica.
    mm = re.search(r"(\d+)\s*(?:min|m)(?![a-z])", s)
    if mm:
        minutos = int(mm.group(1))

    ms = re.search(r"(\d+)\s*s", s)
    if ms:
        segundos = int(ms.group(1))

    total = horas * 3600 + minutos * 60 + segundos
    return total if total > 0 else None


def segundos_para_hms(segundos):
    if pd.isna(segundos):
        return ""
    segundos = int(round(segundos))
    h, resto = divmod(segundos, 3600)
    m, s = divmod(resto, 60)
    if h:
        return f"{h}h {m:02d}min {s:02d}s"
    return f"{m}min {s:02d}s"


def extrair_atividades(texto, data_referencia):
    """
    Procura blocos cuja primeira linha seja um nome e a linha seguinte
    contenha uma data/hora válida de atividade.

    Comentários como:
        Mauricio Orlandi
        há 4 dias
        ...
    não entram porque a segunda linha não é uma data/hora de atividade.
    """
    linhas = texto.splitlines()
    registros = []

    inicios = []
    for i in range(len(linhas) - 1):
        d = parse_data_linha(linhas[i + 1], data_referencia)
        if d:
            nome = linhas[i].strip()
            if nome:
                inicios.append((i, d))

    for pos, (i, data_atividade) in enumerate(inicios):
        fim = inicios[pos + 1][0] if pos + 1 < len(inicios) else len(linhas)
        nome = linhas[i].strip()

        # Exige marcador Tempo/Time dentro do bloco.
        idx_tempo = None
        for k in range(i + 2, fim):
            if linhas[k].strip().lower() in {"tempo", "time"}:
                idx_tempo = k
                break

        if idx_tempo is None:
            continue

        duracao_txt = None
        for k in range(idx_tempo + 1, min(fim, idx_tempo + 4)):
            candidato = linhas[k].strip()
            if candidato:
                duracao_txt = candidato
                break

        duracao_s = duracao_para_segundos(duracao_txt)
        if duracao_s is None:
            continue

        # O título da atividade é a última linha útil imediatamente
        # anterior ao primeiro marcador de métrica.
        primeiro_marcador = None
        for k in range(i + 2, idx_tempo + 1):
            if linhas[k].strip().lower() in MARCADORES:
                primeiro_marcador = k
                break

        if primeiro_marcador is None:
            continue

        atividade = None
        for k in range(primeiro_marcador - 1, i + 1, -1):
            candidato = linhas[k].strip()
            if candidato and candidato != "·":
                atividade = candidato
                break

        if not atividade:
            continue

        registros.append({
            "NOME_ATLETA_ORIGINAL": nome,
            "DATA": data_atividade,
            "ATIVIDADE": atividade,
            "DURACAO_ORIGINAL": duracao_txt,
            "DURACAO_SEGUNDOS": duracao_s,
            "DURACAO_MINUTOS": round(duracao_s / 60, 2),
            "CHAVE_NOME": chave_nome(nome),
        })

    return pd.DataFrame(registros)


def bonus_engajamento(percentual):
    if percentual >= 100:
        return 5
    if percentual >= 90:
        return 3
    if percentual >= 70:
        return 2
    if percentual >= 50:
        return 1
    return 0


def carregar_equipes(upload=None):
    if upload is not None:
        df = pd.read_csv(upload)
    else:
        df = pd.read_csv("equipes.csv")

    colunas = {c.upper().strip(): c for c in df.columns}
    if "NOME_ATLETA" not in colunas or "EQUIPE" not in colunas:
        raise ValueError("A tabela de equipes deve conter as colunas NOME_ATLETA e EQUIPE.")

    df = df.rename(columns={
        colunas["NOME_ATLETA"]: "NOME_ATLETA",
        colunas["EQUIPE"]: "EQUIPE",
    })[["NOME_ATLETA", "EQUIPE"]].copy()

    df["CHAVE_NOME"] = df["NOME_ATLETA"].map(chave_nome)
    return df


# -----------------------------
# Interface
# -----------------------------
st.title("🏃 Clube TCU Ativos")
st.caption("Apuração por participação diária — versão 0.2 (entrada por TXT)")

with st.sidebar:
    st.header("Entrada de dados")

    arquivo_txt = st.file_uploader(
        "TXT bruto copiado do Strava",
        type=["txt"],
        help="Cole a listagem exatamente como aparece e salve em TXT. O sistema faz a limpeza.",
    )

    data_ref = st.date_input(
        "Data de referência do TXT",
        value=date.today(),
        help="Usada para interpretar as expressões “Hoje” e “Ontem”.",
    )

    arquivo_equipes = st.file_uploader(
        "Tabela de equipes (opcional)",
        type=["csv"],
        help="Se não enviar outra, será usado o arquivo equipes.csv do projeto.",
    )

    st.divider()
    st.markdown(
        "**Regra:** 1 participante + 1 dia ativo = **1 ponto** para a equipe. "
        "Várias atividades no mesmo dia continuam valendo 1 ponto."
    )


try:
    equipes = carregar_equipes(arquivo_equipes)
except Exception as e:
    st.error(f"Erro na tabela de equipes: {e}")
    st.stop()


if arquivo_txt is None:
    st.info("Envie o TXT bruto na barra lateral para iniciar a apuração.")
    st.stop()


conteudo = arquivo_txt.getvalue().decode("utf-8-sig", errors="replace")
atividades = extrair_atividades(conteudo, data_ref)

if atividades.empty:
    st.error("Não consegui identificar atividades válidas no TXT.")
    st.stop()


# Cruza o nome do TXT com o cadastro fixo.
atividades = atividades.merge(
    equipes[["CHAVE_NOME", "NOME_ATLETA", "EQUIPE"]],
    on="CHAVE_NOME",
    how="left",
)

atividades["NOME_ATLETA"] = atividades["NOME_ATLETA"].fillna(
    atividades["NOME_ATLETA_ORIGINAL"].map(
        lambda x: re.sub(r"\s+", " ", re.sub(r"[^\wÀ-ÿ .'-]+", "", x)).strip()
    )
)
atividades["EQUIPE"] = atividades["EQUIPE"].fillna("NÃO CADASTRADO")


nao_cadastrados = (
    atividades.loc[atividades["EQUIPE"] == "NÃO CADASTRADO", "NOME_ATLETA_ORIGINAL"]
    .drop_duplicates()
    .tolist()
)

if nao_cadastrados:
    st.warning(
        "Há atleta(s) sem equipe cadastrada: " + ", ".join(nao_cadastrados)
    )


# -----------------------------
# Check-ins: 1 atleta/dia = 1 ponto
# -----------------------------
checkins = (
    atividades.groupby(["DATA", "NOME_ATLETA", "EQUIPE"], as_index=False)
    .agg(
        NUM_ATIVIDADES=("ATIVIDADE", "size"),
        DURACAO_TOTAL_SEGUNDOS=("DURACAO_SEGUNDOS", "sum"),
    )
)

checkins["PONTO_BASE"] = 1
checkins["DURACAO_TOTAL"] = checkins["DURACAO_TOTAL_SEGUNDOS"].map(segundos_para_hms)


# Tamanho de cada equipe conforme cadastro.
tam_equipes = (
    equipes.groupby("EQUIPE", as_index=False)
    .agg(TOTAL_INTEGRANTES=("NOME_ATLETA", "nunique"))
)

apuracao_dia = (
    checkins.loc[checkins["EQUIPE"] != "NÃO CADASTRADO"]
    .groupby(["DATA", "EQUIPE"], as_index=False)
    .agg(
        ATIVOS=("NOME_ATLETA", "nunique"),
        ATIVIDADES=("NUM_ATIVIDADES", "sum"),
        DURACAO_SEGUNDOS=("DURACAO_TOTAL_SEGUNDOS", "sum"),
    )
)

# Cria todas as combinações data x equipe, inclusive dias sem atividade.
datas = pd.DataFrame({"DATA": sorted(checkins["DATA"].unique())})
grade = datas.assign(_k=1).merge(tam_equipes.assign(_k=1), on="_k").drop(columns="_k")

apuracao_dia = grade.merge(apuracao_dia, on=["DATA", "EQUIPE"], how="left")
for c in ["ATIVOS", "ATIVIDADES", "DURACAO_SEGUNDOS"]:
    apuracao_dia[c] = apuracao_dia[c].fillna(0)

apuracao_dia["ATIVOS"] = apuracao_dia["ATIVOS"].astype(int)
apuracao_dia["ATIVIDADES"] = apuracao_dia["ATIVIDADES"].astype(int)

apuracao_dia["ENGAJAMENTO_%"] = (
    apuracao_dia["ATIVOS"] / apuracao_dia["TOTAL_INTEGRANTES"] * 100
).round(1)

apuracao_dia["BONUS"] = apuracao_dia["ENGAJAMENTO_%"].map(bonus_engajamento)
apuracao_dia["PONTOS_DO_DIA"] = apuracao_dia["ATIVOS"] + apuracao_dia["BONUS"]
apuracao_dia["DURACAO_TOTAL"] = apuracao_dia["DURACAO_SEGUNDOS"].map(segundos_para_hms)


ranking_equipes = (
    apuracao_dia.groupby("EQUIPE", as_index=False)
    .agg(
        PONTOS=("PONTOS_DO_DIA", "sum"),
        PONTOS_BASE=("ATIVOS", "sum"),
        BONUS=("BONUS", "sum"),
        DIAS_PESSOA=("ATIVOS", "sum"),
        ATIVIDADES=("ATIVIDADES", "sum"),
    )
    .sort_values(["PONTOS", "PONTOS_BASE", "ATIVIDADES"], ascending=False)
    .reset_index(drop=True)
)
ranking_equipes.index = ranking_equipes.index + 1
ranking_equipes.insert(0, "POSICAO", ranking_equipes.index)


ranking_individual = (
    atividades.groupby(["NOME_ATLETA", "EQUIPE"], as_index=False)
    .agg(
        DIAS_ATIVOS=("DATA", "nunique"),
        ATIVIDADES=("ATIVIDADE", "size"),
        DURACAO_SEGUNDOS=("DURACAO_SEGUNDOS", "sum"),
    )
    .sort_values(
        ["DIAS_ATIVOS", "ATIVIDADES", "DURACAO_SEGUNDOS"],
        ascending=False,
    )
    .reset_index(drop=True)
)
ranking_individual.index = ranking_individual.index + 1
ranking_individual.insert(0, "POSICAO", ranking_individual.index)
ranking_individual["DURACAO_TOTAL"] = ranking_individual["DURACAO_SEGUNDOS"].map(segundos_para_hms)


# -----------------------------
# Painel
# -----------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Atividades identificadas", len(atividades))
c2.metric("Participantes ativos", atividades["NOME_ATLETA"].nunique())
c3.metric("Check-ins (dias-pessoa)", len(checkins))
c4.metric("Dias no arquivo", atividades["DATA"].nunique())


aba1, aba2, aba3, aba4 = st.tabs([
    "🏆 Ranking das equipes",
    "📅 Apuração diária",
    "👤 Participação individual",
    "🧹 Dados tratados",
])


with aba1:
    st.subheader("Ranking acumulado")
    st.dataframe(
        ranking_equipes[
            ["POSICAO", "EQUIPE", "PONTOS", "PONTOS_BASE", "BONUS", "ATIVIDADES"]
        ],
        use_container_width=True,
        hide_index=True,
    )

    graf = ranking_equipes.set_index("EQUIPE")[["PONTOS"]]
    st.bar_chart(graf)


with aba2:
    st.subheader("Pontuação por dia e equipe")
    exibir = apuracao_dia.copy()
    exibir["DATA"] = pd.to_datetime(exibir["DATA"]).dt.strftime("%d/%m/%Y")
    st.dataframe(
        exibir[
            [
                "DATA", "EQUIPE", "TOTAL_INTEGRANTES", "ATIVOS",
                "ENGAJAMENTO_%", "BONUS", "PONTOS_DO_DIA",
                "ATIVIDADES", "DURACAO_TOTAL",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )


with aba3:
    st.subheader("Participação individual")
    st.caption(
        "Ordenação demonstrativa: dias ativos → número de atividades → duração total. "
        "Os critérios finais de premiação podem ser alterados depois."
    )
    st.dataframe(
        ranking_individual[
            [
                "POSICAO", "NOME_ATLETA", "EQUIPE",
                "DIAS_ATIVOS", "ATIVIDADES", "DURACAO_TOTAL",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )


with aba4:
    st.subheader("Atividades extraídas do TXT")
    tratados = atividades[
        [
            "NOME_ATLETA", "EQUIPE", "DATA", "ATIVIDADE",
            "DURACAO_ORIGINAL", "DURACAO_MINUTOS",
        ]
    ].copy()
    tratados["DATA"] = pd.to_datetime(tratados["DATA"]).dt.strftime("%d/%m/%Y")
    st.dataframe(tratados, use_container_width=True, hide_index=True)

    st.download_button(
        "Baixar atividades tratadas (CSV)",
        data=tratados.to_csv(index=False).encode("utf-8-sig"),
        file_name="atividades_tratadas.csv",
        mime="text/csv",
    )

    st.download_button(
        "Baixar check-ins diários (CSV)",
        data=checkins.drop(columns=["DURACAO_TOTAL_SEGUNDOS"])
        .to_csv(index=False)
        .encode("utf-8-sig"),
        file_name="checkins_diarios.csv",
        mime="text/csv",
    )


st.divider()
st.caption(
    "O TXT bruto é processado durante a sessão. O aplicativo trabalha com os campos "
    "necessários para a apuração: atleta, data, atividade, duração e equipe."
)
