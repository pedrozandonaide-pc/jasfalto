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

# ==================== FUNÇÃO DE VALIDAÇÃO DE PRAZO SIMPLIFICADA ====================

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
    
    # Caso 1: Hoje
    if diferenca_dias == 0:
        return False, "❌ Não é permitido programar para o dia de hoje."
    
    # Caso 2: Amanhã (1 dia de diferença)
    if diferenca_dias == 1:
        hora_atual = agora.hour
        if hora_atual >= 16:
            return False, f"❌ Prazo para programar para AMANHÃ expirou. O limite era até às 16h de hoje. Agora são {agora.strftime('%H:%M')} (horário de Brasília)."
        else:
            horas_restantes = 16 - hora_atual
            return True, f"✅ Você pode programar para AMANHÃ (data: {data_selecionada.strftime('%d/%m/%Y')}). Prazo até às 16h de hoje. Faltam {horas_restantes} horas."
    
    # Caso 3: Depois de amanhã ou mais (2+ dias de diferença)
    if diferenca_dias >= 2:
        return True, f"✅ Programação para {data_selecionada.strftime('%d/%m/%Y')} permitida (com {diferenca_dias} dias de antecedência)."
    
    # Caso 4: Data passada
    if diferenca_dias < 0:
        return False, "❌ Não é possível programar para datas passadas."
    
    return False, "Data inválida"

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

# ==================== FUNÇÃO PARA GERAR PDF COM GRÁFICO ====================
def gerar_grafico_toneladas_por_data_produto(df):
    """Gera gráfico de barras empilhadas por data e produto com cores personalizadas"""
    
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
    
    fig.update_traces(
        texttemplate='%{text:.1f}t',
        textposition='inside',
        textfont=dict(size=11, color='black', weight='bold')
    )
    
    fig.update_layout(
        xaxis_title="Data",
        yaxis_title="Toneladas",
        xaxis={'tickformat': '%d/%m/%Y', 'tickangle': -45, 'tickfont': dict(size=12, color='black')},
        yaxis={'gridcolor': '#e0e0e0', 'tickfont': dict(size=12, color='black')},
        height=500,
        plot_bgcolor='white',
        paper_bgcolor='white',
        title_font=dict(size=16, color='black'),
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor='rgba(255,255,255,0.9)')
    )
    
    return fig

def gerar_pdf_html(df_detalhado, df_resumo, fig_html, data_inicio, data_fim):
    """Gera HTML para PDF"""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"><title>Relatório JASFALTO</title>
    <style>
        body {{ font-family: Arial; margin: 40px; }}
        h1 {{ color: #2c3e50; text-align: center; border-bottom: 2px solid #4CAF50; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th {{ background-color: #4CAF50; color: white; padding: 10px; border: 1px solid #ddd; }}
        td {{ padding: 8px; border: 1px solid #ddd; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .footer {{ text-align: center; margin-top: 30px; font-size: 11px; color: #666; }}
    </style>
    </head>
    <body>
        <h1>JASFALTO - Relatório de Programações</h1>
        <p><strong>Período:</strong> {data_inicio} a {data_fim}</p>
        <div class="grafico">{fig_html}</div>
        <h2>Resumo Geral</h2>
        {df_resumo.to_html(index=False)}
        <h2>Detalhamento por Caminhão</h2>
        <p>Total de viagens: {len(df_detalhado)}</p>
        {df_detalhado.to_html(index=False)}
        <div class="footer">Relatório gerado pelo Sistema JASFALTO</div>
    </body>
    </html>
    """
    return html

def expandir_por_caminhao(df_filtrado):
    """Expande o DataFrame para uma linha por caminhão"""
    registros_expandidos = []
    for idx, row in df_filtrado.iterrows():
        placas = row['placas'].split(', ') if pd.notna(row['placas']) and row['placas'] else []
        if placas:
            for placa in placas:
                if placa.strip():
                    novo_registro = row.copy()
                    novo_registro['placa'] = placa.strip()
                    registros_expandidos.append(novo_registro)
        else:
            novo_registro = row.copy()
            novo_registro['placa'] = 'Não informado'
            registros_expandidos.append(novo_registro)
    return pd.DataFrame(registros_expandidos) if registros_expandidos else pd.DataFrame()

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
            worksheet_usuarios.insert_row(['username', 'password_hash', 'nome', 'email', 'telefone', 'cargo', 'tipo', 'data_cadastro'], 1)
        
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
        return pd.DataFrame(columns=['username', 'password_hash', 'nome', 'email', 'telefone', 'cargo', 'tipo', 'data_cadastro'])
    except:
        return pd.DataFrame()

def salvar_usuario(username, password_hash, nome, email, telefone, cargo, tipo):
    try:
        _, worksheet, _ = conectar_google_sheets()
        if worksheet:
            worksheet.append_row([username, password_hash, nome, email, telefone, cargo, tipo, datetime.now().isoformat()])
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
        salvar_usuario('admin', admin_hash, 'Administrador Master', 'admin@jasfalto.com', '', 'Master', 'admin')
        uberaba_hash = hashlib.sha256("uberaba123".encode()).hexdigest()
        salvar_usuario('uberaba', uberaba_hash, 'Administrador Uberaba', 'uberaba@jasfalto.com', '', 'Administrador Usina Uberaba', 'admin_usina')
        araguari_hash = hashlib.sha256("araguari123".encode()).hexdigest()
        salvar_usuario('araguari', araguari_hash, 'Administrador Araguari', 'araguari@jasfalto.com', '', 'Administrador Usina Araguari', 'admin_usina')
        df_usuarios = carregar_usuarios()
    
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    usuario = df_usuarios[df_usuarios['username'] == username]
    if not usuario.empty and usuario.iloc[0]['password_hash'] == password_hash:
        return {'username': username, 'nome': usuario.iloc[0]['nome'], 'cargo': usuario.iloc[0].get('cargo', ''), 'tipo': usuario.iloc[0].get('tipo', 'cliente')}
    return None

def cadastrar_novo_usuario(username, password, nome, email, telefone, cargo, tipo='cliente'):
    df_usuarios = carregar_usuarios()
    if username in df_usuarios['username'].values:
        return False
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    return salvar_usuario(username, password_hash, nome, email, telefone, cargo, tipo)

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
        
        # Data mínima é amanhã (nunca pode hoje)
        data_minima = hoje + timedelta(days=1)
        data_selecionada = st.date_input("Data da Usinagem", value=data_minima, min_value=data_minima)
        
        # Validar a data selecionada
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
                quant_caminhoes = st.number_input("Quantidade de Caminhões", min_value=1, step=1, value=1)
                placas = []
                for i in range(quant_caminhoes):
                    placa = st.text_input(f"Placa Caminhão {i+1}", placeholder="ABC-1234", key=f"placa_{i}")
                    placas.append(placa)
                placas_str = ", ".join([p for p in placas if p])
                
                transportador = st.text_input("Transportador")
                usina = st.selectbox("Usina", ["Jasfalto - Uberaba/MG", "Jasfalto - Araguari/MG"])
                observacoes = st.text_area("Observações", height=80)
            
            enviar = st.form_submit_button("Enviar Programação", disabled=not valido)
            
            if enviar and valido:
                prog_id = adicionar_programacao(
                    usuario['username'], cliente_selecionado, cliente_outros, data_selecionada,
                    produto, toneladas, quant_caminhoes, placas_str, transportador, usina, observacoes
                )
                if prog_id:
                    st.success(f"✅ Programação #{prog_id} enviada!")
                    st.balloons()
                else:
                    st.error("Erro ao salvar")
    
    with aba2:
        st.markdown("### Minhas Programações")
        df = carregar_programacoes()
        if not df.empty:
            minhas = df[df['username'] == usuario['username']].sort_values('data', ascending=False)
            if not minhas.empty:
                st.dataframe(minhas[['id', 'data', 'produto', 'toneladas', 'usina', 'status']], use_container_width=True)
            else:
                st.info("Nenhuma programação")

# ==================== INTERFACE DO ADMIN (SIMPLIFICADA) ====================

def pagina_admin(usuario):
    st.title(f"⚙️ Painel Administrativo - {usuario['nome']}")
    
    df = carregar_programacoes()
    
    if usuario['tipo'] == 'admin_usina':
        usina_filtro = "Jasfalto - Uberaba/MG" if usuario['username'] == 'uberaba' else "Jasfalto - Araguari/MG"
        df = df[df['usina'] == usina_filtro]
        st.info(f"Visualizando apenas: {usina_filtro}")
    
    if not df.empty:
        st.dataframe(df, use_container_width=True)
        
        # Editor de status
        for idx, row in df.iterrows():
            with st.expander(f"Programação #{row['id']} - {row['cliente']} - {row['data']}"):
                novo_status = st.selectbox("Status", ['Pendente', 'Confirmada', 'Cancelada'], 
                                          index=['Pendente', 'Confirmada', 'Cancelada'].index(row['status']),
                                          key=f"status_{row['id']}")
                if novo_status != row['status']:
                    atualizar_status_programacao(row['id'], novo_status)
                    st.rerun()
    else:
        st.info("Nenhuma programação")

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
        
        # Link do site
        st.markdown("""
        <div style="text-align: center; margin: 20px 0;">
            <a href="https://jasfalto.com.br/" target="_blank">
                <button style="background-color: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 5px;">
                    🌐 jasfalto.com.br
                </button>
            </a>
        </div>
        """, unsafe_allow_html=True)
        
        tab_login, tab_cadastro = st.tabs(["Login", "Cadastrar"])
        
        with tab_login:
            with st.form("login"):
                username = st.text_input("Usuário")
                password = st.text_input("Senha", type="password")
                if st.form_submit_button("Entrar"):
                    usuario = autenticar_usuario(username, password)
                    if usuario:
                        st.session_state.autenticado = True
                        st.session_state.usuario = usuario
                        st.rerun()
                    else:
                        st.error("Usuário/senha inválidos")
            
            with st.expander("Esqueci minha senha"):
                st.markdown("""
                📞 Entre em contato com o responsável da balança:
                ** (34) 3326-7300 **
                """)
        
        with tab_cadastro:
            with st.form("cadastro"):
                novo_user = st.text_input("Usuário")
                novo_nome = st.text_input("Nome")
                novo_email = st.text_input("Email")
                novo_telefone = st.text_input("Telefone")
                novo_cargo = st.text_input("Cargo")
                nova_senha = st.text_input("Senha", type="password")
                confirma = st.text_input("Confirmar senha", type="password")
                
                if st.form_submit_button("Cadastrar"):
                    if nova_senha == confirma:
                        if cadastrar_novo_usuario(novo_user, nova_senha, novo_nome, novo_email, novo_telefone, novo_cargo):
                            st.success("Cadastro realizado! Faça login.")
                        else:
                            st.error("Usuário já existe")
                    else:
                        st.error("Senhas não conferem")
    
    else:
        with st.sidebar:
            if logo:
                st.image(logo, width=150)
            st.markdown(f"### {st.session_state.usuario['nome']}")
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
