#pages/2_visao_do_cliente.py
# -*- coding: utf-8 -*-
import streamlit as st
import datetime

# --- CONFIGURAÇÕES DA PÁGINA ---
st.set_page_config(layout="centered", page_title="Visão do Cliente", page_icon="👤")

# --- CONSTANTES E FUNÇÕES AUXILIARES ---
# É necessário ter as mesmas constantes aqui para os cálculos
DURACAO_EXAMES = {
    'Eletrocardiograma': 8, 'Espirometria': 10, 'Eletroencefalograma': 20,
    'Teste ergométrico': 25, 'TVI': 6, 'Audiometria': 8,
    'Consulta oftalmológica': 15, 'Consulta Ocupacional': 12, 'Raio X': 6,
    'Exame de Sangue': 5
}

def calcular_tempo_espera_para_sala(sala_id, paciente_id, estado_clinica):
    """Calcula a posição na fila e o tempo de espera estimado para um paciente em uma sala específica."""
    sala = estado_clinica[sala_id]
    
    tempo_espera = sala['tempo_restante_atendimento']
    
    # Verifica se o paciente já está na fila
    try:
        posicao_na_fila = sala['fila'].index(paciente_id)
        pessoas_na_frente = posicao_na_fila + 1 # +1 para contar quem está em atendimento
        
        # Soma o tempo dos exames das pessoas que estão na frente na fila
        for i in range(posicao_na_fila):
            tempo_espera += DURACAO_EXAMES[sala_id]
            
    except ValueError: # Paciente não está na fila, então ele seria o último
        pessoas_na_frente = len(sala['fila']) + 1
        for _ in sala['fila']:
            tempo_espera += DURACAO_EXAMES[sala_id]
            
    return pessoas_na_frente, tempo_espera

# --- TÍTULO E VERIFICAÇÃO INICIAL ---
st.title("👤 Visão da Jornada do Funcionário")
st.markdown("Use a barra de tempo abaixo para selecionar um instante e, em seguida, escolha um funcionário para analisar sua jornada.")

# A página do cliente só funciona se uma simulação já foi executada na página principal.
if 'historico' not in st.session_state or not st.session_state['historico']:
    st.warning("Por favor, execute uma simulação na página 'Dashboard de Simulação' primeiro.", icon="⚠️")
    st.stop()

# --- CONTROLES DE SELEÇÃO (TEMPO E CLIENTE) ---
historico = st.session_state['historico']
cenario = st.session_state['cenario']

# <-- NOVO SLIDER ADICIONADO AQUI -->
# Este slider controla qual minuto da simulação será exibido.
minuto_selecionado = st.slider(
    "Selecione o minuto da simulação para analisar:", 
    0, 
    len(historico)-1, 
    len(historico)-1 # O valor padrão é o último minuto
)

# Extrai a lista de todos os pacientes que participaram da simulação
lista_pacientes = [p['id'] for p in cenario]
paciente_selecionado_id = st.selectbox("Selecione o funcionário:", lista_pacientes)

# --- VISUALIZAÇÃO DOS DADOS PARA O MINUTO E CLIENTE SELECIONADOS ---

# <-- MODIFICADO PARA USAR O MINUTO SELECIONADO -->
# Em vez de pegar apenas o último estado, pegamos o estado do minuto que o slider indica.
estado_atual = historico[minuto_selecionado]

if paciente_selecionado_id:
    # Encontrar os dados do paciente selecionado no estado ATUAL da simulação
    paciente_info = None
    for p in estado_atual['pacientes_ativos'] + estado_atual['pacientes_finalizados']:
        if p['id'] == paciente_selecionado_id:
            paciente_info = p
            break
    
    # Se o paciente ainda não chegou na clínica no minuto selecionado
    if not paciente_info:
        st.info(f"{paciente_selecionado_id} ainda não havia chegado à clínica no minuto {minuto_selecionado}.")
        st.stop()

    # --- EXIBIÇÃO DA JORNADA DO PACIENTE ---
    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Exames Concluídos")
        if paciente_info['exames_concluidos']:
            for exame in paciente_info['exames_concluidos']:
                st.markdown(f"✅ {exame}")
        else:
            st.info("Nenhum exame concluído ainda.")
    
    with col2:
        exames_pendentes = [e for e in paciente_info['exames_necessarios'] if e not in paciente_info['exames_concluidos']]
        st.subheader("Exames Pendentes")
        if exames_pendentes:
            for exame in exames_pendentes:
                st.markdown(f"📋 {exame}")
        else:
            st.success("Todos os exames foram concluídos!")
            
    st.divider()

    # --- CÁLCULO E EXIBIÇÃO DO PRÓXIMO PASSO ---
    st.header(f"➡️ Próximo Passo no Minuto {minuto_selecionado}")

    if len(paciente_info['exames_concluidos']) == len(paciente_info['exames_necessarios']):
        st.balloons()
        st.success(f"Parabéns, {paciente_selecionado_id}! Neste minuto, sua jornada de exames já havia sido finalizada.")
    
    elif paciente_info['status'] == 'em_exame':
        st.info(f"Neste instante, você está em atendimento no exame: **{paciente_info['local_atual']}**", icon="🧑‍⚕️")

    else:
        clinica_atual = estado_atual['clinica']
        
        if paciente_info['status'] == 'em_fila':
            proximo_destino = paciente_info['local_atual'].replace("fila de ", "")
        else:
            from app import encontrar_proximo_exame
            proximo_destino = encontrar_proximo_exame(paciente_info, clinica_atual)

        if not proximo_destino:
            st.info("Aguardando a liberação de uma sala compatível...")
        else:
            pessoas_na_frente, tempo_de_espera = calcular_tempo_espera_para_sala(proximo_destino, paciente_selecionado_id, clinica_atual)
            
            # Cálculo do horário estimado
            hora_inicio_clinica = datetime.datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
            hora_atual_simulacao = hora_inicio_clinica + datetime.timedelta(minutes=minuto_selecionado)
            horario_estimado_atendimento = hora_atual_simulacao + datetime.timedelta(minutes=tempo_de_espera)
            
            st.info(f"O sistema direciona você para: **{proximo_destino}**")
            
            kpi1, kpi2, kpi3 = st.columns(3)
            with kpi1:
                st.metric(label="🚶 Pessoas na sua frente", value=f"{pessoas_na_frente}")
            with kpi2:
                st.metric(label="⏳ Tempo de Espera Estimado", value=f"~{tempo_de_espera} min")
            with kpi3:
                st.metric(label="🕒 Horário Estimado", value=horario_estimado_atendimento.strftime('%H:%M'))