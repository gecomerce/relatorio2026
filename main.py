import sys
import requests
import pandas as pd
import streamlit as st
import plotly_express as px
from io import BytesIO


st.set_page_config(layout="wide", page_icon= "📃", page_title= "Fechamento Gecomerce")

with open("style.css") as f:
    st.markdown(f"<style>{f.read()}</style>",unsafe_allow_html = True)

@st.cache_data
def load_data():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    API_TOKEN = "eyJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJQaXBlZnkiLCJpYXQiOjE3NTU4NjcwNDMsImp0aSI6IjU1MDBhMjA5LWZkMmUtNDRlNC05MzVlLWQ2NmM4NGI3ZmQ3NiIsInN1YiI6MzAxMDA4ODExLCJ1c2VyIjp7ImlkIjozMDEwMDg4MTEsImVtYWlsIjoiY29tZXJjaWFsQGdlY29tZXJjZS5jb20uYnIifX0.mnbZcuyfOpJxiTZOhLwTpQu4BAb1JsT88oQb8aCr6s9oFYIGD_SOUdVEvkXXZ40LmBeseP_gjm7z-pMQC9MzRw"
    ORG_ID = 300380850
    PIPE_NAME = "RELATORIOS MENSAIS 2026" 
    URL = "https://api.pipefy.com/graphql"

    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json",
    }

    query_pipes = f"""
    {{
      organization(id: {ORG_ID}) {{
        pipes {{
          id
          name
        }}
      }}
    }}
    """
    resp = requests.post(URL, json={"query": query_pipes}, headers=headers)
    pipes = resp.json().get("data", {}).get("organization", {}).get("pipes", [])


    pipe_id = None
    for pipe in pipes:
        if pipe["name"].strip().lower() == PIPE_NAME.strip().lower():
            pipe_id = pipe["id"]
            break

    if not pipe_id:
        st.error(f"Pipe '{PIPE_NAME}' não encontrado!")
        return pd.DataFrame()


    all_cards = []
    has_next_page = True
    after_cursor = None

    while has_next_page:
        cursor_str = f', after: "{after_cursor}"' if after_cursor else ""
        query_cards = f"""
        {{
          allCards(pipeId: {pipe_id}, first: 200{cursor_str}) {{
            pageInfo {{
              hasNextPage
              endCursor
            }}
            edges {{
              node {{
                id
                title
                createdAt
                assignees {{ name }}
                current_phase {{ name }}
                fields {{ name value }}
              }}
            }}
          }}
        }}
        """
        r = requests.post(URL, json={"query": query_cards}, headers=headers)
        j = r.json()

        data = j.get("data", {}).get("allCards", {})
        edges = data.get("edges", [])

        for edge in edges:
            node = edge["node"]
            card = {
                "card_id": node.get("id"),
                "title": node.get("title"),
                "created_at": node.get("createdAt"),
                "phase": node.get("current_phase", {}).get("name", ""),
            }

            for f in node.get("fields", []):
                card[f["name"]] = f.get("value")
            all_cards.append(card)

        page_info = data.get("pageInfo", {})
        has_next_page = page_info.get("hasNextPage", False)
        after_cursor = page_info.get("endCursor")

    df = pd.DataFrame(all_cards)
    return df


# -----------------------------------------------------------------------------

df = load_data()
df = df.rename(columns={"EMPRESAS ": "EMPRESAS"})


col = 'VALOR TOTAL DA NOTA FISCAL'

df[col] = (
    df[col]
    .astype(str)
    .str.replace('R\$', '', regex=True)
    .str.replace('.', '', regex=False)
    .str.replace(',', '.', regex=False)
    .str.strip()
)


df["VALOR PEDIDO DE TRANSFERENCIA "] = pd.to_numeric(
    df["VALOR PEDIDO DE TRANSFERENCIA "]
    .astype(str)
    .str.replace("R$", "", regex=False)
    .str.replace(".", "", regex=False)
    .str.replace(",", ".", regex=False)
    .str.strip(),
    errors="coerce"
)


meses = ["JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"]


# ------------------------------------------------------------------------
# LAYOUT

st.title("Fechamento Gecomerce 2026", anchor=False)
st.divider()


# with tab1:
card1, card2, card4 = st.columns([2,2,1.2])
coluna_faturamento_mensal, = st.columns(1)
container_produtor, = st.columns(1)
st.divider()
coluna4, = st.columns(1)
# -------------------------------------------------------------------------

with card4:
    mes = st.selectbox("Mês", meses)


df_filtered = df[df["MÊS "] == mes].reset_index(drop=True)


with coluna4:
    empresa = st.multiselect("Empresas", df_filtered["EMPRESAS"].unique(),default=df_filtered["EMPRESAS"].unique())

df_produtores = df_filtered.groupby(['NOME DO PRODUTOR RURAL','EMPRESAS'])['VALOR PEDIDO DE TRANSFERENCIA '].sum().reset_index()
df_produtores = df_produtores.sort_values(by= "VALOR PEDIDO DE TRANSFERENCIA ", ascending= False)

with container_produtor:
    empresa_filtro = st.multiselect("Selecione Empresas", df_filtered["EMPRESAS"].unique(),default=df_filtered["EMPRESAS"].unique())
    df_produtores = df_produtores.query('EMPRESAS == @empresa_filtro')
    total_produtores_df = df_produtores["VALOR PEDIDO DE TRANSFERENCIA "].sum()

df_produtores["VALOR PEDIDO DE TRANSFERENCIA "] = df_produtores["VALOR PEDIDO DE TRANSFERENCIA "].apply(
    lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

with container_produtor:
    st.subheader("Produtor Por Empresa", anchor=False)
    st.dataframe(df_produtores)
    st.text(total_produtores_df)

df_produtores_por_empresa = df_filtered.query('EMPRESAS == @empresa')
df_produtores_por_empresa = df_produtores_por_empresa.drop(columns=['title','card_id','VALOR NOTA FISCALYOSHIDA ',
                                                                    'created_at','phase'])





def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Produtores")
    return output.getvalue()


with coluna4:

    st.dataframe(df_produtores_por_empresa)

    df_excel = df_produtores_por_empresa.copy()

    colunas_valor = [
        "VALOR DO PEDIDO DE TRANSFERÊNCIA ",
        "VALOR TOTAL DA NOTA FISCAL"
    ]

    for col in colunas_valor:
        if col in df_excel.columns:

            if df_excel[col].dtype == object:
                df_excel[col] = (
                    df_excel[col]
                    .astype(str)
                    .str.replace(",", ".", regex=False)
                )

            df_excel[col] = pd.to_numeric(df_excel[col], errors="coerce")

            df_excel[col] = df_excel[col].apply(
                lambda x: f"{x:.2f}".replace(".", ",") if pd.notnull(x) else ""
            )


    excel_bytes = to_excel(df_excel)


    st.download_button(
        label="Baixar Planilha",
        data=excel_bytes,
        file_name=f"produtores_{empresa}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )



# ------------------------------------------------------------------------------
# KPIs

qtd_operacoes = df_filtered.shape[0]


# -------------------------------------------------------------------------------
# FATURAMENTO MENSAL GRAFICO

df_faturamento_mensal = df_filtered.groupby(["MÊS "])["VALOR PEDIDO DE TRANSFERENCIA "].sum().reset_index()


df_faturamento_por_empresa = df_filtered.groupby(["EMPRESAS"])["VALOR PEDIDO DE TRANSFERENCIA "].sum().reset_index()
df_faturamento_por_empresa = df_faturamento_por_empresa.sort_values(by= "VALOR PEDIDO DE TRANSFERENCIA ", ascending= False)


df_faturamento_por_empresa["VALOR_FORMATADO"] = df_faturamento_por_empresa["VALOR PEDIDO DE TRANSFERENCIA "].apply(
    lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
)


bar_chart_mensal = px.bar(df_faturamento_por_empresa, x= "EMPRESAS", y= "VALOR PEDIDO DE TRANSFERENCIA ", text="VALOR_FORMATADO",
            color_discrete_sequence=["#0270AF"])

bar_chart_mensal.update_layout(
    xaxis_title=None,
    yaxis_title=None,
    xaxis=dict(
        showgrid=False,
        showline=False
    ),
    yaxis=dict(
        showgrid=False,
        showline=False
    )
)


bar_chart_mensal.update_traces(
    textposition="outside"
)


with coluna_faturamento_mensal:
    st.subheader("Valor Por Empresa", anchor= False)
    st.plotly_chart(bar_chart_mensal, use_container_width= True)

# ----------------------------------------------------------------------------

total = df_filtered["VALOR PEDIDO DE TRANSFERENCIA "].sum()

with card1:
    st.metric("Total Valor",f"R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

with card2:
    st.metric("QTD Operações", qtd_operacoes)


if st.button("Atualizar"):
    st.cache_data.clear()
    load_data()

# --------------------------------------------------------------------------------

borda = """
            <style>
            [data-testid="column"]
            {
            background-color: #fff;
            border-radius: 15px;
            padding: 10px;
            text-align: center;
            opacity: 100%;
            box-shadow: 5px 8px 25px -3px rgba(0,0,0,0.75);
            }
            </style>
            """

st.markdown(borda, unsafe_allow_html=True)  

hide_header = """
    <style>
        header {visibility: hidden;}
    </style>
"""
st.markdown(hide_header, unsafe_allow_html=True)
