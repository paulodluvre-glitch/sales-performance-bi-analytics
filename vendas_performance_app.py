import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(page_title="Relatório de Performance de Vendas - Morana", layout="wide")

estilo_impressao = """
<style>
@media print {
    /* 1. DESTRAVA O LAYOUT (Corrige o erro de ficar só o título e a página em branco) */
    body, html, #root, .appview-container, .main, .block-container, [data-testid="stVerticalBlock"], [data-testid="stTabs"] {
        height: auto !important;
        max-height: none !important;
        overflow: visible !important;
        display: block !important;
    }

    /* 2. ESCONDE O QUE NÃO DEVE APARECER NO PDF */
    [data-testid="stSidebar"],          /* Barra lateral (Filtros) */
    [data-testid="stFileUploader"],     /* Caixa de arrastar arquivo */
    .stButton,                          /* Botões (Gerar Dashboard) */
    header,                             /* Topo padrão do sistema */
    footer,                             /* Rodapé padrão do sistema */
    [data-testid="stTabs"] button       /* Botões superiores das Abas */
    { 
        display: none !important; 
    }
    
    /* 3. TIRA AS MARGENS MORTAS PARA APROVEITAR O PAPEL */
    .block-container { 
        padding-top: 0rem !important; 
    }
    
    /* 4. DIMINUI O TÍTULO PARA CABER EM UMA LINHA SÓ */
    h1 {
        font-size: 33px !important; /* Se ainda quebrar linha, diminua para 30px ou 28px */
        margin-top: -20px !important; /* Puxa ele um pouco mais pro topo da folha */
    }
}
</style>
"""
st.markdown(estilo_impressao, unsafe_allow_html=True)

@st.cache_data
def tratar_base_bruta(arquivos):
    lista_df = []
    for arquivo in arquivos:
        df_temp = pd.read_excel(arquivo)
        df_temp.columns = df_temp.columns.str.strip().str.lower()
        lista_df.append(df_temp)
        
    df = pd.concat(lista_df, ignore_index=True)
    
    colunas_moeda = ['valor', 'valor_base_calculo_comissao', 'desconto', 'acrescimo']
    for col in colunas_moeda:
        if col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.replace('R$', '', regex=False) \
                                             .str.replace('.', '', regex=False) \
                                             .str.replace(',', '.', regex=False).str.strip()
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

    if 'quantidade' in df.columns:
        df['quantidade'] = pd.to_numeric(df['quantidade'], errors='coerce').fillna(0).astype(int)

    if 'data' in df.columns:
        df['data'] = pd.to_datetime(df['data'], errors='coerce')
        df = df.dropna(subset=['data'])
        
        df['dia'] = df['data'].dt.day
        df['ano'] = df['data'].dt.year
        df['mes_num'] = df['data'].dt.month
        
        meses_map = {1:'Janeiro', 2:'Fevereiro', 3:'Março', 4:'Abril', 5:'Maio', 6:'Junho', 7:'Julho', 8:'Agosto', 9:'Setembro', 10:'Outubro', 11:'Novembro', 12:'Dezembro'}
        df['mês'] = df['mes_num'].map(meses_map)
        
        dias_semana = {0: 'Segunda-feira', 1: 'Terça-feira', 2: 'Quarta-feira', 3: 'Quinta-feira', 4: 'Sexta-feira', 5: 'Sábado', 6: 'Domingo'}
        df['dia semana'] = df['data'].dt.dayofweek.map(dias_semana)
        
        cond_descendio = [(df['dia'] <= 10), (df['dia'] > 10) & (df['dia'] <= 20), (df['dia'] > 20)]
        df['descêndio'] = np.select(cond_descendio, ['1º Descêndio', '2º Descêndio', '3º Descêndio'])

    if 'data' in df.columns and 'nrovenda' in df.columns:
        df['id_venda'] = df['data'].dt.strftime('%Y-%m-%d') + '-' + df['nrovenda'].astype(str)
    else:
        df['id_venda'] = df.index.astype(str)

    if 'valor_base_calculo_comissao' in df.columns:
        df['valor_liquido_item'] = df['valor_base_calculo_comissao']
    elif 'valor' in df.columns:
        df['valor_liquido_item'] = df['valor']
    else:
        df['valor_liquido_item'] = 0.0

    if 'id_venda' in df.columns:
        df = df.sort_values(by=['data', 'id_venda'])
        df['soma_total_da_venda'] = df.groupby('id_venda')['valor_liquido_item'].transform('sum')
        df['flag_venda_principal'] = np.where(df.duplicated(subset=['id_venda']), 0, 1)
        df['faturamento_venda_unica'] = np.where(df['flag_venda_principal'] == 1, df['soma_total_da_venda'], 0.0)

    return df

def converter_df_para_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Base Consolidada')
    return output.getvalue()

st.title("Relatório de Performance de Vendas - Morana")

aba1, aba2 = st.tabs(["⚙️ 1. Fábrica de Dados", "📈 2. Gerador de Relatório"])

with aba1:
    st.header("Tratamento e Consolidação da Base")
    st.write("Suba os arquivos originais do CRM aqui.")
    arquivos_brutos = st.file_uploader("Arraste as planilhas do CRM (Brutas)", accept_multiple_files=True, type=['xlsx'], key="up_bruto")
    
    if arquivos_brutos:
        with st.spinner("Processando..."):
            df_consolidado = tratar_base_bruta(arquivos_brutos)
            st.success("Base processada com sucesso!")
            excel_data = converter_df_para_excel(df_consolidado)
            st.download_button("📥 Baixar Base Consolidada", data=excel_data, file_name="Base_Consolidada_Morana.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with aba2:
    st.header("Gerador do Relatório Analítico")
    st.write("Faça o upload da **Base Consolidada** para gerar o Dashboard.")
    
    arquivo_consolidado = st.file_uploader("Arraste a Base Consolidada (Excel)", type=['xlsx'], key="up_consolidado")
    
    if arquivo_consolidado:
        df_base = pd.read_excel(arquivo_consolidado)
        
        st.sidebar.header("Filtros do Relatório")
        anos_disponiveis = sorted(df_base['ano'].dropna().unique(), reverse=True)
        ano_selecionado = st.sidebar.selectbox("Ano de Análise", anos_disponiveis)
        
        meses_disponiveis = df_base[df_base['ano'] == ano_selecionado]['mês'].dropna().unique()
        mes_selecionado = st.sidebar.selectbox("Mês de Análise", meses_disponiveis)
        
        if st.sidebar.button("Gerar Dashboard"):
            st.divider()
            
            mes_num_atual = df_base[(df_base['ano'] == ano_selecionado) & (df_base['mês'] == mes_selecionado)]['mes_num'].iloc[0]
            
            st.subheader("1. COMPARATIVO VISÃO GERAL (Últimos 3 Meses)")
            st.write("Análise da evolução de vendas líquidas e volume de peças.")
            
            df_base['AnoMes_str'] = df_base['ano'].astype(str) + '-' + df_base['mes_num'].astype(str).str.zfill(2)
            anomes_alvo = f"{ano_selecionado}-{str(mes_num_atual).zfill(2)}"
            
            ultimos_3_anomes = sorted(df_base[df_base['AnoMes_str'] <= anomes_alvo]['AnoMes_str'].unique())[-3:]
            df_3m = df_base[df_base['AnoMes_str'].isin(ultimos_3_anomes)]
            
            resumo_3m = df_3m.groupby(['AnoMes_str', 'mês'], as_index=False).agg(
                Pecas=('quantidade', 'sum'),
                Faturamento=('faturamento_venda_unica', 'sum')
            ).sort_values('AnoMes_str')
            
            tendencias = []
            for i in range(len(resumo_3m)):
                if i == 0:
                    tendencias.append("Base Inicial")
                else:
                    tendencias.append("Crescimento" if resumo_3m['Faturamento'].iloc[i] > resumo_3m['Faturamento'].iloc[i-1] else "Queda")
            
            if len(resumo_3m) > 1 and resumo_3m['Faturamento'].iloc[-1] == resumo_3m['Faturamento'].max():
                tendencias[-1] = "Recorde de Faturamento"
                
            resumo_3m['Tendência'] = tendencias
            
            tabela_3m = resumo_3m[['mês', 'Pecas', 'Faturamento', 'Tendência']].copy()
            tabela_3m.columns = ['Mês', 'Peças Vendidas', 'Valor Líquido (R$)', 'Tendência']
            st.dataframe(tabela_3m.style.format({'Valor Líquido (R$)': 'R$ {:,.2f}'}), hide_index=True, use_container_width=True)
            
            st.markdown("**Destaques:**")
            if len(resumo_3m) >= 2:
                fat_atual = float(resumo_3m['Faturamento'].iloc[-1])
                fat_ant = float(resumo_3m['Faturamento'].iloc[-2])
                pecas_atual = int(resumo_3m['Pecas'].iloc[-1])
                pecas_ant = int(resumo_3m['Pecas'].iloc[-2])
                
                diff_fat = fat_atual - fat_ant
                if fat_atual > fat_ant and pecas_atual < pecas_ant:
                    st.markdown(f"• **Faturamento vs. Volume:** Embora o volume de peças em {mes_selecionado} ({pecas_atual}) tenha sido ligeiramente menor que no mês anterior ({pecas_ant}), o Faturamento Líquido aumentou mais de R$ {diff_fat:,.2f}. Isso indica venda de produtos de maior valor agregado.")
                elif fat_atual > fat_ant and pecas_atual >= pecas_ant:
                    st.markdown(f"• **Faturamento vs. Volume:** O mês apresentou forte crescimento tanto em volume de peças ({pecas_atual}) quanto em faturamento (aumento de R$ {diff_fat:,.2f}), demonstrando uma excelente performance geral.")
                else:
                    st.markdown(f"• **Faturamento vs. Volume:** O mês de {mes_selecionado} apresentou um recuo de R$ {abs(diff_fat):,.2f} no faturamento. Uma oportunidade para revisar estratégias de ticket médio e volume nos próximos períodos.")
                
                fat_inicial = float(resumo_3m['Faturamento'].iloc[0])
                if fat_atual > fat_inicial:
                    st.markdown(f"• **Crescimento Trimestral:** A loja saiu de um patamar de R$ {fat_inicial/1000:.0f}k para R$ {fat_atual/1000:.0f}k no período analisado.")
                else:
                    st.markdown(f"• **Oscilação Trimestral:** O trimestre começou em R$ {fat_inicial/1000:.0f}k e fechou o mês atual em R$ {fat_atual/1000:.0f}k.")


            
            st.divider()
            st.subheader(f"2. COMPARATIVO ANUAL ({mes_selecionado} {ano_selecionado-1} vs. {ano_selecionado})")
            st.write("Confronto direto para medir o crescimento real da operação.")

            df_atual = df_base[(df_base['ano'] == ano_selecionado) & (df_base['mês'] == mes_selecionado)]
            df_passado = df_base[(df_base['ano'] == ano_selecionado - 1) & (df_base['mês'] == mes_selecionado)]

            def calcular_kpis(df_periodo):
                vendas = df_periodo['id_venda'].nunique() 
                pecas = df_periodo['quantidade'].sum()
                fat = df_periodo['faturamento_venda_unica'].sum()
                pa = pecas / vendas if vendas > 0 else 0
                tkm = fat / vendas if vendas > 0 else 0
                return vendas, pa, tkm, fat

            vendas_atual, pa_atual, tkm_atual, fat_atual = calcular_kpis(df_atual)
            vendas_passado, pa_passado, tkm_passado, fat_passado = calcular_kpis(df_passado)

            def var_str(atual, passado, tipo='int'):
                if passado == 0: return "Sem Base Comparativa"
                diff = atual - passado
                if tipo == 'moeda': 
                    return f"🟢 Aumento de ~R$ {diff:,.2f}" if diff > 0 else f"🔴 Queda de ~R$ {abs(diff):,.2f}"
                elif tipo == 'float': 
                    return f"🟢 + {diff:,.2f}" if diff > 0 else (f"🔴 ▼ Leve Queda" if diff >= -0.1 else f"🔴 - {abs(diff):,.2f}")
                else:
                    return f"🟢 + {int(diff)} Atendimentos" if diff > 0 else f"🔴 {int(diff)} Atendimentos"

            perc_fat = ((fat_atual / fat_passado) - 1) * 100 if fat_passado > 0 else 0
            status_fat = f"🟢 Crescimento de +{perc_fat:.1f}%" if perc_fat > 0 else f"🔴 Queda de {abs(perc_fat):.1f}%"

            dados_comp = {
                "Indicador": ["Vendas (Atendimentos)", "Peças por Atendimento (P.A)", "Ticket Médio (TKM)", "FATURAMENTO LÍQUIDO"],
                f"{mes_selecionado} {ano_selecionado-1}": [
                    vendas_passado, 
                    f"{pa_passado:.2f}".replace('.', ','), 
                    f"R$ {tkm_passado:,.2f}", 
                    f"R$ {fat_passado:,.2f}"
                ],
                f"{mes_selecionado} {ano_selecionado}": [
                    vendas_atual, 
                    f"{pa_atual:.2f}".replace('.', ','), 
                    f"R$ {tkm_atual:,.2f}", 
                    f"R$ {fat_atual:,.2f}"
                ],
                "Variação / Status": [
                    var_str(vendas_atual, vendas_passado, 'int'),
                    var_str(pa_atual, pa_passado, 'float'),
                    var_str(tkm_atual, tkm_passado, 'moeda'),
                    status_fat if fat_passado > 0 else "Sem Base"
                ]
            }
            
            st.table(pd.DataFrame(dados_comp))

            if fat_passado > 0:
                var_fat_rs = fat_atual - fat_passado
                texto_analise = f"O {'crescimento' if var_fat_rs > 0 else 'recuo'} de R$ {abs(var_fat_rs):,.2f} em relação ao ano anterior foi impulsionado "
                
                if vendas_atual > vendas_passado:
                    texto_analise += f"pelo aumento expressivo no fluxo de clientes (+{vendas_atual - vendas_passado} vendas) "
                else:
                    texto_analise += f"apesar da queda no fluxo de clientes ({vendas_atual - vendas_passado} vendas) "
                    
                if tkm_atual > tkm_passado:
                    texto_analise += f"e valorização do ticket médio"
                else:
                    texto_analise += f"e retração no ticket médio"
                    
                if pa_atual < pa_passado:
                    texto_analise += ", apesar de uma leve oscilação no P.A."
                else:
                    texto_analise += ", com sustentação no volume de peças por atendimento (P.A)."
                
                st.markdown(f"**Análise:**\n• {texto_analise}")

            st.divider()
            st.subheader(f"3. MAPA DE CALOR ({mes_selecionado} {ano_selecionado})")
            st.write("Comportamento de vendas por dia da semana.")

            ordem_dias = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo']
            
            df_heat = df_atual.groupby('dia semana').agg(
                Peças=('quantidade', 'sum'),
                Vendas=('id_venda', 'nunique'),
                Faturamento=('faturamento_venda_unica', 'sum')
            ).reindex(ordem_dias).dropna().reset_index()
            
            df_heat['P.A.'] = (df_heat['Peças'] / df_heat['Vendas']).fillna(0)
            df_heat['Ticket Médio'] = (df_heat['Faturamento'] / df_heat['Vendas']).fillna(0)

            fat_total_mes = df_heat['Faturamento'].sum()
            
            if not df_heat.empty and fat_total_mes > 0:
                dia_max_fat = df_heat.loc[df_heat['Faturamento'].idxmax()]
                dia_max_tkm = df_heat.loc[df_heat['Ticket Médio'].idxmax()]
                dia_max_pa = df_heat.loc[df_heat['P.A.'].idxmax()]
                dia_min_venda = df_heat.loc[df_heat['Vendas'].idxmin()]
                
                perc_max_fat = (dia_max_fat['Faturamento'] / fat_total_mes) * 100
                
                st.markdown(f"🔥 **Dia de Maior Faturamento:** {dia_max_fat['dia semana']} (R$ {dia_max_fat['Faturamento']:,.2f} e {int(dia_max_fat['Vendas'])} atendimentos). Representa sozinho {perc_max_fat:.0f}% da venda do mês.")
                st.markdown(f"💎 **Melhor Ticket Médio:** {dia_max_tkm['dia semana']} (R$ {dia_max_tkm['Ticket Médio']:,.2f}).")
                st.markdown(f"📦 **Melhor P.A (Peças/Venda):** {dia_max_pa['dia semana']} ({dia_max_pa['P.A.']:.2f}). Diferente do padrão, esse dia se destacou em peças por cliente.")
                st.markdown(f"❄ **Dia de Menor Fluxo:** {dia_min_venda['dia semana']} ({int(dia_min_venda['Vendas'])} atendimentos).")
            
            df_heat_display = df_heat.copy()
            df_heat_display.columns = ['Dia da Semana', 'Peças (Qtd)', 'Vendas (Qtd)', 'Faturamento Líquido', 'P.A.', 'Ticket Médio']
            
            st.dataframe(
                df_heat_display.style
                .format({
                    'Faturamento Líquido': 'R$ {:,.2f}',
                    'Ticket Médio': 'R$ {:,.2f}',
                    'P.A.': '{:.2f}',
                    'Peças (Qtd)': '{:.0f}',
                    'Vendas (Qtd)': '{:.0f}'
                })
                .background_gradient(subset=['Faturamento Líquido'], cmap='Oranges') 
                .background_gradient(subset=['Vendas (Qtd)'], cmap='Blues'),         
                hide_index=True, 
                use_container_width=True
            )

            st.divider()
            st.subheader(f"4. COMPARATIVO POR DESCÊNDIO ({mes_selecionado} {ano_selecionado})")
            st.write("Performance da loja dividida por períodos de 10 dias.")

            df_desc = df_atual.groupby('descêndio').agg(
                Vendas=('id_venda', 'nunique'),
                Faturamento=('faturamento_venda_unica', 'sum')
            ).reset_index()

            df_desc.columns = ['Período', 'Vendas (Qtd)', 'Faturamento Líquido']

            if not df_desc.empty and df_desc['Faturamento Líquido'].sum() > 0:
                max_fat_desc = df_desc['Faturamento Líquido'].max()
                min_fat_desc = df_desc['Faturamento Líquido'].min()

                def classificar_descendio(valor):
                    if valor == max_fat_desc:
                        return "⭐ Melhor período do mês"
                    elif valor == min_fat_desc:
                        return "⚠️ Período de menor fluxo/venda"
                    else:
                        return "Desempenho dentro da média"

                df_desc['Destaque no Período'] = df_desc['Faturamento Líquido'].apply(classificar_descendio)

                st.dataframe(
                    df_desc.style.format({
                        'Vendas (Qtd)': '{:.0f}',
                        'Faturamento Líquido': 'R$ {:,.2f}'
                    }),
                    hide_index=True, 
                    use_container_width=True
                )

                linha_campea = df_desc.loc[df_desc['Faturamento Líquido'].idxmax()]
                st.markdown(f"**Obs:** O **{linha_campea['Período']}** foi o grande motor do mês, concentrando **R$ {linha_campea['Faturamento Líquido']:,.2f}** em faturamento e impulsionando os resultados com {int(linha_campea['Vendas (Qtd)'])} atendimentos.")
            else:
                st.warning("Não há dados suficientes para analisar os descêndios neste mês.")


            st.divider()
            st.subheader(f"5. RANKING DE PRODUTOS ({mes_selecionado} {ano_selecionado})")
            st.write("Performance das categorias por Valor e Quantidade.")

            if not df_atual.empty and df_atual['valor_liquido_item'].sum() > 0:

                df_prod = df_atual.groupby('categoria').agg(
                    Quantidade=('quantidade', 'sum'),
                    Faturamento=('valor_liquido_item', 'sum')
                ).reset_index()


                fat_total_mes = df_prod['Faturamento'].sum()
                df_prod['% Faturamento'] = (df_prod['Faturamento'] / fat_total_mes) * 100


                df_prod = df_prod.sort_values(by='Faturamento', ascending=False).reset_index(drop=True)
                
                top_1_valor = df_prod.iloc[0]['categoria']
                top_1_fat = df_prod.iloc[0]['Faturamento']
                
                df_prod_qtd = df_prod.sort_values(by='Quantidade', ascending=False).reset_index(drop=True)
                top_1_qtd = df_prod_qtd.iloc[0]['categoria']
                top_1_vol = df_prod_qtd.iloc[0]['Quantidade']

                insight_texto = f"A categoria **{str(top_1_valor).upper()}** confirmou a liderança em faturamento (R$ {top_1_fat:,.2f}). "
                if top_1_valor == top_1_qtd:
                    insight_texto += f"Além de ser a mais rentável, também foi a campeã em volume, com {int(top_1_vol)} peças vendidas."
                else:
                    insight_texto += f"Já em volume de peças, o destaque absoluto foi a categoria **{str(top_1_qtd).upper()}**, com {int(top_1_vol)} unidades vendidas."
                
                st.info(f"💡 **Insight do Ranking:** {insight_texto}")

                st.markdown("**Top 10 Categorias por Faturamento (Gráfico):**")
                import altair as alt
                
                df_grafico = df_prod.head(10).copy()
                df_grafico['Rotulo'] = df_grafico['Faturamento'].apply(lambda x: f"R$ {x:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
                
                max_fat_grafico = df_grafico['Faturamento'].max() * 1.3
                
                barras = alt.Chart(df_grafico).mark_bar(color='#1f77b4').encode(
                    x=alt.X('Faturamento:Q', title='', axis=None, scale=alt.Scale(domain=[0, max_fat_grafico])),
                    y=alt.Y('categoria:N', sort='-x', title='Categoria')
                )
                
                textos = barras.mark_text(
                    align='left',
                    baseline='middle',
                    dx=5, 
                    fontWeight='bold'
                    
                ).encode(
                    text='Rotulo:N'
                )
                
                grafico = (barras + textos).properties(height=400)
                st.altair_chart(grafico, use_container_width=True)

               
                st.markdown("**Tabela Detalhada (Todas as Categorias):**")
                
                df_prod_display = df_prod.copy()
                df_prod_display.columns = ['Categoria', 'Qtd Vendida', 'Valor Líquido (R$)', '% do Faturamento']
                
                
                total_qtd = df_prod_display['Qtd Vendida'].sum()
                total_fat = df_prod_display['Valor Líquido (R$)'].sum()
                total_perc = df_prod_display['% do Faturamento'].sum()
                
                df_total = pd.DataFrame([{
                    'Categoria': 'TOTAL GERAL', 
                    'Qtd Vendida': total_qtd, 
                    'Valor Líquido (R$)': total_fat, 
                    '% do Faturamento': total_perc
                }])
                
                df_prod_display = pd.concat([df_prod_display, df_total], ignore_index=True)
                
              
                indices = [f"{i+1}º" for i in range(len(df_prod_display)-1)] + ["-"]
                df_prod_display.index = indices
                
            
                st.table(
                    df_prod_display.style.format({
                        'Valor Líquido (R$)': 'R$ {:,.2f}',
                        '% do Faturamento': '{:.2f}%',
                        'Qtd Vendida': '{:.0f}'
                    }).apply(lambda x: ['font-weight: bold; background-color: rgba(128, 128, 128, 0.2)' if x.name == '-' else '' for _ in x], axis=1)
                )
            else:
                st.warning("Não há dados suficientes para gerar o ranking de produtos.")


        
            st.divider()
            st.subheader("6. REFLEXÕES PARA MELHORIA")
            st.write("Perguntas chave para a gestão baseada nos dados:")

            if not df_atual.empty:
                
                df_dias = df_atual.groupby('dia semana').agg(
                    Vendas=('id_venda', 'nunique'),
                    Faturamento=('faturamento_venda_unica', 'sum'),
                    Pecas=('quantidade', 'sum')
                ).reset_index()
                
                df_dias['P.A.'] = (df_dias['Pecas'] / df_dias['Vendas']).fillna(0)
                df_dias['TKM'] = (df_dias['Faturamento'] / df_dias['Vendas']).fillna(0)
                
               
                dia_super = df_dias.loc[df_dias['TKM'].idxmax()]
                dia_volume = df_dias.loc[df_dias['Vendas'].idxmax()]
                dia_fraco = df_dias.loc[df_dias['Vendas'].idxmin()]
                
               
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.info(f"🏆 **A 'Super {dia_super['dia semana']}':**\nApresentou o maior Ticket Médio (R$ {dia_super['TKM']:,.2f}). O que aconteceu de diferente nas {dia_super['dia semana'].lower()}s de {mes_selecionado}? Foi uma ação específica ou equipe de alta performance? Vale investigar para replicar nos outros dias.")
                    
                with col2:
                 
                    if dia_volume['P.A.'] < df_dias['P.A.'].max():
                        meta_pa = dia_volume['P.A.'] + 0.15
                        st.warning(f"🎯 **Oportunidade no(a) {dia_volume['dia semana']}:**\nTraz volume massivo ({int(dia_volume['Vendas'])} clientes), mas o P.A. ({dia_volume['P.A.']:.2f}) pode melhorar. Com a loja cheia, a equipe foca só em 'tirar pedido'? Um leve aumento de P.A. para {meta_pa:.2f} geraria um impacto gigante.")
                    else:
                        st.success(f"🔥 **Máxima Conversão no(a) {dia_volume['dia semana']}:**\nO dia de maior fluxo ({int(dia_volume['Vendas'])} clientes) também sustentou um excelente P.A. ({dia_volume['P.A.']:.2f}). A operação suportou muito bem o pico de movimento!")

                with col3:
                    st.error(f"⚠️ **Desafio do(a) {dia_fraco['dia semana']}:**\nÉ o dia de menor fluxo ({int(dia_fraco['Vendas'])} atendimentos). Como o movimento é baixo, a equipe está aproveitando a loja vazia para oferecer produtos adicionais (venda casada) e aumentar o ticket do cliente que entra?")

             
            st.divider()
            st.subheader("📌 RESUMO EXECUTIVO")

            if not df_atual.empty and df_atual['faturamento_venda_unica'].sum() > 0:
                fat_total_resumo = df_atual['faturamento_venda_unica'].sum()
                vendas_total_resumo = df_atual['id_venda'].nunique()
                pa_resumo = df_atual['quantidade'].sum() / vendas_total_resumo if vendas_total_resumo > 0 else 0
                tkm_resumo = fat_total_resumo / vendas_total_resumo if vendas_total_resumo > 0 else 0
                cat_campea = df_atual.groupby('categoria')['valor_liquido_item'].sum().idxmax()
                
                texto_resumo = f"""
**Para amarrar todas as análises, este é o Raio-X definitivo de {mes_selecionado} de {ano_selecionado}:**

* 💰 **Faturamento Total:** R$ {fat_total_resumo:,.2f}
* 🛍️ **Fluxo da Loja:** {int(vendas_total_resumo)} atendimentos realizados
* 💎 **Ticket Médio (TKM):** R$ {tkm_resumo:,.2f}
* 📦 **Peças por Atendimento (P.A):** {pa_resumo:.2f}
* 👑 **Carro-Chefe:** A categoria **{str(cat_campea).upper()}** puxou os resultados do mês.

**🎯 Direcionamento:** O caminho para o próximo mês é focar na conversão (aumentar o P.A. nos dias de pico) e no trabalho de venda adicional para subir o Ticket Médio nos dias de menor fluxo.
                """
                
                st.info(texto_resumo)

            st.markdown("<br><br>", unsafe_allow_html=True)
            st.caption("---")
            st.markdown("*A Effective agradece a confiança e parceria. A operação demonstra dados claros e pontos de otimização focados em conversão. Ficamos à disposição para dúvidas ou sugestões!*")