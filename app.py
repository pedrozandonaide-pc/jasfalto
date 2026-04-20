import streamlit as st
import pandas as pd
from datetime import datetime, date
import plotly.express as px
import hashlib
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import base64
import io

# Configuração da página
st.set_page_config(
    page_title="Gestão de Usinagem - JASFALTO",
    page_icon="🏭",
    layout="wide"
)

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
    """Gera gráfico de barras empilhadas por data e produto com cores personalizadas e textos legíveis"""
    
    # Definir um mapa de cores fixo para cada produto
    cores_produtos = {
        "Faixa B": "#1f77b4",      # Azul
        "Faixa C": "#ff7f0e",      # Laranja
        "Faixa D": "#2ca02c",      # Verde
        "Faixa D Aditivado": "#d62728",  # Vermelho
        "EGL 16-19": "#9467bd",    # Roxo
        "Gap-Graded": "#8c564b",   # Marrom
        "PMQ": "#e377c2",          # Rosa
        "Emulsão RR-1C": "#7f7f7f", # Cinza
        "CM-IMP": "#bcbd22"        # Verde-oliva
    }
    
    # Agrupar os dados
    dados_grafico = df.groupby(['data', 'produto'])['toneladas'].sum().reset_index()
    
    # Criar o gráfico com cores personalizadas
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
    
    # Corrigir a cor do texto dentro das barras
    fig.update_traces(
        texttemplate='%{text:.1f}t',
        textposition='inside',
        textfont=dict(size=11, color='black', weight='bold')
    )
    
    fig.update_layout(
        xaxis_title="Data",
        yaxis_title="Toneladas",
        xaxis={
            'tickformat': '%d/%m/%Y',
            'tickangle': -45,
            'tickfont': dict(size=12, color='black')
        },
        yaxis={
            'gridcolor': '#e0e0e0',
            'tickfont': dict(size=12, color='black'),
            'title_font': dict(size=14, color='black')
        },
        height=500,
        plot_bgcolor='white',
        paper_bgcolor='white',
        title_font=dict(size=16, color='black'),
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            bgcolor='rgba(255, 255, 255, 0.9)',
            bordercolor='#ccc',
            borderwidth=1,
            font=dict(size=11, color='black')
        ),
        font=dict(family="Arial, sans-serif", size=12, color='black')
    )
    
    return fig

def gerar_pdf_html(df_detalhado, df_resumo, fig_html, data_inicio, data_fim):
    """Gera HTML para converter em PDF com detalhamento por caminhão e gráfico"""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Relatório de Programações - JASFALTO</title>
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
            h3 {{
                color: #2c3e50;
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
            .page-break {{
                page-break-before: always;
            }}
        </style>
    </html>
    <body>
        <div class="header">
            <h1>JASFALTO - Relatório de Programações</h1>
        </div>
        <div class="periodo">
            <strong>Período:</strong> {data_inicio} a {data_fim}
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
            <p>Sistema desenvolvido para gestão de programações de usinagem</p>
        </div>
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
    
    if registros_expandidos:
        return pd.DataFrame(registros_expandidos)
    return pd.DataFrame()

# ==================== CONEXÃO COM GOOGLE SHEETS ====================

def conectar_google_sheets():
    """Conecta ao Google Sheets e garante que as abas existam"""
    try:
        if 'google' not in st.secrets:
            st.error("Configure as secrets do Google Sheets no Streamlit Cloud")
            return None, None, None
        
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            st.secrets["google"], 
            scope
        )
        client = gspread.authorize(creds)
        
        sheet_id = st.secrets["google_sheet_id"]
        spreadsheet = client.open_by_key(sheet_id)
        
        try:
            worksheet_usuarios = spreadsheet.worksheet("usuarios")
        except gspread.exceptions.WorksheetNotFound:
            worksheet_usuarios = spreadsheet.add_worksheet(title="usuarios", rows="100", cols="20")
            cabecalhos = ['username', 'password_hash', 'nome', 'email', 'telefone', 'cargo', 'tipo', 'data_cadastro']
            worksheet_usuarios.insert_row(cabecalhos, 1)
        
        try:
            worksheet_programacoes = spreadsheet.worksheet("programacoes")
        except gspread.exceptions.WorksheetNotFound:
            worksheet_programacoes = spreadsheet.add_worksheet(title="programacoes", rows="100", cols="20")
            cabecalhos = ['id', 'username', 'cliente', 'cliente_outros', 'data', 'produto', 'toneladas', 
                         'quant_caminhoes', 'placas', 'transportador', 'usina', 'status', 'data_solicitacao', 'observacoes']
            worksheet_programacoes.insert_row(cabecalhos, 1)
        
        return spreadsheet, worksheet_usuarios, worksheet_programacoes
    except Exception as e:
        st.error(f"Erro ao conectar ao Google Sheets: {e}")
        return None, None, None

def carregar_usuarios():
    """Carrega usuários do Google Sheets"""
    try:
        _, worksheet, _ = conectar_google_sheets()
        if worksheet:
            dados = worksheet.get_all_records()
            if dados and len(dados) > 0:
                df = pd.DataFrame(dados)
                colunas_necessarias = ['username', 'password_hash', 'nome', 'email', 'telefone', 'cargo', 'tipo', 'data_cadastro']
                for col in colunas_necessarias:
                    if col not in df.columns:
                        df[col] = ''
                
                # Verificar se os usuários uberaba e araguari existem
                usuarios_existentes = df['username'].tolist() if 'username' in df.columns else []
                
                if 'uberaba' not in usuarios_existentes:
                    uberaba_hash = hashlib.sha256("uberaba123".encode()).hexdigest()
                    nova_linha = ['uberaba', uberaba_hash, 'Administrador Uberaba', 'uberaba@jasfalto.com', '', 'Administrador Usina Uberaba', 'admin_usina', datetime.now().isoformat()]
                    worksheet.append_row(nova_linha)
                
                if 'araguari' not in usuarios_existentes:
                    araguari_hash = hashlib.sha256("araguari123".encode()).hexdigest()
                    nova_linha = ['araguari', araguari_hash, 'Administrador Araguari', 'araguari@jasfalto.com', '', 'Administrador Usina Araguari', 'admin_usina', datetime.now().isoformat()]
                    worksheet.append_row(nova_linha)
                
                # Recarregar os dados após adicionar
                dados = worksheet.get_all_records()
                df = pd.DataFrame(dados)
                
                return df
            else:
                # Criar usuários padrão se a planilha estiver vazia
                df = pd.DataFrame(columns=['username', 'password_hash', 'nome', 'email', 'telefone', 'cargo', 'tipo', 'data_cadastro'])
                
                # Admin Master
                admin_hash = hashlib.sha256("admin123".encode()).hexdigest()
                admin_row = ['admin', admin_hash, 'Administrador Master', 'admin@jasfalto.com', '', 'Master', 'admin', datetime.now().isoformat()]
                worksheet.append_row(admin_row)
                
                # Usuário Uberaba
                uberaba_hash = hashlib.sha256("uberaba123".encode()).hexdigest()
                uberaba_row = ['uberaba', uberaba_hash, 'Administrador Uberaba', 'uberaba@jasfalto.com', '', 'Administrador Usina Uberaba', 'admin_usina', datetime.now().isoformat()]
                worksheet.append_row(uberaba_row)
                
                # Usuário Araguari
                araguari_hash = hashlib.sha256("araguari123".encode()).hexdigest()
                araguari_row = ['araguari', araguari_hash, 'Administrador Araguari', 'araguari@jasfalto.com', '', 'Administrador Usina Araguari', 'admin_usina', datetime.now().isoformat()]
                worksheet.append_row(araguari_row)
                
                return df
        return pd.DataFrame(columns=['username', 'password_hash', 'nome', 'email', 'telefone', 'cargo', 'tipo', 'data_cadastro'])
    except Exception as e:
        st.error(f"Erro ao carregar usuários: {e}")
        return pd.DataFrame()

def salvar_usuario(username, password_hash, nome, email, telefone, cargo, tipo):
    """Salva novo usuário no Google Sheets"""
    try:
        spreadsheet, worksheet, _ = conectar_google_sheets()
        if worksheet:
            dados = worksheet.get_all_records()
            for row in dados:
                if row.get('username') == username:
                    return False
            
            nova_linha = [username, password_hash, nome, email, telefone, cargo, tipo, datetime.now().isoformat()]
            worksheet.append_row(nova_linha)
            return True
    except Exception as e:
        st.error(f"Erro ao salvar usuário: {e}")
        return False
    return False

def carregar_programacoes():
    """Carrega programações do Google Sheets"""
    try:
        _, _, worksheet = conectar_google_sheets()
        if worksheet:
            dados = worksheet.get_all_records()
            if dados:
                df = pd.DataFrame(dados)
                if 'data' in df.columns:
                    df['data'] = pd.to_datetime(df['data']).dt.date
                if 'data_solicitacao' in df.columns:
                    df['data_solicitacao'] = pd.to_datetime(df['data_solicitacao'])
                return df
        return pd.DataFrame(columns=[
            'id', 'username', 'cliente', 'cliente_outros', 'data', 'produto', 'toneladas', 
            'quant_caminhoes', 'placas', 'transportador', 'usina', 'status', 'data_solicitacao', 'observacoes'
        ])
    except Exception as e:
        st.error(f"Erro ao carregar programações: {e}")
        return pd.DataFrame()

def salvar_programacao(programacao):
    """Salva nova programação no Google Sheets"""
    try:
        _, _, worksheet = conectar_google_sheets()
        if worksheet:
            nova_linha = [
                programacao['id'],
                programacao['username'],
                programacao['cliente'],
                programacao['cliente_outros'],
                programacao['data'].isoformat(),
                programacao['produto'],
                programacao['toneladas'],
                programacao['quant_caminhoes'],
                programacao['placas'],
                programacao['transportador'],
                programacao['usina'],
                programacao['status'],
                programacao['data_solicitacao'].isoformat(),
                programacao['observacoes']
            ]
            worksheet.append_row(nova_linha)
            return True
    except Exception as e:
        st.error(f"Erro ao salvar programação: {e}")
        return False
    return False

def atualizar_status_programacao(id_programacao, novo_status):
    """Atualiza o status de uma programação"""
    try:
        _, _, worksheet = conectar_google_sheets()
        if worksheet:
            dados = worksheet.get_all_records()
            for idx, row in enumerate(dados, start=2):
                if str(row.get('id', '')) == str(id_programacao):
                    coluna_status = list(row.keys()).index('status') + 1
                    worksheet.update_cell(idx, coluna_status, novo_status)
                    return True
        return False
    except Exception as e:
        st.error(f"Erro ao atualizar status: {e}")
        return False

def adicionar_programacao(username, cliente, cliente_outros, data, produto, toneladas, 
                         quant_caminhoes, placas, transportador, usina, observacoes):
    """Adiciona nova programação"""
    df = carregar_programacoes()
    
    novo_id = len(df) + 1 if not df.empty else 1
    
    nome_cliente = cliente
    if cliente == "OUTROS" and cliente_outros:
        nome_cliente = cliente_outros
    
    programacao = {
        'id': novo_id,
        'username': username,
        'cliente': nome_cliente,
        'cliente_outros': cliente_outros if cliente == "OUTROS" else "",
        'data': data,
        'produto': produto,
        'toneladas': toneladas,
        'quant_caminhoes': quant_caminhoes,
        'placas': placas,
        'transportador': transportador,
        'usina': usina,
        'status': 'Pendente',
        'data_solicitacao': datetime.now(),
        'observacoes': observacoes
    }
    
    if salvar_programacao(programacao):
        return novo_id
    return None

def autenticar_usuario(username, password):
    """Verifica credenciais do usuário"""
    df_usuarios = carregar_usuarios()
    
    if df_usuarios.empty:
        return None
    
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    if 'username' not in df_usuarios.columns:
        st.error("Erro na estrutura da planilha. Contate o administrador.")
        return None
    
    usuario = df_usuarios[df_usuarios['username'] == username]
    if not usuario.empty and usuario.iloc[0]['password_hash'] == password_hash:
        tipo_usuario = usuario.iloc[0]['tipo'] if 'tipo' in usuario.columns else 'cliente'
        
        # Se for uberaba ou araguari, garantir que o tipo seja 'admin_usina'
        if username == 'uberaba' or username == 'araguari':
            tipo_usuario = 'admin_usina'
        
        return {
            'username': username,
            'nome': usuario.iloc[0]['nome'],
            'cargo': usuario.iloc[0]['cargo'] if 'cargo' in usuario.columns else '',
            'tipo': tipo_usuario
        }
    return None

def cadastrar_novo_usuario(username, password, nome, email, telefone, cargo, tipo='cliente'):
    """Cadastra novo usuário"""
    df_usuarios = carregar_usuarios()
    
    if 'username' not in df_usuarios.columns:
        st.error("Erro na estrutura da planilha. Contate o administrador.")
        return False
    
    if username in df_usuarios['username'].values:
        return False
    
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    if salvar_usuario(username, password_hash, nome, email, telefone, cargo, tipo):
        return True
    return False

def resetar_senha_usuario(username, nova_senha):
    """Reseta a senha de um usuário"""
    try:
        spreadsheet, worksheet, _ = conectar_google_sheets()
        if worksheet:
            dados = worksheet.get_all_records()
            
            # Encontrar o usuário
            for idx, row in enumerate(dados, start=2):
                if row.get('username') == username:
                    # Gerar novo hash da senha
                    nova_senha_hash = hashlib.sha256(nova_senha.encode()).hexdigest()
                    
                    # Encontrar a coluna password_hash
                    colunas = list(row.keys())
                    coluna_senha = colunas.index('password_hash') + 1
                    
                    # Atualizar a senha
                    worksheet.update_cell(idx, coluna_senha, nova_senha_hash)
                    return True
        return False
    except Exception as e:
        st.error(f"Erro ao resetar senha: {e}")
        return False

# ==================== INTERFACE DO CLIENTE ====================

def pagina_cliente(usuario):
    """Página para clientes fazerem programações"""
    
    st.title(f"🏭 Bem-vindo, {usuario['nome']}!")
    if usuario.get('cargo'):
        st.caption(f"Cargo: {usuario['cargo']}")
    st.markdown("### 📝 Faça sua Programação Diária")
    
    st.markdown("⚠️ **Campos com * são obrigatórios**")
    st.markdown("---")
    
    with st.form("form_programacao"):
        col1, col2 = st.columns(2)
        
        with col1:
            data_programacao = st.date_input(
                "Data da Usinagem *",
                min_value=date.today(),
                value=date.today()
            )
            
            opcoes_clientes = [
                "CONCEBRA - CONCESSIONARIA DAS RODOVIAS CENTRAIS DO BRASIL S.A.",
                "WAY 262 - CONCESSIONARIA DA RODOVIA BR 262 MG S.A.",
                "WAY 153 - CONCESSIONARIA ROTA SERTANEJA MG-GO S.A",
                "EPR TRIÂNGULO - CONCESSIONARIA RODOVIAS DO TRIANGULO SPE S.A.",
                "ECO050 - CONCESSIONARIA DE RODOVIAS S.A.",
                "PAVIÁGIL CONSTRUÇÕES E COMÉRCIO LTDA",
                "OUTROS"
            ]
            
            cliente_selecionado = st.selectbox(
                "Cliente (responsável pelo pagamento) *",
                opcoes_clientes
            )
            
            cliente_outros = ""
            if cliente_selecionado == "OUTROS":
                cliente_outros = st.text_input("Digite o nome do cliente *")
            
            produto = st.selectbox(
                "Produto *",
                ["Faixa B", "Faixa C", "Faixa D", "Faixa D Aditivado", "EGL 16-19", "Gap-Graded", "PMQ", "Emulsão RR-1C", "CM-IMP"]
            )
            
            toneladas = st.number_input(
                "Quantidade (Toneladas) *",
                min_value=1.0,
                max_value=5000.0,
                step=10.0,
                format="%.1f",
                value=1.0
            )
        
        with col2:
            quant_caminhoes = st.number_input(
                "Quantidade de Caminhões *",
                min_value=1,
                max_value=50,
                step=1,
                value=1
            )
            
            st.markdown("#### Placas dos Caminhões *")
            placas = []
            todas_placas_preenchidas = True
            for i in range(quant_caminhoes):
                placa = st.text_input(
                    f"Caminhão {i+1} (formato: XXX-XXXX)",
                    key=f"placa_{i}",
                    placeholder="Ex: ABC-1234"
                )
                placas.append(placa)
                if not placa:
                    todas_placas_preenchidas = False
            
            placas_str = ", ".join([p for p in placas if p])
            
            transportador = st.text_input(
                "Transportador (responsável pelo transporte) *",
                placeholder="Digite o nome da transportadora"
            )
            
            usina = st.selectbox(
                "Usina - Localidade *",
                ["Jasfalto - Uberaba/MG", "Jasfalto - Araguari/MG"]
            )
            
            observacoes = st.text_area("Observações (opcional)", height=100)
        
        submitted = st.form_submit_button("📊 Enviar Programação", use_container_width=True)
        
        if submitted:
            erros = []
            
            if cliente_selecionado == "OUTROS" and not cliente_outros:
                erros.append("❌ Digite o nome do cliente")
            
            if not transportador:
                erros.append("❌ Informe o transportador responsável")
            
            if quant_caminhoes > 0 and not todas_placas_preenchidas:
                erros.append("❌ Preencha a placa de todos os caminhões")
            
            if toneladas <= 0:
                erros.append("❌ Informe a quantidade de toneladas")
            
            if erros:
                st.error("⚠️ **Não foi possível enviar a programação. Preencha todos os campos obrigatórios:**")
                for erro in erros:
                    st.write(erro)
            else:
                prog_id = adicionar_programacao(
                    usuario['username'],
                    cliente_selecionado,
                    cliente_outros,
                    data_programacao,
                    produto,
                    toneladas,
                    quant_caminhoes,
                    placas_str,
                    transportador,
                    usina,
                    observacoes
                )
                if prog_id:
                    st.success(f"✅ Programação #{prog_id} enviada com sucesso!")
                    st.balloons()
                else:
                    st.error("Erro ao salvar programação. Tente novamente.")
    
    st.markdown("---")
    st.markdown("### 📋 Minhas Programações")
    
    df_prog = carregar_programacoes()
    if not df_prog.empty and 'username' in df_prog.columns:
        minhas_progs = df_prog[df_prog['username'] == usuario['username']].sort_values('data', ascending=False)
        
        if not minhas_progs.empty:
            def cor_status(val):
                colors = {
                    'Pendente': '🟡',
                    'Confirmada': '🟢',
                    'Cancelada': '❌'
                }
                return f"{colors.get(val, '⚪')} {val}"
            
            display_df = minhas_progs[['id', 'data', 'cliente', 'produto', 'toneladas', 'quant_caminhoes', 'placas', 'transportador', 'usina', 'status']].copy()
            display_df['status'] = display_df['status'].apply(cor_status)
            display_df.columns = ['ID', 'Data', 'Cliente', 'Produto', 'Toneladas', 'Qtde Caminhões', 'Placas', 'Transportador', 'Usina', 'Status']
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)
        else:
            st.info("Você ainda não fez nenhuma programação.")
    else:
        st.info("Nenhuma programação encontrada.")

# ==================== INTERFACE DO ADMIN ====================

def pagina_admin(usuario):
    """Página administrativa para gerenciar programações"""
    
    st.title(f"⚙️ Painel Administrativo - {usuario['nome']}")
    
    # Se for admin de usina, definir qual usina ele pode ver
    if usuario['tipo'] == 'admin_usina':
        if usuario['username'] == 'uberaba':
            usina_permitida = "Jasfalto - Uberaba/MG"
            st.info(f"🔒 Você está visualizando apenas programações da usina: **{usina_permitida}**")
        elif usuario['username'] == 'araguari':
            usina_permitida = "Jasfalto - Araguari/MG"
            st.info(f"🔒 Você está visualizando apenas programações da usina: **{usina_permitida}**")
        else:
            usina_permitida = None
    else:
        usina_permitida = None
    
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "📋 Programações", "👥 Clientes", "⚙️ Configurações"])
    
    with tab1:
        st.markdown("### Dashboard de Programações")
        
        df_prog = carregar_programacoes()
        
        if not df_prog.empty:
            # Filtrar por usina se for admin_usina
            if usina_permitida:
                df_prog = df_prog[df_prog['usina'] == usina_permitida]
            
            # Filtros do Dashboard
            st.markdown("#### Filtros")
            col_f1, col_f2, col_f3, col_f4 = st.columns(4)
            
            with col_f1:
                data_inicio = st.date_input("Data Início", value=date.today())
            with col_f2:
                data_fim = st.date_input("Data Fim", value=date.today())
            with col_f3:
                if usina_permitida:
                    st.markdown(f"**Usina:** {usina_permitida}")
                    usina_filtro = usina_permitida
                else:
                    usina_filtro = st.selectbox(
                        "Usina",
                        ["Todas", "Jasfalto - Uberaba/MG", "Jasfalto - Araguari/MG"]
                    )
            with col_f4:
                status_filtro = st.multiselect(
                    "Status",
                    options=['Pendente', 'Confirmada', 'Cancelada'],
                    default=['Pendente', 'Confirmada']
                )
            
            # Aplicar filtros
            df_filtrado = df_prog[(df_prog['data'] >= data_inicio) & (df_prog['data'] <= data_fim)]
            
            if not usina_permitida and usina_filtro != "Todas":
                df_filtrado = df_filtrado[df_filtrado['usina'] == usina_filtro]
            
            if status_filtro:
                df_filtrado = df_filtrado[df_filtrado['status'].isin(status_filtro)]
            
            # Botão para gerar PDF
            if st.button("📄 Gerar Relatório PDF", use_container_width=True):
                if not df_filtrado.empty:
                    df_detalhado = expandir_por_caminhao(df_filtrado)
                    
                    if not df_detalhado.empty:
                        df_pdf_detalhado = df_detalhado[['cliente', 'data', 'produto', 'placa', 'transportador', 'usina', 'status']].copy()
                        df_pdf_detalhado.columns = ['Cliente', 'Data', 'Produto', 'Placa', 'Transportador', 'Usina', 'Status']
                        
                        resumo = df_filtrado.groupby('cliente').agg({
                            'toneladas': 'sum',
                            'quant_caminhoes': 'sum'
                        }).reset_index()
                        resumo.columns = ['Cliente', 'Total Toneladas', 'Total de Viagens']
                        
                        fig = gerar_grafico_toneladas_por_data_produto(df_filtrado)
                        fig_html = fig.to_html(full_html=False, include_plotlyjs='cdn')
                        
                        html = gerar_pdf_html(df_pdf_detalhado, resumo, fig_html, data_inicio.strftime('%d/%m/%Y'), data_fim.strftime('%d/%m/%Y'))
                        
                        st.download_button(
                            label="📥 Baixar PDF",
                            data=html.encode(),
                            file_name=f"relatorio_programacoes_{data_inicio.strftime('%Y%m%d')}_{data_fim.strftime('%Y%m%d')}.html",
                            mime="text/html",
                            use_container_width=True
                        )
                    else:
                        st.warning("Não foi possível gerar o relatório. Verifique os dados.")
                else:
                    st.warning("Nenhum dado encontrado no período selecionado.")
            
            st.markdown("---")
            
            # Gráfico
            st.markdown("#### Toneladas por Data e Produto")
            
            if not df_filtrado.empty:
                fig = gerar_grafico_toneladas_por_data_produto(df_filtrado)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Sem dados para exibir no gráfico")
            
            # Métricas
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_progs = len(df_filtrado)
                st.metric("Total de Programações", total_progs)
            
            with col2:
                total_ton = df_filtrado['toneladas'].sum()
                st.metric("Toneladas Totais", f"{total_ton:,.0f} t")
            
            with col3:
                pendentes = len(df_filtrado[df_filtrado['status'] == 'Pendente'])
                st.metric("Pendentes", pendentes)
            
            with col4:
                total_caminhoes = df_filtrado['quant_caminhoes'].sum()
                st.metric("Total de Viagens", f"{total_caminhoes:,.0f}")
            
            # Gráfico de toneladas por produto
            st.markdown("#### Toneladas por Produto")
            ton_por_produto = df_filtrado.groupby('produto')['toneladas'].sum().reset_index()
            if not ton_por_produto.empty:
                fig2 = px.pie(ton_por_produto, values='toneladas', names='produto', title="Distribuição por Produto")
                st.plotly_chart(fig2, use_container_width=True)
            
            # Tabela de dados
            st.markdown("#### Dados Filtrados")
            st.dataframe(df_filtrado[['id', 'cliente', 'data', 'produto', 'toneladas', 'quant_caminhoes', 'usina', 'status']], 
                        use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma programação cadastrada ainda.")
    
    with tab2:
        st.markdown("### Gerenciar Programações")
        
        df_prog = carregar_programacoes()
        
        if not df_prog.empty:
            if usina_permitida:
                df_prog = df_prog[df_prog['usina'] == usina_permitida]
            
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                filtro_status = st.multiselect(
                    "Filtrar por Status",
                    options=['Pendente', 'Confirmada', 'Cancelada'],
                    default=['Pendente', 'Confirmada']
                )
            with col_f2:
                filtro_data = st.date_input("Filtrar por Data", value=None)
            
            df_filtrado = df_prog.copy()
            if filtro_status:
                df_filtrado = df_filtrado[df_filtrado['status'].isin(filtro_status)]
            if filtro_data:
                df_filtrado = df_filtrado[df_filtrado['data'] == filtro_data]
            
            st.markdown("#### Programações")
            
            for idx, row in df_filtrado.iterrows():
                with st.expander(f"📦 Programação #{row['id']} - {row['cliente']} - {row['data']} - Usuário: {row['username']}"):
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        st.write(f"**Produto:** {row['produto']}")
                        st.write(f"**Toneladas:** {row['toneladas']} t")
                        st.write(f"**Quantidade Caminhões:** {row['quant_caminhoes']}")
                        st.write(f"**Placas:** {row['placas'] if pd.notna(row['placas']) else 'Não informado'}")
                        st.write(f"**Transportador:** {row['transportador'] if pd.notna(row['transportador']) else 'Não informado'}")
                        st.write(f"**Usina:** {row['usina'] if pd.notna(row['usina']) else 'Não informado'}")
                    with col_b:
                        novo_status = st.selectbox(
                            "Status",
                            options=['Pendente', 'Confirmada', 'Cancelada'],
                            index=['Pendente', 'Confirmada', 'Cancelada'].index(row['status']) if row['status'] in ['Pendente', 'Confirmada', 'Cancelada'] else 0,
                            key=f"status_{row['id']}"
                        )
                        if novo_status != row['status']:
                            if atualizar_status_programacao(row['id'], novo_status):
                                st.rerun()
        else:
            st.info("Nenhuma programação cadastrada.")
    
    with tab3:
        st.markdown("### Gerenciar Clientes")
        
        if usuario['tipo'] == 'admin':
            df_usuarios = carregar_usuarios()
            
            if not df_usuarios.empty and 'tipo' in df_usuarios.columns:
                # Clientes comuns
                clientes = df_usuarios[df_usuarios['tipo'] == 'cliente']
                
                # Administradores de usina
                admins_usina = df_usuarios[df_usuarios['tipo'] == 'admin_usina']
                
                # Admin master
                admin_master = df_usuarios[df_usuarios['tipo'] == 'admin']
                
                # Exibir clientes
                if not clientes.empty:
                    st.markdown("#### 👥 Clientes")
                    st.dataframe(
                        clientes[['username', 'nome', 'email', 'telefone', 'cargo', 'data_cadastro']],
                        use_container_width=True,
                        hide_index=True
                    )
                
                # Exibir administradores de usina
                if not admins_usina.empty:
                    st.markdown("#### 🔐 Administradores de Usina")
                    st.dataframe(
                        admins_usina[['username', 'nome', 'email', 'telefone', 'cargo', 'data_cadastro']],
                        use_container_width=True,
                        hide_index=True
                    )
                
                st.markdown("---")
                
                # Ferramenta de Reset de Senha
                st.markdown("### 🔑 Resetar Senha de Usuário")
                st.warning("⚠️ Esta ação irá alterar a senha do usuário imediatamente.")
                
                col_r1, col_r2 = st.columns(2)
                
                with col_r1:
                    usuarios_lista = df_usuarios[df_usuarios['username'] != 'admin']['username'].tolist()
                    
                    if usuarios_lista:
                        usuario_reset = st.selectbox(
                            "Selecione o usuário",
                            options=usuarios_lista,
                            key="select_usuario_reset"
                        )
                    else:
                        st.info("Nenhum usuário cadastrado para resetar senha.")
                        usuario_reset = None
                
                with col_r2:
                    nova_senha = st.text_input(
                        "Nova senha",
                        type="password",
                        placeholder="Digite a nova senha",
                        key="nova_senha_reset"
                    )
                    confirmar_senha = st.text_input(
                        "Confirmar nova senha",
                        type="password",
                        placeholder="Confirme a nova senha",
                        key="confirmar_senha_reset"
                    )
                
                if st.button("🔄 Resetar Senha", use_container_width=True, key="btn_reset_senha"):
                    if usuario_reset and nova_senha:
                        if nova_senha == confirmar_senha:
                            if resetar_senha_usuario(usuario_reset, nova_senha):
                                st.success(f"✅ Senha do usuário **{usuario_reset}** resetada com sucesso!")
                                st.info(f"Nova senha: `{nova_senha}`")
                                st.balloons()
                                st.rerun()
                            else:
                                st.error("Erro ao resetar a senha. Tente novamente.")
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
                                st.success(f"Cliente {novo_nome} cadastrado com sucesso!")
                                st.rerun()
                            else:
                                st.error("Usuário já existe!")
                        else:
                            st.error("Preencha todos os campos obrigatórios!")
        else:
            st.info("👑 Apenas o Administrador Master pode gerenciar clientes e resetar senhas.")
    
    with tab4:
        st.markdown("### Configurações")
        st.info("✅ Dados salvos permanentemente no Google Sheets. Não há risco de perda de dados.")
        st.info("📋 As programações são salvas em tempo real e podem ser consultadas a qualquer momento.")
        st.info("🏭 Usinas disponíveis: Jasfalto - Uberaba/MG e Jasfalto - Araguari/MG")
        
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
    """Função principal"""
    
    logo = carregar_logo()
    
    if 'autenticado' not in st.session_state:
        st.session_state.autenticado = False
    
    if not st.session_state.autenticado:
        if logo:
            col_logo1, col_logo2, col_logo3 = st.columns([1, 1, 1])
            with col_logo2:
                st.image(logo, width=200)
        
        st.title("🏭 Sistema de Gestão de Usinagem - JASFALTO")
        st.markdown("### Acesso ao Sistema")
        
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
                            st.error("Preencha todos os campos obrigatórios!")
                        elif nova_senha != confirma_senha:
                            st.error("As senhas não conferem!")
                        else:
                            if cadastrar_novo_usuario(novo_username, nova_senha, novo_nome, novo_email, novo_telefone, novo_cargo):
                                st.success("Cadastro realizado com sucesso! Faça login para continuar.")
                                st.balloons()
                            else:
                                st.error("Usuário já existe! Escolha outro nome de usuário.")
    
    else:
        with st.sidebar:
            if logo:
                st.image(logo, width=150)
                st.markdown("---")
            
            st.markdown(f"### 👤 {st.session_state.usuario['nome']}")
            if st.session_state.usuario.get('cargo'):
                st.markdown(f"*{st.session_state.usuario['cargo']}*")
            st.markdown(f"*{st.session_state.usuario['tipo'].upper()}*")
            st.markdown("---")
            
            if st.button("🚪 Sair", use_container_width=True):
                st.session_state.autenticado = False
                st.session_state.usuario = None
                st.rerun()
        
        if st.session_state.usuario['tipo'] in ['admin', 'admin_usina']:
            pagina_admin(st.session_state.usuario)
        else:
            pagina_cliente(st.session_state.usuario)

if __name__ == "__main__":
    main()
