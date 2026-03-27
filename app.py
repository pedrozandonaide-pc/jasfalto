import streamlit as st
import pandas as pd
from datetime import datetime, date
import plotly.express as px
import os
import hashlib

# Configuração da página
st.set_page_config(
    page_title="Gestão de Usinagem - CBUQ",
    page_icon="🏭",
    layout="wide"
)

# ==================== FUNÇÕES DE BANCO DE DADOS ====================

def init_database():
    """Inicializa os arquivos CSV se não existirem"""
    
    # Criar pasta database se não existir
    if not os.path.exists('database'):
        os.makedirs('database')
    
    # Inicializar usuários
    if not os.path.exists('database/usuarios.csv'):
        df_usuarios = pd.DataFrame(columns=[
            'username', 'password_hash', 'nome', 'email', 'telefone', 'tipo', 'data_cadastro'
        ])
        # Criar usuário admin padrão
        admin_hash = hashlib.sha256("admin123".encode()).hexdigest()
        df_usuarios.loc[0] = ['admin', admin_hash, 'Administrador', 'admin@asfalto.com', '', 'admin', datetime.now()]
        df_usuarios.to_csv('database/usuarios.csv', index=False)
    
    # Inicializar programações
    if not os.path.exists('database/programacoes.csv'):
        df_prog = pd.DataFrame(columns=[
            'id', 'cliente', 'data', 'tipo_cbuq', 'toneladas', 'horario', 
            'local', 'status', 'data_solicitacao', 'observacoes'
        ])
        df_prog.to_csv('database/programacoes.csv', index=False)

def carregar_usuarios():
    """Carrega lista de usuários"""
    return pd.read_csv('database/usuarios.csv')

def carregar_programacoes():
    """Carrega programações"""
    df = pd.read_csv('database/programacoes.csv')
    if not df.empty and 'data' in df.columns:
        df['data'] = pd.to_datetime(df['data']).dt.date
        df['data_solicitacao'] = pd.to_datetime(df['data_solicitacao'])
    return df

def salvar_programacoes(df):
    """Salva programações"""
    df.to_csv('database/programacoes.csv', index=False)

def adicionar_programacao(cliente, data, tipo_cbuq, toneladas, horario, local, observacoes):
    """Adiciona nova programação"""
    df = carregar_programacoes()
    
    # Gerar ID
    novo_id = len(df) + 1 if not df.empty else 1
    
    nova_prog = pd.DataFrame([{
        'id': novo_id,
        'cliente': cliente,
        'data': data,
        'tipo_cbuq': tipo_cbuq,
        'toneladas': toneladas,
        'horario': horario,
        'local': local,
        'status': 'Pendente',
        'data_solicitacao': datetime.now(),
        'observacoes': observacoes
    }])
    
    df = pd.concat([df, nova_prog], ignore_index=True)
    salvar_programacoes(df)
    return novo_id

def autenticar_usuario(username, password):
    """Verifica credenciais do usuário"""
    df_usuarios = carregar_usuarios()
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    usuario = df_usuarios[df_usuarios['username'] == username]
    if not usuario.empty and usuario.iloc[0]['password_hash'] == password_hash:
        return {
            'username': username,
            'nome': usuario.iloc[0]['nome'],
            'tipo': usuario.iloc[0]['tipo']
        }
    return None

def cadastrar_novo_usuario(username, password, nome, email, telefone, tipo='cliente'):
    """Cadastra novo usuário"""
    df_usuarios = carregar_usuarios()
    
    # Verificar se usuário já existe
    if username in df_usuarios['username'].values:
        return False
    
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    novo_usuario = pd.DataFrame([{
        'username': username,
        'password_hash': password_hash,
        'nome': nome,
        'email': email,
        'telefone': telefone,
        'tipo': tipo,
        'data_cadastro': datetime.now()
    }])
    
    df_usuarios = pd.concat([df_usuarios, novo_usuario], ignore_index=True)
    df_usuarios.to_csv('database/usuarios.csv', index=False)
    return True

# ==================== INTERFACE DO CLIENTE ====================

def pagina_cliente(usuario):
    """Página para clientes fazerem programações"""
    
    st.title(f"🏭 Bem-vindo, {usuario['nome']}!")
    st.markdown("### 📝 Faça sua Programação Diária")
    
    # Formulário de programação
    with st.form("form_programacao"):
        col1, col2 = st.columns(2)
        
        with col1:
            data_programacao = st.date_input(
                "Data da Usinagem",
                min_value=date.today(),
                value=date.today()
            )
            
            tipo_cbuq = st.selectbox(
                "Tipo de CBUQ",
                ["CBUQ 0/19", "CBUQ 0/25", "CBUQ 0/12,5", "CBUQ 0/9,5", "CBUQ 0/32"]
            )
            
            toneladas = st.number_input(
                "Quantidade (Toneladas)",
                min_value=1.0,
                max_value=5000.0,
                step=10.0,
                format="%.1f"
            )
        
        with col2:
            horario = st.time_input("Horário Desejado", value=datetime.now().time())
            
            local = st.text_input("Local da Obra / Entrega")
            
            observacoes = st.text_area("Observações (opcional)", height=100)
        
        submitted = st.form_submit_button("📊 Enviar Programação", use_container_width=True)
        
        if submitted:
            if not local:
                st.error("Por favor, informe o local da obra!")
            else:
                prog_id = adicionar_programacao(
                    usuario['username'],
                    data_programacao,
                    tipo_cbuq,
                    toneladas,
                    horario.strftime("%H:%M"),
                    local,
                    observacoes
                )
                st.success(f"✅ Programação #{prog_id} enviada com sucesso!")
                st.balloons()
    
    # Exibir programações do cliente
    st.markdown("---")
    st.markdown("### 📋 Minhas Programações")
    
    df_prog = carregar_programacoes()
    if not df_prog.empty:
        # Filtrar programações do cliente
        minhas_progs = df_prog[df_prog['cliente'] == usuario['username']].sort_values('data', ascending=False)
        
        if not minhas_progs.empty:
            # Cores por status
            def cor_status(val):
                colors = {
                    'Pendente': '🟡',
                    'Confirmada': '🟢',
                    'Em Produção': '🔵',
                    'Entregue': '✅',
                    'Cancelada': '❌'
                }
                return f"{colors.get(val, '⚪')} {val}"
            
            # Exibir tabela
            display_df = minhas_progs[['id', 'data', 'tipo_cbuq', 'toneladas', 'horario', 'local', 'status']].copy()
            display_df['status'] = display_df['status'].apply(cor_status)
            display_df.columns = ['ID', 'Data', 'Tipo', 'Toneladas', 'Horário', 'Local', 'Status']
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)
        else:
            st.info("Você ainda não fez nenhuma programação.")
    else:
        st.info("Nenhuma programação encontrada.")

# ==================== INTERFACE DO ADMIN ====================

def pagina_admin(usuario):
    """Página administrativa para gerenciar programações"""
    
    st.title(f"⚙️ Painel Administrativo - {usuario['nome']}")
    
    # Abas para diferentes funções
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "📋 Programações", "👥 Clientes", "⚙️ Configurações"])
    
    with tab1:
        st.markdown("### Dashboard de Programações")
        
        df_prog = carregar_programacoes()
        
        if not df_prog.empty:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_progs = len(df_prog[df_prog['data'] >= date.today()])
                st.metric("Programações Futuras", total_progs)
            
            with col2:
                total_ton = df_prog[df_prog['data'] >= date.today()]['toneladas'].sum()
                st.metric("Toneladas Agendadas", f"{total_ton:,.0f} t")
            
            with col3:
                pendentes = len(df_prog[df_prog['status'] == 'Pendente'])
                st.metric("Pendentes", pendentes)
            
            with col4:
                clientes_unicos = df_prog['cliente'].nunique()
                st.metric("Clientes Ativos", clientes_unicos)
            
            # Gráfico de programações por dia
            st.markdown("#### Programações por Dia")
            prog_por_dia = df_prog[df_prog['data'] >= date.today()].groupby('data').size().reset_index(name='quantidade')
            if not prog_por_dia.empty:
                fig = px.bar(prog_por_dia, x='data', y='quantidade', title="Quantidade de Programações por Dia")
                st.plotly_chart(fig, use_container_width=True)
            
            # Gráfico de toneladas por tipo
            st.markdown("#### Toneladas por Tipo de CBUQ")
            ton_por_tipo = df_prog[df_prog['data'] >= date.today()].groupby('tipo_cbuq')['toneladas'].sum().reset_index()
            if not ton_por_tipo.empty:
                fig2 = px.pie(ton_por_tipo, values='toneladas', names='tipo_cbuq', title="Distribuição por Tipo")
                st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Nenhuma programação cadastrada ainda.")
    
    with tab2:
        st.markdown("### Gerenciar Programações")
        
        df_prog = carregar_programacoes()
        
        if not df_prog.empty:
            # Filtros
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                filtro_status = st.multiselect(
                    "Filtrar por Status",
                    options=['Pendente', 'Confirmada', 'Em Produção', 'Entregue', 'Cancelada'],
                    default=['Pendente', 'Confirmada']
                )
            with col_f2:
                filtro_data = st.date_input("Filtrar por Data", value=None)
            
            # Aplicar filtros
            df_filtrado = df_prog.copy()
            if filtro_status:
                df_filtrado = df_filtrado[df_filtrado['status'].isin(filtro_status)]
            if filtro_data:
                df_filtrado = df_filtrado[df_filtrado['data'] == filtro_data]
            
            # Tabela editável
            st.markdown("#### Programações")
            
            # Selecionar colunas para exibir
            colunas = ['id', 'cliente', 'data', 'tipo_cbuq', 'toneladas', 'horario', 'local', 'status']
            df_edit = df_filtrado[colunas].copy()
            
            # Editor de status
            for idx, row in df_edit.iterrows():
                with st.expander(f"📦 Programação #{row['id']} - {row['cliente']} - {row['data']}"):
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        st.write(f"**Tipo:** {row['tipo_cbuq']}")
                        st.write(f"**Toneladas:** {row['toneladas']} t")
                        st.write(f"**Horário:** {row['horario']}")
                        st.write(f"**Local:** {row['local']}")
                    with col_b:
                        novo_status = st.selectbox(
                            "Status",
                            options=['Pendente', 'Confirmada', 'Em Produção', 'Entregue', 'Cancelada'],
                            index=['Pendente', 'Confirmada', 'Em Produção', 'Entregue', 'Cancelada'].index(row['status']),
                            key=f"status_{row['id']}"
                        )
                        if novo_status != row['status']:
                            # Atualizar status
                            df_prog.loc[df_prog['id'] == row['id'], 'status'] = novo_status
                            salvar_programacoes(df_prog)
                            st.rerun()
        else:
            st.info("Nenhuma programação cadastrada.")
    
    with tab3:
        st.markdown("### Gerenciar Clientes")
        
        df_usuarios = carregar_usuarios()
        clientes = df_usuarios[df_usuarios['tipo'] == 'cliente']
        
        if not clientes.empty:
            st.dataframe(
                clientes[['username', 'nome', 'email', 'telefone', 'data_cadastro']],
                use_container_width=True,
                hide_index=True
            )
        
        with st.expander("➕ Cadastrar Novo Cliente"):
            with st.form("form_novo_cliente"):
                col_a, col_b = st.columns(2)
                with col_a:
                    novo_username = st.text_input("Usuário (login)")
                    novo_nome = st.text_input("Nome Completo")
                    novo_email = st.text_input("E-mail")
                with col_b:
                    nova_senha = st.text_input("Senha", type="password")
                    novo_telefone = st.text_input("Telefone (WhatsApp)")
                
                cadastrar = st.form_submit_button("Cadastrar Cliente")
                
                if cadastrar:
                    if all([novo_username, nova_senha, novo_nome, novo_email]):
                        if cadastrar_novo_usuario(novo_username, nova_senha, novo_nome, novo_email, novo_telefone):
                            st.success(f"Cliente {novo_nome} cadastrado com sucesso!")
                            st.rerun()
                        else:
                            st.error("Usuário já existe!")
                    else:
                        st.error("Preencha todos os campos obrigatórios!")
    
    with tab4:
        st.markdown("### Configurações")
        
        # Aqui você pode adicionar configurações como capacidade das usinas, etc.
        st.info("Em desenvolvimento - Configure aqui a capacidade diária das usinas, horários de funcionamento, etc.")

# ==================== LOGIN E MAIN ====================

def main():
    """Função principal"""
    
    init_database()
    
    # Login
    if 'autenticado' not in st.session_state:
        st.session_state.autenticado = False
    
    if not st.session_state.autenticado:
        st.title("🏭 Sistema de Gestão de Usinagem - CBUQ")
        st.markdown("### Acesso ao Sistema")
        
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
            
            st.markdown("---")
            st.markdown("### Não tem cadastro?")
            st.markdown("Entre em contato com o administrador para criar seu acesso.")
    
    else:
        # Logout na sidebar
        with st.sidebar:
            st.markdown(f"### 👤 {st.session_state.usuario['nome']}")
            st.markdown(f"*{st.session_state.usuario['tipo'].upper()}*")
            st.markdown("---")
            
            if st.button("🚪 Sair", use_container_width=True):
                st.session_state.autenticado = False
                st.session_state.usuario = None
                st.rerun()
        
        # Redirecionar para página correta
        if st.session_state.usuario['tipo'] == 'admin':
            pagina_admin(st.session_state.usuario)
        else:
            pagina_cliente(st.session_state.usuario)

if __name__ == "__main__":
    main()