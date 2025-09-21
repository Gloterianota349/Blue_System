#app.py
# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import random
import copy

# --- 1. CONFIGURAÇÕES E CONSTANTES ---

# Configuração da página para usar o layout largo e um ícone
st.set_page_config(layout="wide", page_title="Simulador SESI", page_icon="🏥")

# Duração média de cada exame em minutos
DURACAO_EXAMES = {
    'Eletrocardiograma': 8, 'Espirometria': 10, 'Eletroencefalograma': 20,
    'Teste ergométrico': 25, 'TVI': 6, 'Audiometria': 8,
    'Consulta oftalmológica': 15, 'Consulta Ocupacional': 12, 'Raio X': 6,
    'Exame de Sangue': 5
}
LISTA_TODOS_EXAMES = list(DURACAO_EXAMES.keys())

# Regras de Dependência
PRE_ERGOMETRICO = ['Eletrocardiograma', 'Eletroencefalograma', 'Espirometria', 'Consulta oftalmológica']

# --- 2. LÓGICA PRINCIPAL DA SIMULAÇÃO (Refatorada) ---

# Funções auxiliares (as mesmas do script anterior)
def calcular_tempo_total_fila(sala_id, estado_clinica):
    sala = estado_clinica[sala_id]
    tempo_total = sala['tempo_restante_atendimento']
    for _ in sala['fila']:
        tempo_total += DURACAO_EXAMES[sala_id]
    return tempo_total

def encontrar_proximo_exame(paciente, estado_clinica):
    exames_pendentes = [e for e in paciente['exames_necessarios'] if e not in paciente['exames_concluidos']]
    if not exames_pendentes: return None

    opcoes_viaveis = []
    if 'Exame de Sangue' in exames_pendentes and not paciente['exames_concluidos']:
        opcoes_viaveis = ['Exame de Sangue']
    elif len(exames_pendentes) == 1 and 'Consulta Ocupacional' in exames_pendentes:
        opcoes_viaveis = ['Consulta Ocupacional']
    else:
        opcoes_viaveis = [e for e in exames_pendentes if e != 'Consulta Ocupacional']
        if 'Teste ergométrico' in opcoes_viaveis:
            pre_req_necessarios = [p for p in PRE_ERGOMETRICO if p in paciente['exames_necessarios']]
            if not all(p in paciente['exames_concluidos'] for p in pre_req_necessarios):
                opcoes_viaveis.remove('Teste ergométrico')
    
    if not opcoes_viaveis: return None

    salas_livres = [e for e in opcoes_viaveis if estado_clinica[e]['status'] == 'livre']
    if salas_livres:
        return min(salas_livres, key=lambda e: DURACAO_EXAMES[e])
    else:
        return min(opcoes_viaveis, key=lambda e: calcular_tempo_total_fila(e, estado_clinica))

def gerar_cenario_aleatorio(num_pacientes, intervalo_chegada, max_exames_por_paciente):
    """Gera uma lista de pacientes com chegadas e exames aleatórios."""
    cenario = []
    tempo_chegada_atual = 0
    for i in range(num_pacientes):
        num_exames = random.randint(2, max_exames_por_paciente)
        bateria_exames = random.sample(LISTA_TODOS_EXAMES, num_exames)
        
        # Garante a lógica de dependências na criação do cenário
        if 'Teste ergométrico' in bateria_exames and not any(e in bateria_exames for e in PRE_ERGOMETRICO):
            bateria_exames.append(random.choice(PRE_ERGOMETRICO))
        
        cenario.append({
            'id': f'Paciente {i+1}',
            'chegada': tempo_chegada_atual,
            'exames': bateria_exames
        })
        tempo_chegada_atual += random.randint(intervalo_chegada - 2, intervalo_chegada + 2)
    return cenario


@st.cache_data # Cache para não re-executar a simulação desnecessariamente
def executar_simulacao(cenario_pacientes, duracao_simulacao):
    """Executa a simulação e retorna um histórico completo, minuto a minuto."""
    clinica = {nome: {'status': 'livre', 'paciente_em_atendimento': None, 'tempo_restante_atendimento': 0, 'fila': []} for nome in DURACAO_EXAMES}
    pacientes_ativos, pacientes_finalizados = [], []
    historico_completo = []

    for minuto_atual in range(duracao_simulacao):
        log_eventos_minuto = []

        # ETAPA A: ATUALIZAR SALAS
        for nome_sala, sala in clinica.items():
            if sala['status'] == 'ocupada':
                sala['tempo_restante_atendimento'] -= 1
                if sala['tempo_restante_atendimento'] <= 0:
                    paciente_id = sala['paciente_em_atendimento']
                    log_eventos_minuto.append(f"✅ {paciente_id} finalizou {nome_sala}.")
                    
                    for p in pacientes_ativos:
                        if p['id'] == paciente_id:
                            p['exames_concluidos'].append(nome_sala)
                            p['status'], p['local_atual'] = 'aguardando', 'corredor'
                            break
                    
                    if sala['fila']:
                        proximo_id = sala['fila'].pop(0)
                        sala['paciente_em_atendimento'] = proximo_id
                        sala['tempo_restante_atendimento'] = DURACAO_EXAMES[nome_sala]
                        log_eventos_minuto.append(f"▶️ {proximo_id} (da fila) iniciou {nome_sala}.")
                        for p in pacientes_ativos:
                            if p['id'] == proximo_id:
                                p['status'], p['local_atual'] = 'em_exame', nome_sala
                                break
                    else:
                        sala['status'], sala['paciente_em_atendimento'] = 'livre', None

        # ETAPA B: NOVAS CHEGADAS
        for p_info in cenario_pacientes:
            if p_info['chegada'] == minuto_atual:
                novo_paciente = {
                    'id': p_info['id'], 'chegada': minuto_atual, 'exames_necessarios': p_info['exames'],
                    'exames_concluidos': [], 'status': 'aguardando', 'local_atual': 'recepcao'
                }
                pacientes_ativos.append(novo_paciente)
                log_eventos_minuto.append(f"➡️ {novo_paciente['id']} chegou.")

        # ETAPA C: TOMAR DECISÕES
        for p in pacientes_ativos:
            if p['status'] == 'aguardando':
                destino = encontrar_proximo_exame(p, clinica)
                if destino:
                    sala_destino = clinica[destino]
                    if sala_destino['status'] == 'livre':
                        sala_destino.update({'status': 'ocupada', 'paciente_em_atendimento': p['id'], 'tempo_restante_atendimento': DURACAO_EXAMES[destino]})
                        p.update({'status': 'em_exame', 'local_atual': destino})
                        log_eventos_minuto.append(f"▶️ {p['id']} iniciou {destino}.")
                    else:
                        sala_destino['fila'].append(p['id'])
                        p.update({'status': 'em_fila', 'local_atual': f"fila de {destino}"})
                        log_eventos_minuto.append(f"⏳ {p['id']} entrou na fila de {destino}.")

        # ETAPA D: FINALIZAR PACIENTES
        pacientes_ainda_ativos = []
        for p in pacientes_ativos:
            if len(p['exames_concluidos']) == len(p['exames_necessarios']):
                p['finalizacao'] = minuto_atual
                log_eventos_minuto.append(f"🏁 {p['id']} concluiu sua jornada em {p['finalizacao'] - p['chegada']} minutos.")
                pacientes_finalizados.append(p)
            else:
                pacientes_ainda_ativos.append(p)
        pacientes_ativos = pacientes_ainda_ativos
        
        # Armazena uma cópia profunda do estado atual
        historico_completo.append({
            'minuto': minuto_atual,
            'clinica': copy.deepcopy(clinica),
            'pacientes_ativos': copy.deepcopy(pacientes_ativos),
            'pacientes_finalizados': copy.deepcopy(pacientes_finalizados),
            'log': log_eventos_minuto
        })

    return historico_completo


# --- 3. INTERFACE GRÁFICA (UI) COM STREAMLIT ---

st.title("🏥 Dashboard de Simulação - Otimização de Fluxo SESI")
st.markdown("Use os controles na barra lateral para configurar e rodar uma simulação do fluxo de pacientes.")

# --- BARRA LATERAL DE CONTROLES ---
st.sidebar.header("⚙️ Controles da Simulação")
num_pacientes = st.sidebar.slider("Número de Pacientes", 1, 50, 10)
intervalo_chegada = st.sidebar.slider("Intervalo Médio de Chegada (min)", 1, 10, 4)
max_exames = st.sidebar.slider("Máx. de exames por paciente", 2, 6, 3)
duracao_total = st.sidebar.slider("Duração da Simulação (min)", 60, 480, 240)

if st.sidebar.button("🚀 Rodar Nova Simulação"):
    cenario = gerar_cenario_aleatorio(num_pacientes, intervalo_chegada, max_exames)
    st.session_state['historico'] = executar_simulacao(cenario, duracao_total)
    st.session_state['cenario'] = cenario

# --- ÁREA DE VISUALIZAÇÃO PRINCIPAL ---
if 'historico' in st.session_state:
    historico = st.session_state['historico']
    
    minuto_selecionado = st.slider("Selecione o minuto para visualizar:", 0, len(historico)-1, 0)
    
    estado_atual = historico[minuto_selecionado]
    clinica_atual = estado_atual['clinica']
    
    st.markdown(f"### 🕒 Visualização do Minuto: **{minuto_selecionado}**")
    
    # --- DASHBOARD DA CLÍNICA ---
    st.markdown("#### Status das Salas de Exame")
    cols = st.columns(5)
    col_idx = 0
    for nome_sala, sala in clinica_atual.items():
        with cols[col_idx]:
            if sala['status'] == 'livre':
                st.success(f"✅ {nome_sala}")
                st.metric("Status", "Livre")
            else:
                st.warning(f"🟧 {nome_sala}")
                st.metric(f"Atendendo: {sala['paciente_em_atendimento']}", f"{sala['tempo_restante_atendimento']} min restantes")
                fila_str = ", ".join(sala['fila']) if sala['fila'] else "Ninguém"
                st.caption(f"Fila: {fila_str}")
        col_idx = (col_idx + 1) % 5

    # --- TABELAS DE PACIENTES E LOG ---
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.markdown("#### Situação dos Pacientes")
        pacientes_agora = estado_atual['pacientes_ativos'] + estado_atual['pacientes_finalizados']
        if pacientes_agora:
            df_pacientes = pd.DataFrame(pacientes_agora)
            df_pacientes['jornada'] = df_pacientes.apply(lambda row: f"{len(row['exames_concluidos'])}/{len(row['exames_necessarios'])}", axis=1)
            df_display = df_pacientes[['id', 'status', 'local_atual', 'jornada']].rename(columns={
                'id': 'Paciente', 'status': 'Status', 'local_atual': 'Localização', 'jornada': 'Exames Concluídos'
            })
            st.dataframe(df_display, use_container_width=True)
        else:
            st.info("Nenhum paciente na clínica neste minuto.")

    with col2:
        st.markdown("#### Log de Eventos do Minuto")
        if estado_atual['log']:
            log_formatado = "\n".join(estado_atual['log'])
            st.text_area("Eventos:", log_formatado, height=200)
        else:
            st.info("Nenhum evento neste minuto.")
            
    # --- RELATÓRIO FINAL ---
    with st.expander("Ver Relatório Final da Simulação"):
        finalizados = historico[-1]['pacientes_finalizados']
        if finalizados:
            df_final = pd.DataFrame(finalizados)
            df_final['tempo_total'] = df_final['finalizacao'] - df_final['chegada']
            st.dataframe(df_final[['id', 'chegada', 'finalizacao', 'tempo_total']].rename(columns={
                'id':'Paciente', 'chegada':'Min. Chegada', 'finalizacao':'Min. Saída', 'tempo_total':'Tempo Total (min)'
            }))
        else:
            st.warning("Nenhum paciente completou a jornada ao final da simulação.")

else:
    st.info("⬅️ Configure sua simulação na barra lateral e clique em 'Rodar Nova Simulação' para começar.")