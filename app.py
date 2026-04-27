import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import plotly.express as px
import hashlib
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import base64
import io
import pytz

# Configuração da página
st.set_page_config(
    page_title="Gestão de Usinagem - JASFALTO",
    page_icon="🏭",
    layout="wide"
)

# ==================== FUNÇÃO PARA OBTER HORÁRIO BRASÍLIA ====================

def obter_horario_brasilia():
    """Retorna a data e hora atual no fuso horário de Brasília (GMT-3)"""
    fuso_brasilia = pytz.timezone('America/Sao_Paulo')
    agora_utc = datetime.now(pytz.UTC)
    agora_brasilia = agora_utc.astimezone(fuso_brasilia)
    return agora_brasilia

def obter_data_hoje_brasilia():
    """Retorna a data atual no fuso horário de Brasília"""
    return obter_horario_brasilia().date()

# ==================== FUNÇÃO DE VALIDAÇÃO DE PRAZO ====================

def validar_data_programacao(data_selecionada):
    """
    Valida se a data selecionada é permitida para programação
    Regras:
    - Hoje: NUNCA permitido
    - Amanhã: Permitido APENAS se ainda NÃO passou das 16h de HOJE
    - D+2, D+3, D+4...: SEMPRE permitido
    """
    agora = obter_horario_brasilia()
    hoje = obter_data_hoje_brasilia()
    
    diferenca_dias = (data_selecionada - hoje).days
    
    if diferenca_dias == 0:
        return False, "❌ Não é permitido programar para o dia de hoje."
    
    if diferenca_dias == 1:
        hora_atual = agora.hour
        if hora_atual >= 16:
            return False, f"❌ Prazo para programar para AMANHÃ expirou. O limite era até às 16h de hoje. Agora são {agora.strftime('%H:%M')} (horário de Brasília)."
        else:
            horas_restantes = 16 - hora_atual
            return True, f"✅ Você pode programar para AMANHÃ (data: {data_selecionada.strftime('%d/%m/%Y')}). Prazo até às 16h de hoje. Faltam {horas_restantes} horas."
    
    if diferenca_dias >= 2:
        return True, f"✅ Programação para {data_selecionada.strftime('%d/%m/%Y')} permitida (com {diferenca_dias} dias de antecedência)."
    
    if diferenca_dias < 0:
        return False, "❌ Não é possível programar para datas passadas."
    
    return False, "Data inválida"

def pode_editar_programacao(data_programacao):
    """
    Verifica se o usuário ainda pode editar uma programação existente
    Regras:
    - Programações para hoje (D): NÃO podem ser editadas
    - Programações para amanhã (D+1): Podem ser editadas apenas se hoje antes das 16h
    - Programações para D+2, D+3, D+4...: SEMPRE podem ser editadas
    """
    agora = obter_horario_brasilia()
    hoje = obter_data_hoje_brasilia()
    
    diferenca_dias = (data_programacao - hoje).days
    
    if diferenca_dias == 0:
        return False, "❌ Não é possível editar programação para o dia atual."
    
    if diferenca_dias == 1:
        if agora.hour >= 16:
            return False, f"❌ Prazo para editar programação para amanhã expirou. O limite era até às 16h de hoje."
        else:
            return True, f"✅ Você pode editar programação para amanhã até às 16h de hoje."
    
    if diferenca_dias >= 2:
        return True, f"✅ Você pode editar esta programação (sem limite de horário)."
    
    return False, "Prazo para edição expirado."

# ==================== LOGOMARCA ====================
def carregar_logo():
    """Carrega a logomarca da empresa"""
    try:
        with open("Logo Jasfalto.jpeg", "rb") as img_file:
            logo_bytes = img_file.read()
            logo_base64 = base64.b64encode(logo_bytes).decode()
            return f"data:image/jpeg;base64,{logo_base64}"
    except:
        return None

# ==================== FUNÇÕES DE GRÁFICO ====================

def gerar_grafico_toneladas_por_data_produto(df):
    """Gera gráfico de barras empilhadas por data e produto"""
    
    cores_produtos = {
        "Faixa B": "#1f77b4",
        "Faixa C": "#ff7f0e",
        "Faixa D": "#2ca02c",
        "Faixa D Aditivado": "#d62728",
        "Faixa D Aditivado (saco 25kg)": "#ff9896",
        "EGL 16-19": "#9467bd",
        "Gap-Graded": "#8c564b",
        "PMQ": "#e377c2",
        "Emulsão RR-1C": "#7f7f7f",
        "CM-IMP": "#bcbd22",
        "Rejeito de Asfalto": "#c5b0d5"
    }
    
    if df.empty:
        return px.bar(title="Sem dados")
    
    dados_grafico = df.groupby(['data', 'produto'])['toneladas'].sum().reset_index()
    
    fig = px.bar(
        dados_grafico,
        x='data',
        y='toneladas',
        color='produto',
        title="Somatório de Toneladas por Dia e Produto",
        labels={'data': 'Data', 'toneladas': 'Toneladas', 'produto': 'Produto'},
        text='toneladas',
        barmode='stack',
        color_discrete_map=cores_produtos
    )
    
    fig.update_traces(texttemplate='%{text:.1f}t', textposition='inside', textfont=dict(size=11, color='black', weight='bold'))
    fig.update_layout(
        xaxis_title="Data", yaxis_title="Toneladas",
        xaxis={'tickformat': '%d/%m/%Y', 'tickangle': -45, 'tickfont': dict(size=12, color='black')},
        yaxis={'gridcolor': '#e0e0e0', 'tickfont': dict(size=12, color='black')},
        height=500, plot_bgcolor='white', paper_bgcolor='white',
        title_font=dict(size=16, color='black'),
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor='rgba(255,255,255,0.9)')
    )
    return fig

# ==================== FUNÇÃO PARA GERAR PDF ====================

def gerar_pdf_relatorio(df_filtrado, data_inicio, data_fim, titulo="Relatório de Programações"):
    """Gera um relatório em PDF com resumo e detalhamento por caminhão"""
    
    if df_filtrado.empty:
        return None
    
    # Expandir por caminhão para o detalhamento
    registros_expandidos = []
    for idx, row in df_filtrado.iterrows():
        placas = row['placas'].split(', ') if pd.notna(row['placas']) and row['placas'] else []
        if placas:
            for placa in placas:
                if placa.strip():
                    novo_registro = {
                        'Data': row['data'].strftime('%d/%m/%Y'),
                        'Cliente': row['cliente'],
                        'Produto': row['produto'],
                        'Placa': placa.strip(),
                        'Transportador': row['transportador'],
                        'Usina': row['usina'],
                        'Status': row['status']
                    }
                    registros_expandidos.append(novo_registro)
        else:
            novo_registro = {
                'Data': row['data'].strftime('%d/%m/%Y'),
                'Cliente': row['cliente'],
                'Produto': row['produto'],
                'Placa': 'Não informado',
                'Transportador': row['transportador'],
                'Usina': row['usina'],
                'Status': row['status']
            }
            registros_expandidos.append(novo_registro)
    
    df_detalhado = pd.DataFrame(registros_expandidos)
    
    # Preparar resumo
    resumo = {
        'Período': f"{data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}",
        'Total de Programações': len(df_filtrado),
        'Total de Toneladas': f"{df_filtrado['toneladas'].sum():,.0f} t",
        'Total de Viagens (Caminhões)': df_filtrado['quant_caminhoes'].sum(),
        'Total de Clientes': df_filtrado['cliente'].nunique()
    }
    
    # Separar por status
    status_counts = df_filtrado['status'].value_counts().to_dict()
    for status, count in status_counts.items():
        resumo[f'Programações {status}'] = count
    
    df_resumo = pd.DataFrame([resumo])
    
    # Gerar gráfico
    fig = gerar_grafico_toneladas_por_data_produto(df_filtrado)
    fig_html = fig.to_html(full_html=False, include_plotlyjs='cdn')
    
    # Gerar HTML do relatório
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>{titulo} - JASFALTO</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 40px;
                color: #333;
            }}
            h1 {{
                color: #2c3e50;
                text-align: center;
                border-bottom: 2px solid #4CAF50;
                padding-bottom: 10px;
            }}
            h2 {{
                color: #2c3e50;
                margin-top: 30px;
                border-left: 4px solid #4CAF50;
                padding-left: 15px;
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
            }}
            .periodo {{
                text-align: center;
                color: #666;
                margin-bottom: 10px;
            }}
            .resumo {{
                background-color: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 30px;
                border: 1px solid #dee2e6;
            }}
            .resumo h3 {{
                margin-top: 0;
                color: #2c3e50;
            }}
            .resumo table {{
                width: 100%;
                border-collapse: collapse;
            }}
            .resumo td {{
                padding: 8px;
                border: none;
            }}
            .grafico {{
                margin: 30px 0;
                text-align: center;
                page-break-inside: avoid;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
                margin-bottom: 30px;
                font-size: 12px;
            }}
            th {{
                background-color: #4CAF50;
                color: white;
                padding: 10px;
                text-align: left;
                border: 1px solid #ddd;
            }}
            td {{
                padding: 8px;
                border: 1px solid #ddd;
                text-align: left;
            }}
            tr:nth-child(even) {{
                background-color: #f2f2f2;
            }}
            .footer {{
                text-align: center;
                margin-top: 30px;
                font-size: 11px;
                color: #666;
                border-top: 1px solid #dee2e6;
                padding-top: 15px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>JASFALTO - {titulo}</h1>
        </div>
        <div class="periodo">
            <strong>Período:</strong> {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}
        </div>
        <div class="periodo">
            <strong>Data de emissão:</strong> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
        </div>
        
        <div class="resumo">
            <h3>📊 RESUMO GERAL</h3>
            {df_resumo.to_html(index=False)}
        </div>
        
        <div class="grafico">
            <h3>📈 TONELADAS POR DATA E PRODUTO</h3>
            {fig_html}
        </div>
        
        <h2>📋 DETALHAMENTO POR CAMINHÃO</h2>
        <p><strong>Total de viagens:</strong> {len(df_detalhado)}</p>
        {df_detalhado.to_html(index=False)}
        
        <div class="footer">
            <p>Relatório gerado automaticamente pelo Sistema de Gestão de Usinagem JASFALTO</p>
        </div>
    </body>
    </html>
    """
    
    return html

# ==================== CONEXÃO COM GOOGLE SHEETS ====================

def conectar_google_sheets():
    """Conecta ao Google Sheets"""
    try:
        if 'google' not in st.secrets:
            st.error("Configure as secrets do Google Sheets no Streamlit Cloud")
            return None, None, None
        
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["google"], scope)
        client = gspread.authorize(creds)
        sheet_id = st.secrets["google_sheet_id"]
        spreadsheet = client.open_by_key(sheet_id)
        
        try:
            worksheet_usuarios = spreadsheet.worksheet("usuarios")
        except:
            worksheet_usuarios = spreadsheet.add_worksheet(title="usuarios", rows="100", cols="20")
            worksheet_usuarios.insert_row(['username', 'password_hash', 'nome', 'email', 'telefone', 'cargo', 'tipo', 'usina_permitida', 'data_cadastro'], 1)
        
        try:
            worksheet_programacoes = spreadsheet.worksheet("programacoes")
        except:
            worksheet_programacoes = spreadsheet.add_worksheet(title="programacoes", rows="100", cols="20")
            worksheet_programacoes.insert_row(['id', 'username', 'cliente', 'cliente_outros', 'data', 'produto', 'toneladas', 'quant_caminhoes', 'placas', 'transportador', 'usina', 'status', 'data_solicitacao', 'observacoes'], 1)
        
        return spreadsheet, worksheet_usuarios, worksheet_programacoes
    except Exception as e:
        st.error(f"Erro ao conectar: {e}")
        return None, None, None

def carregar_usuarios():
    try:
        _, worksheet, _ = conectar_google_sheets()
        if worksheet:
            dados = worksheet.get_all_records()
            if dados:
                return pd.DataFrame(dados)
        return pd.DataFrame(columns=['username', 'password_hash', 'nome', 'email', 'telefone', 'cargo', 'tipo', 'usina_permitida', 'data_cadastro'])
    except:
        return pd.DataFrame()

def salvar_usuario(username, password_hash, nome, email, telefone, cargo, tipo, usina_permitida=""):
    try:
        _, worksheet, _ = conectar_google_sheets()
        if worksheet:
            worksheet.append_row([username, password_hash, nome, email, telefone, cargo, tipo, usina_permitida, datetime.now().isoformat()])
            return True
    except:
        return False
    return False

def carregar_programacoes():
    try:
        _, _, worksheet = conectar_google_sheets()
        if worksheet:
            dados = worksheet.get_all_records()
            if dados:
                df = pd.DataFrame(dados)
                if 'data' in df.columns:
                    df['data'] = pd.to_datetime(df['data']).dt.date
                return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

def salvar_programacao(programacao):
    try:
        _, _, worksheet = conectar_google_sheets()
        if worksheet:
            worksheet.append_row([
                programacao['id'], programacao['username'], programacao['cliente'], programacao['cliente_outros'],
                programacao['data'].isoformat(), programacao['produto'], programacao['toneladas'],
                programacao['quant_caminhoes'], programacao['placas'], programacao['transportador'],
                programacao['usina'], programacao['status'], programacao['data_solicitacao'].isoformat(),
                programacao['observacoes']
            ])
            return True
    except:
        return False
    return False

def atualizar_status_programacao(id_programacao, novo_status):
    try:
        _, _, worksheet = conectar_google_sheets()
        if worksheet:
            dados = worksheet.get_all_records()
            for idx, row in enumerate(dados, start=2):
                if str(row.get('id', '')) == str(id_programacao):
                    coluna_status = list(row.keys()).index('status') + 1
                    worksheet.update_cell(idx, coluna_status, novo_status)
                    return True
    except:
        pass
    return False

def atualizar_programacao(id_programacao, cliente, cliente_outros, data, produto, toneladas, 
                         quant_caminhoes, placas, transportador, usina, observacoes):
    """Atualiza uma programação existente"""
    try:
        _, _, worksheet = conectar_google_sheets()
        if worksheet:
            dados = worksheet.get_all_records()
            
            for idx, row in enumerate(dados, start=2):
                if str(row.get('id', '')) == str(id_programacao):
                    colunas = list(row.keys())
                    
                    worksheet.update_cell(idx, colunas.index('cliente') + 1, cliente)
                    worksheet.update_cell(idx, colunas.index('cliente_outros') + 1, cliente_outros if cliente == "OUTROS" else "")
                    worksheet.update_cell(idx, colunas.index('data') + 1, data.isoformat())
                    worksheet.update_cell(idx, colunas.index('produto') + 1, produto)
                    worksheet.update_cell(idx, colunas.index('toneladas') + 1, toneladas)
                    worksheet.update_cell(idx, colunas.index('quant_caminhoes') + 1, quant_caminhoes)
                    worksheet.update_cell(idx, colunas.index('placas') + 1, placas)
                    worksheet.update_cell(idx, colunas.index('transportador') + 1, transportador)
                    worksheet.update_cell(idx, colunas.index('usina') + 1, usina)
                    worksheet.update_cell(idx, colunas.index('observacoes') + 1, observacoes)
                    
                    return True
        return False
    except Exception as e:
        st.error(f"Erro ao atualizar programação: {e}")
        return False

def cancelar_programacao(id_programacao):
    """Cancela uma programação"""
    return atualizar_status_programacao(id_programacao, "Cancelada")

def adicionar_programacao(username, cliente, cliente_outros, data, produto, toneladas, quant_caminhoes, placas, transportador, usina, observacoes):
    df = carregar_programacoes()
    novo_id = len(df) + 1 if not df.empty else 1
    nome_cliente = cliente_outros if cliente == "OUTROS" and cliente_outros else cliente
    
    programacao = {
        'id': novo_id, 'username': username, 'cliente': nome_cliente, 'cliente_outros': cliente_outros if cliente == "OUTROS" else "",
        'data': data, 'produto': produto, 'toneladas': toneladas, 'quant_caminhoes': quant_caminhoes,
        'placas': placas, 'transportador': transportador, 'usina': usina, 'status': 'Pendente',
        'data_solicitacao': datetime.now(), 'observacoes': observacoes
    }
    return novo_id if salvar_programacao(programacao) else None

def autenticar_usuario(username, password):
    df_usuarios = carregar_usuarios()
    if df_usuarios.empty:
        admin_hash = hashlib.sha256("admin123".encode()).hexdigest()
        salvar_usuario('admin', admin_hash, 'Administrador Master', 'admin@jasfalto.com', '', 'Master', 'admin', '')
        uberaba_hash = hashlib.sha256("uberaba123".encode()).hexdigest()
        salvar_usuario('uberaba', uberaba_hash, 'Administrador Uberaba', 'uberaba@jasfalto.com', '', 'Administrador Usina', 'admin_usina', 'Jasfalto - Uberaba/MG')
        araguari_hash = hashlib.sha256("araguari123".encode()).hexdigest()
        salvar_usuario('araguari', araguari_hash, 'Administrador Araguari', 'araguari@jasfalto.com', '', 'Administrador Usina', 'admin_usina', 'Jasfalto - Araguari/MG')
        df_usuarios = carregar_usuarios()
    
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    usuario = df_usuarios[df_usuarios['username'] == username]
    if not usuario.empty and usuario.iloc[0]['password_hash'] == password_hash:
        return {
            'username': username,
            'nome': usuario.iloc[0]['nome'],
            'cargo': usuario.iloc[0].get('cargo', ''),
            'tipo': usuario.iloc[0].get('tipo', 'cliente'),
            'usina_permitida': usuario.iloc[0].get('usina_permitida', '') if 'usina_permitida' in usuario.columns else ''
        }
    return None

def cadastrar_novo_usuario(username, password, nome, email, telefone, cargo, tipo='cliente', usina_permitida=""):
    df_usuarios = carregar_usuarios()
    if username in df_usuarios['username'].values:
        return False
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    return salvar_usuario(username, password_hash, nome, email, telefone, cargo, tipo, usina_permitida)

def resetar_senha_usuario(username, nova_senha):
    try:
        _, worksheet, _ = conectar_google_sheets()
        if worksheet:
            dados = worksheet.get_all_records()
            for idx, row in enumerate(dados, start=2):
                if row.get('username') == username:
                    nova_senha_hash = hashlib.sha256(nova_senha.encode()).hexdigest()
                    coluna_senha = list(row.keys()).index('password_hash') + 1
                    worksheet.update_cell(idx, coluna_senha, nova_senha_hash)
                    return True
    except:
        pass
    return False

# ==================== INTERFACE DO CLIENTE ====================

def pagina_cliente(usuario):
    st.title(f"🏭 Bem-vindo, {usuario['nome']}!")
    
    hoje = obter_data_hoje_brasilia()
    agora = obter_horario_brasilia()
    
    st.info(f"⏰ Horário atual: {agora.strftime('%H:%M:%S')} (Brasília) | Prazo para amanhã: até 16h")
    
    aba1, aba2 = st.tabs(["📝 Nova Programação", "📋 Minhas Programações"])
    
    with aba1:
        st.markdown("### Nova Programação")
        
        data_minima = hoje + timedelta(days=1)
        data_selecionada = st.date_input("Data da Usinagem", value=data_minima, min_value=data_minima)
        
        valido, mensagem = validar_data_programacao(data_selecionada)
        
        if not valido:
            st.error(f"❌ {mensagem}")
        else:
            st.success(f"✅ {mensagem}")
        
        with st.form("form_programacao"):
            col1, col2 = st.columns(2)
            
            with col1:
                opcoes_clientes = [
                    "CONCEBRA - CONCESSIONARIA DAS RODOVIAS CENTRAIS DO BRASIL S.A.",
                    "WAY 262 - CONCESSIONARIA DA RODOVIA BR 262 MG S.A.",
                    "WAY 153 - CONCESSIONARIA ROTA SERTANEJA MG-GO S.A",
                    "EPR TRIÂNGULO - CONCESSIONARIA RODOVIAS DO TRIANGULO SPE S.A.",
                    "ECO050 - CONCESSIONARIA DE RODOVIAS S.A.",
                    "PAVIÁGIL CONSTRUÇÕES E COMÉRCIO LTDA",
                    "OUTROS"
                ]
                cliente_selecionado = st.selectbox("Cliente", opcoes_clientes)
                cliente_outros = st.text_input("Nome do cliente") if cliente_selecionado == "OUTROS" else ""
                
                produto = st.selectbox("Produto", ["Faixa B", "Faixa C", "Faixa D", "Faixa D Aditivado", "Faixa D Aditivado (saco 25kg)", "EGL 16-19", "Gap-Graded", "PMQ", "Emulsão RR-1C", "CM-IMP", "Rejeito de Asfalto"])
                toneladas = st.number_input("Toneladas", min_value=1.0, step=10.0, value=20.0)
            
            with col2:
                if 'quant_caminhoes_novo' not in st.session_state:
                    st.session_state.quant_caminhoes_novo = 1
                
                quant_caminhoes = st.number_input(
                    "Quantidade de Caminhões", min_value=1, max_value=50, step=1,
                    value=st.session_state.quant_caminhoes_novo, key="quant_caminhoes_novo_input"
                )
                
                if quant_caminhoes != st.session_state.quant_caminhoes_novo:
                    st.session_state.quant_caminhoes_novo = quant_caminhoes
                    st.rerun()
                
                st.markdown("#### Placas dos Caminhões")
                placas = []
                for i in range(quant_caminhoes):
                    placa = st.text_input(f"Placa do Caminhão {i+1}", placeholder="Ex: ABC-1234", key=f"nova_placa_{i}")
                    placas.append(placa)
                placas_str = ", ".join([p for p in placas if p])
                
                transportador = st.text_input("Transportador")
                usina = st.selectbox("Usina", ["Jasfalto - Uberaba/MG", "Jasfalto - Araguari/MG"])
                observacoes = st.text_area("Observações", height=80)
            
            enviar = st.form_submit_button("Enviar Programação", disabled=not valido)
            
            if enviar and valido:
                if quant_caminhoes > 0 and not all(placas):
                    st.error("❌ Preencha a placa de todos os caminhões!")
                elif not transportador:
                    st.error("❌ Informe o transportador responsável!")
                elif cliente_selecionado == "OUTROS" and not cliente_outros:
                    st.error("❌ Digite o nome do cliente!")
                else:
                    prog_id = adicionar_programacao(
                        usuario['username'], cliente_selecionado, cliente_outros, data_selecionada,
                        produto, toneladas, quant_caminhoes, placas_str, transportador, usina, observacoes
                    )
                    if prog_id:
                        st.success(f"✅ Programação #{prog_id} enviada com sucesso!")
                        st.balloons()
                        st.session_state.quant_caminhoes_novo = 1
                        st.rerun()
                    else:
                        st.error("Erro ao salvar programação. Tente novamente.")
    
    with aba2:
        st.markdown("### Minhas Programações")
        st.markdown("Aqui você pode visualizar, editar ou cancelar suas programações.")
        
        df = carregar_programacoes()
        if not df.empty:
            minhas = df[df['username'] == usuario['username']].sort_values('data', ascending=True)
            
            if not minhas.empty:
                programacoes_ativas = minhas[minhas['status'].isin(['Pendente', 'Confirmada'])]
                programacoes_finalizadas = minhas[minhas['status'].isin(['Cancelada', 'Entregue'])]
                
                if not programacoes_ativas.empty:
                    st.markdown("#### 📌 Programações Ativas")
                    for idx, row in programacoes_ativas.iterrows():
                        pode_editar, msg_edicao = pode_editar_programacao(row['data'])
                        
                        with st.expander(f"📦 Programação #{row['id']} - {row['data']} - {row['produto']} - Status: {row['status']}"):
                            col_a, col_b, col_c, col_d = st.columns([2, 1, 1, 1])
                            
                            with col_a:
                                st.write(f"**Cliente:** {row['cliente']}")
                                st.write(f"**Produto:** {row['produto']}")
                                st.write(f"**Toneladas:** {row['toneladas']} t")
                                st.write(f"**Quantidade de Caminhões:** {row['quant_caminhoes']}")
                                st.write(f"**Placas:** {row['placas']}")
                                st.write(f"**Transportador:** {row['transportador']}")
                                st.write(f"**Usina:** {row['usina']}")
                                st.write(f"**Observações:** {row['observacoes'] if pd.notna(row['observacoes']) else 'Nenhuma'}")
                            
                            with col_b:
                                if pode_editar:
                                    if st.button(f"✏️ Editar", key=f"edit_{row['id']}"):
                                        st.session_state['editando_id'] = row['id']
                                        st.session_state['editando_dados'] = row.to_dict()
                                        st.session_state['editando_placas_originais'] = row['placas'].split(', ') if pd.notna(row['placas']) else []
                                        st.rerun()
                                else:
                                    st.caption(f"⏰ {msg_edicao}")
                            
                            with col_c:
                                if pode_editar and row['status'] != 'Cancelada':
                                    if st.button(f"❌ Cancelar", key=f"cancel_{row['id']}"):
                                        if cancelar_programacao(row['id']):
                                            st.success(f"✅ Programação #{row['id']} cancelada com sucesso!")
                                            st.rerun()
                                        else:
                                            st.error("Erro ao cancelar programação.")
                            
                            with col_d:
                                st.caption(f"ID: {row['id']}")
                else:
                    st.info("Você não possui programações ativas no momento.")
                
                if not programacoes_finalizadas.empty:
                    st.markdown("---")
                    st.markdown("#### 📜 Histórico de Programações Finalizadas")
                    for idx, row in programacoes_finalizadas.iterrows():
                        with st.expander(f"📦 Programação #{row['id']} - {row['data']} - {row['produto']} - Status: {row['status']}"):
                            st.write(f"**Cliente:** {row['cliente']}")
                            st.write(f"**Produto:** {row['produto']}")
                            st.write(f"**Toneladas:** {row['toneladas']} t")
                            st.write(f"**Quantidade de Caminhões:** {row['quant_caminhoes']}")
                            st.write(f"**Placas:** {row['placas']}")
                            st.write(f"**Transportador:** {row['transportador']}")
                            st.write(f"**Usina:** {row['usina']}")
            else:
                st.info("Você ainda não fez nenhuma programação.")
        else:
            st.info("Nenhuma programação encontrada.")
        
        # Formulário de edição
        if 'editando_id' in st.session_state:
            st.markdown("---")
            st.markdown("### ✏️ Editar Programação")
            st.warning("⚠️ Altere apenas os campos necessários.")
            
            dados_edit = st.session_state['editando_dados']
            placas_originais = st.session_state.get('editando_placas_originais', [])
            
            with st.form("form_editar_programacao"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.info(f"**Data original:** {dados_edit['data']}")
                    st.caption("A data não pode ser alterada. Para mudar a data, cancele esta programação e crie uma nova.")
                    
                    st.info(f"**Cliente original:** {dados_edit['cliente']}")
                    st.caption("O cliente não pode ser alterado.")
                    
                    novo_produto = st.selectbox(
                        "Produto",
                        ["Faixa B", "Faixa C", "Faixa D", "Faixa D Aditivado", "Faixa D Aditivado (saco 25kg)", "EGL 16-19", "Gap-Graded", "PMQ", "Emulsão RR-1C", "CM-IMP", "Rejeito de Asfalto"],
                        index=["Faixa B", "Faixa C", "Faixa D", "Faixa D Aditivado", "Faixa D Aditivado (saco 25kg)", "EGL 16-19", "Gap-Graded", "PMQ", "Emulsão RR-1C", "CM-IMP", "Rejeito de Asfalto"].index(dados_edit['produto']) if dados_edit['produto'] in ["Faixa B", "Faixa C", "Faixa D", "Faixa D Aditivado", "Faixa D Aditivado (saco 25kg)", "EGL 16-19", "Gap-Graded", "PMQ", "Emulsão RR-1C", "CM-IMP", "Rejeito de Asfalto"] else 0
                    )
                    
                    novas_toneladas = st.number_input(
                        "Quantidade (Toneladas)",
                        min_value=1.0,
                        max_value=5000.0,
                        step=10.0,
                        format="%.1f",
                        value=float(dados_edit['toneladas'])
                    )
                
                with col2:
                    novo_quant_caminhoes = st.number_input(
                        "Quantidade de Caminhões",
                        min_value=1,
                        max_value=50,
                        step=1,
                        value=int(dados_edit['quant_caminhoes']),
                        key="edit_quant_caminhoes"
                    )
                    
                    st.markdown("#### Placas dos Caminhões")
                    novas_placas = []
                    for i in range(novo_quant_caminhoes):
                        valor_antigo = placas_originais[i] if i < len(placas_originais) else ""
                        placa = st.text_input(
                            f"Caminhão {i+1} (formato: XXX-XXXX)",
                            value=valor_antigo,
                            key=f"edit_placa_{i}",
                            placeholder="Ex: ABC-1234"
                        )
                        novas_placas.append(placa)
                    
                    novas_placas_str = ", ".join([p for p in novas_placas if p])
                    
                    novo_transportador = st.text_input(
                        "Transportador",
                        value=dados_edit['transportador'] if pd.notna(dados_edit['transportador']) else ""
                    )
                    
                    nova_usina = st.selectbox(
                        "Usina - Localidade",
                        ["Jasfalto - Uberaba/MG", "Jasfalto - Araguari/MG"],
                        index=0 if dados_edit['usina'] == "Jasfalto - Uberaba/MG" else 1
                    )
                    
                    novas_observacoes = st.text_area(
                        "Observações",
                        value=dados_edit['observacoes'] if pd.notna(dados_edit['observacoes']) else "",
                        height=100
                    )
                
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    salvar_edicao = st.form_submit_button("💾 Salvar Alterações", use_container_width=True)
                with col_btn2:
                    cancelar_edicao = st.form_submit_button("❌ Cancelar Edição", use_container_width=True)
                
                if salvar_edicao:
                    if novo_quant_caminhoes > 0 and not all(novas_placas):
                        st.error("❌ Preencha a placa de todos os caminhões!")
                    elif not novo_transportador:
                        st.error("❌ Informe o transportador responsável!")
                    else:
                        if atualizar_programacao(
                            dados_edit['id'],
                            dados_edit['cliente'],
                            "",
                            dados_edit['data'],
                            novo_produto,
                            novas_toneladas,
                            novo_quant_caminhoes,
                            novas_placas_str,
                            novo_transportador,
                            nova_usina,
                            novas_observacoes
                        ):
                            st.success(f"✅ Programação #{dados_edit['id']} atualizada com sucesso!")
                            del st.session_state['editando_id']
                            del st.session_state['editando_dados']
                            del st.session_state['editando_placas_originais']
                            st.rerun()
                        else:
                            st.error("Erro ao atualizar programação.")
                
                if cancelar_edicao:
                    del st.session_state['editando_id']
                    del st.session_state['editando_dados']
                    if 'editando_placas_originais' in st.session_state:
                        del st.session_state['editando_placas_originais']
                    st.rerun()

# ==================== INTERFACE DO ADMIN ====================

def pagina_admin(usuario):
    st.title(f"⚙️ Painel Administrativo - {usuario['nome']}")
    
    # Determinar qual usina o usuário pode ver
    usina_filtro = None
    if usuario['tipo'] == 'admin_usina':
        usina_filtro = usuario.get('usina_permitida', '')
        if usina_filtro:
            st.info(f"🔒 Você está visualizando apenas programações da usina: **{usina_filtro}**")
    
    df_prog = carregar_programacoes()
    df_usuarios = carregar_usuarios()
    
    if usina_filtro and not df_prog.empty:
        df_prog = df_prog[df_prog['usina'] == usina_filtro]
    
    # Abas
    if usuario['tipo'] == 'admin':
        tab1, tab2, tab3 = st.tabs(["📊 Dashboard Programações", "👥 Gerenciar Clientes", "⚙️ Configurações"])
    else:
        tab1, tab2 = st.tabs(["📊 Dashboard Programações", "⚙️ Configurações"])
    
    # Aba 1: Dashboard
    with tab1:
        st.markdown("### Dashboard de Programações")
        
        if not df_prog.empty:
            # Filtros
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                data_inicio = st.date_input("Data Início", value=obter_data_hoje_brasilia() - timedelta(days=7))
            with col_f2:
                data_fim = st.date_input("Data Fim", value=obter_data_hoje_brasilia())
            with col_f3:
                status_filtro = st.multiselect("Status", ['Pendente', 'Confirmada', 'Cancelada'], default=['Pendente', 'Confirmada'])
            
            # Aplicar filtros
            df_filtrado = df_prog[(df_prog['data'] >= data_inicio) & (df_prog['data'] <= data_fim)]
            if status_filtro:
                df_filtrado = df_filtrado[df_filtrado['status'].isin(status_filtro)]
            
            # Botão para gerar PDF
            col_btn1, col_btn2 = st.columns([1, 4])
            with col_btn1:
                if st.button("📄 Gerar PDF", use_container_width=True):
                    if not df_filtrado.empty:
                        html = gerar_pdf_relatorio(df_filtrado, data_inicio, data_fim, "Relatório de Programações")
                        if html:
                            st.download_button(
                                label="📥 Baixar Relatório",
                                data=html.encode(),
                                file_name=f"relatorio_programacoes_{data_inicio.strftime('%Y%m%d')}_{data_fim.strftime('%Y%m%d')}.html",
                                mime="text/html",
                                use_container_width=True
                            )
                    else:
                        st.warning("Nenhum dado encontrado no período selecionado.")
            
            st.markdown("---")
            
            # Métricas
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            with col_m1:
                st.metric("Total Programações", len(df_filtrado))
            with col_m2:
                st.metric("Toneladas Totais", f"{df_filtrado['toneladas'].sum():,.0f} t")
            with col_m3:
                pendentes = len(df_filtrado[df_filtrado['status'] == 'Pendente'])
                st.metric("Pendentes", pendentes)
            with col_m4:
                st.metric("Total Viagens", df_filtrado['quant_caminhoes'].sum())
            
            # Gráfico
            if not df_filtrado.empty:
                fig = gerar_grafico_toneladas_por_data_produto(df_filtrado)
                st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("---")
            st.markdown("### Gerenciar Programações")
            
            for idx, row in df_filtrado.iterrows():
                with st.expander(f"📦 #{row['id']} - {row['cliente']} - {row['data']} - {row['usina']} - Status: {row['status']}"):
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        st.write(f"**Produto:** {row['produto']}")
                        st.write(f"**Toneladas:** {row['toneladas']} t")
                        st.write(f"**Caminhões:** {row['quant_caminhoes']}")
                        st.write(f"**Placas:** {row['placas']}")
                        st.write(f"**Transportador:** {row['transportador']}")
                        st.write(f"**Solicitante:** {row['username']}")
                        st.write(f"**Observações:** {row['observacoes'] if pd.notna(row['observacoes']) else 'Nenhuma'}")
                    with col_b:
                        novo_status = st.selectbox(
                            "Status",
                            ['Pendente', 'Confirmada', 'Cancelada'],
                            index=['Pendente', 'Confirmada', 'Cancelada'].index(row['status']) if row['status'] in ['Pendente', 'Confirmada', 'Cancelada'] else 0,
                            key=f"status_{row['id']}"
                        )
                        if novo_status != row['status']:
                            if atualizar_status_programacao(row['id'], novo_status):
                                st.success(f"Status atualizado para {novo_status}")
                                st.rerun()
        else:
            st.info("Nenhuma programação cadastrada.")
    
    # Aba 2: Gerenciar Clientes (apenas admin master)
    if usuario['tipo'] == 'admin':
        with tab2:
            st.markdown("### Gerenciar Clientes")
            
            if not df_usuarios.empty:
                clientes = df_usuarios[df_usuarios['tipo'] == 'cliente']
                if not clientes.empty:
                    st.markdown("#### 👥 Clientes Cadastrados")
                    st.dataframe(clientes[['username', 'nome', 'email', 'telefone', 'cargo', 'data_cadastro']], use_container_width=True)
                
                admins_usina = df_usuarios[df_usuarios['tipo'] == 'admin_usina']
                if not admins_usina.empty:
                    st.markdown("#### 🔐 Administradores de Usina")
                    st.dataframe(admins_usina[['username', 'nome', 'email', 'usina_permitida']], use_container_width=True)
            
            st.markdown("---")
            
            # Resetar senha
            st.markdown("### 🔑 Resetar Senha de Usuário")
            st.warning("⚠️ Esta ação irá alterar a senha do usuário imediatamente.")
            
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                usuarios_lista = df_usuarios[df_usuarios['username'] != 'admin']['username'].tolist() if not df_usuarios.empty else []
                if usuarios_lista:
                    usuario_reset = st.selectbox("Selecione o usuário", options=usuarios_lista, key="select_usuario_reset")
                else:
                    st.info("Nenhum usuário cadastrado")
                    usuario_reset = None
            
            with col_r2:
                nova_senha = st.text_input("Nova senha", type="password", placeholder="Digite a nova senha", key="nova_senha_reset")
                confirmar_senha = st.text_input("Confirmar nova senha", type="password", placeholder="Confirme a nova senha", key="confirmar_senha_reset")
            
            if st.button("🔄 Resetar Senha", use_container_width=True, key="btn_reset_senha"):
                if usuario_reset and nova_senha:
                    if nova_senha == confirmar_senha:
                        if resetar_senha_usuario(usuario_reset, nova_senha):
                            st.success(f"✅ Senha do usuário **{usuario_reset}** resetada com sucesso!")
                            st.info(f"Nova senha: `{nova_senha}`")
                            st.balloons()
                            st.rerun()
                        else:
                            st.error("Erro ao resetar a senha.")
                    else:
                        st.error("❌ As senhas não conferem!")
                else:
                    st.error("❌ Selecione um usuário e digite a nova senha!")
            
            st.markdown("---")
            
            # Cadastrar novo cliente
            with st.expander("➕ Cadastrar Novo Cliente"):
                with st.form("form_novo_cliente"):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        novo_username = st.text_input("Usuário (login) *")
                        novo_nome = st.text_input("Nome Completo *")
                        novo_email = st.text_input("E-mail *")
                        novo_cargo = st.text_input("Função/Cargo *")
                    with col_b:
                        nova_senha_cliente = st.text_input("Senha *", type="password")
                        novo_telefone = st.text_input("Telefone (WhatsApp)")
                    
                    cadastrar = st.form_submit_button("Cadastrar Cliente")
                    
                    if cadastrar:
                        if all([novo_username, nova_senha_cliente, novo_nome, novo_email, novo_cargo]):
                            if cadastrar_novo_usuario(novo_username, nova_senha_cliente, novo_nome, novo_email, novo_telefone, novo_cargo):
                                st.success(f"✅ Cliente {novo_nome} cadastrado com sucesso!")
                                st.rerun()
                            else:
                                st.error("❌ Usuário já existe!")
                        else:
                            st.error("❌ Preencha todos os campos obrigatórios!")
    
    # Aba de Configurações
    config_tab = tab2 if usuario['tipo'] == 'admin' else tab1 if usuario['tipo'] == 'admin_usina' else None
    
    if config_tab:
        with config_tab:
            st.markdown("### Configurações")
            st.info("✅ Dados salvos permanentemente no Google Sheets. Não há risco de perda de dados.")
            st.info("📋 As programações são salvas em tempo real e podem ser consultadas a qualquer momento.")
            st.info("⏰ **Regras de programação:**")
            st.info("   - ❌ Não é permitido programar para o dia atual")
            st.info("   - ✅ Programação para amanhã: permitida apenas até às 16h de hoje")
            st.info("   - ✅ Programação para depois de amanhã em diante: permitida em qualquer horário")
            
            if usuario['tipo'] == 'admin':
                st.markdown("---")
                st.markdown("### 🔐 Credenciais dos Administradores de Usina")
                st.markdown("""
                | Usuário | Senha | Usina |
                |---------|-------|-------|
                | `uberaba` | `uberaba123` | Jasfalto - Uberaba/MG |
                | `araguari` | `araguari123` | Jasfalto - Araguari/MG |
                """)

# ==================== LOGIN E MAIN ====================

def main():
    logo = carregar_logo()
    
    if 'autenticado' not in st.session_state:
        st.session_state.autenticado = False
    
    if not st.session_state.autenticado:
        if logo:
            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                st.image(logo, width=200)
        
        st.title("🏭 JASFALTO - Gestão de Usinagem")
        
        st.markdown("""
        <div style="text-align: center; margin: 20px 0;">
            <a href="https://jasfalto.com.br/" target="_blank">
                <button style="background-color: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 5px;">
                    🌐 jasfalto.com.br
                </button>
            </a>
        </div>
        """, unsafe_allow_html=True)
        
        tab_login, tab_cadastro = st.tabs(["🔐 Login", "📝 Cadastrar-se"])
        
        with tab_login:
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                with st.form("login"):
                    username = st.text_input("Usuário")
                    password = st.text_input("Senha", type="password")
                    submitted = st.form_submit_button("Entrar", use_container_width=True)
                    
                    if submitted:
                        usuario = autenticar_usuario(username, password)
                        if usuario:
                            st.session_state.autenticado = True
                            st.session_state.usuario = usuario
                            st.rerun()
                        else:
                            st.error("Usuário ou senha inválidos!")
                
                with st.expander("🔑 Esqueci minha senha"):
                    st.markdown("""
                    <div style="text-align: center; padding: 20px; background-color: #f8f9fa; border-radius: 10px;">
                        <p style="font-size: 16px;">📞 Entre em contato com o responsável da balança:</p>
                        <p style="font-size: 20px; font-weight: bold; color: #4CAF50;">(34) 3326-7300</p>
                    </div>
                    """, unsafe_allow_html=True)
        
        with tab_cadastro:
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                with st.form("cadastro"):
                    st.markdown("### Criar nova conta")
                    
                    novo_username = st.text_input("Usuário (login) *")
                    novo_nome = st.text_input("Nome completo *")
                    novo_email = st.text_input("E-mail *")
                    novo_telefone = st.text_input("Telefone (WhatsApp)")
                    novo_cargo = st.text_input("Função/Cargo *")
                    nova_senha = st.text_input("Senha *", type="password")
                    confirma_senha = st.text_input("Confirmar senha *", type="password")
                    
                    cadastrar = st.form_submit_button("Cadastrar", use_container_width=True)
                    
                    if cadastrar:
                        if not all([novo_username, novo_nome, novo_email, novo_cargo, nova_senha]):
                            st.error("❌ Preencha todos os campos obrigatórios!")
                        elif nova_senha != confirma_senha:
                            st.error("❌ As senhas não conferem!")
                        else:
                            if cadastrar_novo_usuario(novo_username, nova_senha, novo_nome, novo_email, novo_telefone, novo_cargo):
                                st.success("✅ Cadastro realizado com sucesso! Faça login para continuar.")
                                st.balloons()
                            else:
                                st.error("❌ Usuário já existe! Escolha outro nome de usuário.")
    
    else:
        with st.sidebar:
            if logo:
                st.image(logo, width=150)
            st.markdown(f"### 👤 {st.session_state.usuario['nome']}")
            st.markdown(f"*{st.session_state.usuario['tipo']}*")
            if st.button("Sair"):
                st.session_state.autenticado = False
                st.rerun()
        
        if st.session_state.usuario['tipo'] in ['admin', 'admin_usina']:
            pagina_admin(st.session_state.usuario)
        else:
            pagina_cliente(st.session_state.usuario)

if __name__ == "__main__":
    main()
