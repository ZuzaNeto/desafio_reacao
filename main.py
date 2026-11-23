import json
import os
import random
import time
import cv2
import pygame

from detector import DetectorPose
from movimentos import COMANDOS_DISPONIVEIS, FiltroEstabilidade, verificar_movimento
from ranking import carregar_ranking, salvar_resultado
from sons import GerenciadorSons

# Dimensões da janela
LARGURA_JANELA, ALTURA_JANELA = 1240, 730
LARGURA_CAM, ALTURA_CAM = 760, 560

# Paleta Dark Slate
COR_FUNDO = (15, 23, 42)
COR_CARD = (30, 41, 59)
COR_CARD_CLARO = (51, 65, 85)
COR_TEXTO = (248, 250, 252)
COR_SUBTEXTO = (148, 163, 184)
COR_PRIMARIA = (56, 189, 248)
COR_SUCESSO = (16, 185, 129)
COR_ALERTA = (245, 158, 11)
COR_ERRO = (239, 68, 68)
COR_DESTAQUE = (168, 85, 247)

MODOS = {
    "NORMAL": {"rodadas": 5, "limite": 5.0, "label": "Normal (5 rodadas | 5s)"},
    "TURBO": {"rodadas": 8, "limite": 3.0, "label": "Turbo (8 rodadas | 3s)"},
}

DURACAO_PEGADINHA = 2.0
CHANCE_PEGADINHA = 0.25


def classificar_reflexo(tempo_s):
    if tempo_s < 0.8:
        return "RELÂMPAGO!"
    if tempo_s < 1.3:
        return "MUITO RÁPIDO!"
    if tempo_s < 2.0:
        return "BOM REFLEXO!"
    return "CONCLUÍDO!"


def salvar_metricas_acumuladas(modelo_atual, metricas_por_modelo, stats_poses_sessao):
    """Salva e acumula métricas de FPS/Latência por modelo e taxa de acerto por pose."""
    caminho = "metricas_execucao.json"
    dados_antigos = {}
    if os.path.exists(caminho):
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                dados_antigos = json.load(f)
        except Exception:
            dados_antigos = {}

    por_modelo_final = dados_antigos.get("por_modelo", {})
    for modelo, valores in metricas_por_modelo.items():
        if valores["fps"]:
            por_modelo_final[modelo] = {
                "fps": valores["fps"][-300:],
                "latencia_ms": valores["latencia_ms"][-300:],
            }

    stats_final = dados_antigos.get("estatisticas_poses", {})
    for pose, cont in stats_poses_sessao.items():
        if pose not in stats_final:
            stats_final[pose] = {"acertos": 0, "tentativas": 0}
        stats_final[pose]["acertos"] += cont["acertos"]
        stats_final[pose]["tentativas"] += cont["tentativas"]

    dados = {
        "modelo_ultimo": modelo_atual,
        "fps": metricas_por_modelo[modelo_atual]["fps"][-300:],
        "latencia_ms": metricas_por_modelo[modelo_atual]["latencia_ms"][-300:],
        "por_modelo": por_modelo_final,
        "estatisticas_poses": stats_final,
    }
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def salvar_foto_podio(frame_bgr, nome, media_s, acertos, total_rodadas, modelo):
    os.makedirs("fotos_podio", exist_ok=True)
    foto = frame_bgr.copy()
    h, w, _ = foto.shape

    overlay = foto.copy()
    cv2.rectangle(overlay, (0, h - 90), (w, h), (15, 23, 42), -1)
    cv2.addWeighted(overlay, 0.78, foto, 0.22, 0, foto)

    texto_1 = f"{nome} | Media: {media_s:.3f}s | Acertos: {acertos}/{total_rodadas}"
    texto_2 = f"Desafio de Reacao Corporal (PDI) - Modelo: {modelo}"
    cv2.putText(foto, texto_1, (20, h - 52), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (16, 185, 129), 2, cv2.LINE_AA)
    cv2.putText(foto, texto_2, (20, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 210, 225), 1, cv2.LINE_AA)

    nome_limpo = "".join(c for c in nome if c.isalnum() or c in ("_", "-")) or "jogador"
    caminho = os.path.join("fotos_podio", f"podio_{nome_limpo}_{int(time.time())}.png")
    cv2.imwrite(caminho, foto)
    return caminho


def desenhar_icone_pose(tela, codigo, cx, cy, cor=COR_PRIMARIA, proibido=False):
    cabeca = (cx, cy - 36)
    ombro_e, ombro_d = (cx + 16, cy - 18), (cx - 16, cy - 18)
    quadril = (cx, cy + 16)
    mao_d, mao_e = (cx - 24, cy + 18), (cx + 24, cy + 18)
    cotovelo_d, cotovelo_e = (cx - 22, cy), (cx + 22, cy)

    if codigo == "BRACO_DIR_CIMA":
        cotovelo_d, mao_d = (cx - 22, cy - 36), (cx - 20, cy - 58)
    elif codigo == "BRACO_ESQ_CIMA":
        cotovelo_e, mao_e = (cx + 22, cy - 36), (cx + 20, cy - 58)
    elif codigo == "AMBOS_CIMA":
        cotovelo_d, mao_d = (cx - 22, cy - 36), (cx - 20, cy - 58)
        cotovelo_e, mao_e = (cx + 22, cy - 36), (cx + 20, cy - 58)
    elif codigo == "BRACOS_EM_T":
        cotovelo_d, mao_d = (cx - 34, cy - 18), (cx - 52, cy - 18)
        cotovelo_e, mao_e = (cx + 34, cy - 18), (cx + 52, cy - 18)
    elif codigo == "MAOS_CRUZADAS":
        cotovelo_d, mao_d = (cx - 24, cy), (cx + 12, cy - 10)
        cotovelo_e, mao_e = (cx + 24, cy), (cx - 12, cy - 10)
    elif codigo == "MAOS_NA_CABECA":
        cotovelo_d, mao_d = (cx - 34, cy - 32), (cx - 12, cy - 38)
        cotovelo_e, mao_e = (cx + 34, cy - 32), (cx + 12, cy - 38)
    elif codigo == "SUPER_HEROI":
        cotovelo_d, mao_d = (cx - 34, cy), (cx - 10, cy + 14)
        cotovelo_e, mao_e = (cx + 34, cy), (cx + 10, cy + 14)
    elif codigo == "INCLINAR_DIR":
        cabeca = (cx - 24, cy - 28)
        ombro_d, ombro_e = (cx - 26, cy - 4), (cx + 2, cy - 20)
        cotovelo_d, mao_d = (cx - 34, cy + 16), (cx - 36, cy + 32)
        cotovelo_e, mao_e = (cx + 16, cy - 6), (cx + 20, cy + 14)
    elif codigo == "INCLINAR_ESQ":
        cabeca = (cx + 24, cy - 28)
        ombro_d, ombro_e = (cx - 2, cy - 20), (cx + 26, cy - 4)
        cotovelo_d, mao_d = (cx - 16, cy - 6), (cx - 20, cy + 14)
        cotovelo_e, mao_e = (cx + 34, cy + 16), (cx + 36, cy + 32)
    elif codigo == "ABAIXAR":
        cabeca = (cx, cy - 10)
        ombro_d, ombro_e = (cx - 16, cy + 8), (cx + 16, cy + 8)
        quadril = (cx, cy + 32)
        cotovelo_d, mao_d = (cx - 24, cy + 20), (cx - 18, cy + 32)
        cotovelo_e, mao_e = (cx + 24, cy + 20), (cx + 18, cy + 32)

    pygame.draw.circle(tela, cor, cabeca, 11, 3)
    meio_ombros = ((ombro_d[0] + ombro_e[0]) // 2, (ombro_d[1] + ombro_e[1]) // 2)
    pygame.draw.line(tela, cor, ombro_d, ombro_e, 4)
    pygame.draw.line(tela, cor, meio_ombros, quadril, 4)
    pygame.draw.line(tela, cor, ombro_d, cotovelo_d, 4)
    pygame.draw.line(tela, cor, cotovelo_d, mao_d, 4)
    pygame.draw.line(tela, cor, ombro_e, cotovelo_e, 4)
    pygame.draw.line(tela, cor, cotovelo_e, mao_e, 4)
    pygame.draw.line(tela, cor, quadril, (quadril[0] - 12, quadril[1] + 26), 4)
    pygame.draw.line(tela, cor, quadril, (quadril[0] + 12, quadril[1] + 26), 4)

    if proibido:
        pygame.draw.line(tela, COR_ERRO, (cx - 46, cy - 54), (cx + 46, cy + 44), 6)
        pygame.draw.line(tela, COR_ERRO, (cx + 46, cy - 54), (cx - 46, cy + 44), 6)


def main():
    pygame.init()
    tela = pygame.display.set_mode((LARGURA_JANELA, ALTURA_JANELA))
    pygame.display.set_caption("PDI - Tema 12: Desafio de Reação Corporal")
    clock = pygame.time.Clock()

    fonte_banner = pygame.font.SysFont("segoeui,arial", 30, bold=True)
    fonte_titulo = pygame.font.SysFont("segoeui,arial", 20, bold=True)
    fonte_media = pygame.font.SysFont("segoeui,arial", 18)
    fonte_pequena = pygame.font.SysFont("segoeui,arial", 14)

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, LARGURA_CAM)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, ALTURA_CAM)

    detector = DetectorPose("FULL")
    filtro_estabilidade = FiltroEstabilidade(frames_confirmacao=4)
    sons = GerenciadorSons()

    # Estado do jogo
    estado = "MENU"
    modo_atual = "NORMAL"
    pegadinha_habilitada = True
    modo_raiox = False
    usar_clahe = False
    eh_pegadinha = False

    nome_jogador = ""
    rodada_atual = 0
    comando_atual = None
    ultimo_comando = None
    tempos_reacao = []
    acertos_totais = 0
    sequencia_acertos = 0
    calibracao_neutro = {}
    stats_poses_sessao = {}

    aviso_sistema = ""
    tempo_aviso_sistema = 0.0

    inicio_espera = 0.0
    atraso_aleatorio = 0.0
    inicio_comando = 0.0
    inicio_feedback = 0.0
    texto_feedback = ""
    subtexto_feedback = ""
    cor_feedback = COR_SUCESSO
    ranking = carregar_ranking()

    metricas_por_modelo = {
        "LITE": {"fps": [], "latencia_ms": []},
        "FULL": {"fps": [], "latencia_ms": []},
        "HEAVY": {"fps": [], "latencia_ms": []},
    }
    tempo_frame_anterior = time.perf_counter()

    def registrar_estatistica_pose(chave_pose, acertou):
        if chave_pose not in stats_poses_sessao:
            stats_poses_sessao[chave_pose] = {"acertos": 0, "tentativas": 0}
        stats_poses_sessao[chave_pose]["tentativas"] += 1
        if acertou:
            stats_poses_sessao[chave_pose]["acertos"] += 1

    rodando = True
    while rodando:
        agora = time.perf_counter()
        dt = agora - tempo_frame_anterior
        tempo_frame_anterior = agora
        fps_atual = 1.0 / dt if dt > 0 else 0.0

        cfg_modo = MODOS[modo_atual]
        total_rodadas = cfg_modo["rodadas"]
        tempo_limite = cfg_modo["limite"]

        # 1. Eventos
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                rodando = False
            elif evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_ESCAPE:
                    rodando = False
                elif evento.key in (pygame.K_F1, pygame.K_F2, pygame.K_F3):
                    mapa_tecla = {pygame.K_F1: "LITE", pygame.K_F2: "FULL", pygame.K_F3: "HEAVY"}
                    _, msg = detector.trocar_modelo(mapa_tecla[evento.key])
                    aviso_sistema = msg
                    tempo_aviso_sistema = agora
                elif evento.key == pygame.K_F4:
                    pegadinha_habilitada = not pegadinha_habilitada
                    aviso_sistema = f"Modo Pegadinha: {'ATIVADO' if pegadinha_habilitada else 'DESATIVADO'}"
                    tempo_aviso_sistema = agora
                elif evento.key == pygame.K_F5:
                    modo_raiox = not modo_raiox
                    aviso_sistema = f"Modo Raio-X (Telemetria): {'ATIVADO' if modo_raiox else 'DESATIVADO'}"
                    tempo_aviso_sistema = agora
                elif evento.key == pygame.K_F6:
                    usar_clahe = not usar_clahe
                    aviso_sistema = f"Pré-processamento CLAHE: {'ATIVADO' if usar_clahe else 'DESATIVADO'}"
                    tempo_aviso_sistema = agora
                elif estado == "MENU":
                    if evento.key == pygame.K_TAB:
                        modo_atual = "TURBO" if modo_atual == "NORMAL" else "NORMAL"
                    elif evento.key == pygame.K_RETURN and nome_jogador.strip():
                        estado = "AGUARDAR_NEUTRO"
                        rodada_atual = 1
                        tempos_reacao = []
                        acertos_totais = 0
                        sequencia_acertos = 0
                        stats_poses_sessao = {}
                        ultimo_comando = None
                        inicio_espera = 0.0
                        filtro_estabilidade.resetar()
                    elif evento.key == pygame.K_BACKSPACE:
                        nome_jogador = nome_jogador[:-1]
                    elif len(nome_jogador) < 16 and evento.unicode.isprintable():
                        nome_jogador += evento.unicode
                elif estado == "RESULTADO":
                    if evento.key == pygame.K_RETURN:
                        estado = "MENU"
                        nome_jogador = ""

        # 2. Captura, CLAHE opcional e MediaPipe Pose
        ret, frame = cap.read()
        if not ret:
            continue

        if usar_clahe:
            frame = detector.aplicar_clahe(frame)

        landmarks, latencia_ms = detector.processar_frame(frame)
        m_atual = detector.modelo_atual
        metricas_por_modelo[m_atual]["fps"].append(round(fps_atual, 2))
        metricas_por_modelo[m_atual]["latencia_ms"].append(round(latencia_ms, 2))

        frame_espelhado = cv2.flip(frame, 1)
        frame_espelhado = detector.desenhar_esqueleto_espelhado(frame_espelhado, landmarks)
        if modo_raiox:
            frame_espelhado = detector.desenhar_telemetria_espelhada(frame_espelhado, landmarks)

        # 3. Máquina de estados
        banner_texto = ""
        banner_cor = COR_TEXTO
        cor_borda_cam = COR_CARD_CLARO
        progresso_tempo = 0.0

        if estado == "MENU":
            banner_texto = "Digite seu nome, escolha o modo (TAB) e aperte ENTER"
            banner_cor = COR_PRIMARIA
            cor_borda_cam = COR_PRIMARIA

        elif estado == "AGUARDAR_NEUTRO":
            em_neutro = verificar_movimento(landmarks, "NEUTRO")
            if not em_neutro:
                inicio_espera = 0.0
                banner_texto = f"Rodada {rodada_atual}/{total_rodadas} — Fique reto com os braços abaixados"
                banner_cor = COR_ALERTA
                cor_borda_cam = COR_ALERTA
            else:
                calibracao_neutro = {
                    "nariz_y": landmarks[0].y,
                    "largura_ombros": abs(landmarks[11].x - landmarks[12].x) + 1e-6,
                }
                if inicio_espera == 0.0:
                    inicio_espera = agora
                    atraso_aleatorio = random.uniform(1.4, 3.2)
                banner_texto = "Posição neutra OK! Aguarde o comando..."
                banner_cor = COR_SUCESSO
                cor_borda_cam = COR_SUCESSO

                if agora - inicio_espera >= atraso_aleatorio:
                    opcoes = [c for c in COMANDOS_DISPONIVEIS.keys() if c != ultimo_comando]
                    comando_atual = random.choice(opcoes)
                    ultimo_comando = comando_atual
                    eh_pegadinha = (
                        pegadinha_habilitada
                        and random.random() < CHANCE_PEGADINHA
                        and not (rodada_atual == total_rodadas and len(tempos_reacao) == 0)
                    )
                    inicio_comando = time.perf_counter()
                    filtro_estabilidade.resetar()
                    sons.tocar("pegadinha" if eh_pegadinha else "comando")
                    estado = "COMANDO"

        elif estado == "COMANDO":
            decorrido = agora - inicio_comando

            if eh_pegadinha:
                progresso_tempo = max(0.0, 1.0 - (decorrido / DURACAO_PEGADINHA))
                banner_texto = f"NÃO FAÇA: {COMANDOS_DISPONIVEIS[comando_atual]}"
                banner_cor = COR_ERRO
                cor_borda_cam = COR_ERRO

                saiu_do_neutro = not verificar_movimento(landmarks, "NEUTRO")
                if filtro_estabilidade.atualizar(saiu_do_neutro):
                    registrar_estatistica_pose("PEGADINHA", False)
                    sequencia_acertos = 0
                    texto_feedback = "CAIU NA PEGADINHA!"
                    subtexto_feedback = "Comando em vermelho = fique parado!"
                    cor_feedback = COR_ERRO
                    inicio_feedback = agora
                    sons.tocar("erro")
                    estado = "FEEDBACK"
                elif decorrido >= DURACAO_PEGADINHA:
                    registrar_estatistica_pose("PEGADINHA", True)
                    acertos_totais += 1
                    sequencia_acertos += 1
                    texto_feedback = "ESCAPOU DA PEGADINHA!"
                    subtexto_feedback = f"Ótimo autocontrole! Sequência: {sequencia_acertos}x"
                    cor_feedback = COR_SUCESSO
                    inicio_feedback = agora
                    sons.tocar("acerto")
                    estado = "FEEDBACK"
            else:
                progresso_tempo = max(0.0, 1.0 - (decorrido / tempo_limite))
                banner_texto = f"{COMANDOS_DISPONIVEIS[comando_atual]}"
                banner_cor = COR_ALERTA
                cor_borda_cam = COR_DESTAQUE

                movimento_ok = verificar_movimento(landmarks, comando_atual, calibracao_neutro)
                if filtro_estabilidade.atualizar(movimento_ok):
                    tempo_reacao = time.perf_counter() - inicio_comando
                    registrar_estatistica_pose(comando_atual, True)
                    tempos_reacao.append(tempo_reacao)
                    acertos_totais += 1
                    sequencia_acertos += 1
                    texto_feedback = f"{classificar_reflexo(tempo_reacao)}  {tempo_reacao:.3f}s"
                    subtexto_feedback = f"Sequência atual: {sequencia_acertos}x"
                    cor_feedback = COR_SUCESSO
                    inicio_feedback = agora
                    sons.tocar("acerto")
                    estado = "FEEDBACK"
                elif decorrido >= tempo_limite:
                    registrar_estatistica_pose(comando_atual, False)
                    sequencia_acertos = 0
                    texto_feedback = "TEMPO ESGOTADO!"
                    subtexto_feedback = "Tente reagir mais rápido na próxima."
                    cor_feedback = COR_ERRO
                    inicio_feedback = agora
                    sons.tocar("erro")
                    estado = "FEEDBACK"

        elif estado == "FEEDBACK":
            banner_texto = f"{texto_feedback}   ({subtexto_feedback})"
            banner_cor = cor_feedback
            cor_borda_cam = cor_feedback
            if agora - inicio_feedback >= 1.5:
                if rodada_atual < total_rodadas:
                    rodada_atual += 1
                    inicio_espera = 0.0
                    estado = "AGUARDAR_NEUTRO"
                else:
                    registro, ranking = salvar_resultado(
                        nome_jogador, tempos_reacao, total_rodadas, acertos_totais=acertos_totais
                    )
                    salvar_metricas_acumuladas(m_atual, metricas_por_modelo, stats_poses_sessao)
                    caminho_foto = salvar_foto_podio(
                        frame_espelhado,
                        registro["nome"],
                        registro["media_s"],
                        registro["acertos"],
                        total_rodadas,
                        detector.modelo_atual,
                    )
                    aviso_sistema = f"Foto do pódio salva: {caminho_foto}"
                    tempo_aviso_sistema = agora
                    sons.tocar("fim")
                    estado = "RESULTADO"

        elif estado == "RESULTADO":
            media = sum(tempos_reacao) / len(tempos_reacao) if tempos_reacao else 0.0
            banner_texto = f"Fim! Média: {media:.3f}s ({acertos_totais}/{total_rodadas}) | ENTER p/ voltar"
            banner_cor = COR_SUCESSO
            cor_borda_cam = COR_SUCESSO

        # 4. Renderização
        tela.fill(COR_FUNDO)

        # Banner superior
        pygame.draw.rect(tela, COR_CARD, (20, 16, LARGURA_JANELA - 40, 74), border_radius=14)
        pygame.draw.rect(tela, cor_borda_cam, (20, 16, LARGURA_JANELA - 40, 74), width=2, border_radius=14)
        tela.blit(fonte_banner.render(banner_texto, True, banner_cor), (40, 35))

        # Container da Webcam
        pygame.draw.rect(tela, cor_borda_cam, (16, 106, LARGURA_CAM + 8, ALTURA_CAM + 8), border_radius=12)
        frame_rgb = cv2.cvtColor(frame_espelhado, cv2.COLOR_BGR2RGB)
        frame_redim = cv2.resize(frame_rgb, (LARGURA_CAM, ALTURA_CAM))
        surf_cam = pygame.image.frombuffer(frame_redim.tobytes(), (LARGURA_CAM, ALTURA_CAM), "RGB")
        tela.blit(surf_cam, (20, 110))

        # Aviso temporário sobre a webcam
        if aviso_sistema and (agora - tempo_aviso_sistema) < 3.0:
            pygame.draw.rect(tela, COR_FUNDO, (32, 122, 480, 34), border_radius=8)
            tela.blit(fonte_pequena.render(aviso_sistema, True, COR_PRIMARIA), (44, 130))

        # Barra de tempo regressiva
        pygame.draw.rect(tela, COR_CARD, (20, 682, LARGURA_CAM, 18), border_radius=9)
        if estado == "COMANDO":
            if eh_pegadinha:
                cor_barra = COR_ERRO
            else:
                cor_barra = COR_SUCESSO if progresso_tempo > 0.5 else (COR_ALERTA if progresso_tempo > 0.25 else COR_ERRO)
            pygame.draw.rect(tela, cor_barra, (20, 682, int(LARGURA_CAM * progresso_tempo), 18), border_radius=9)

        # Painel Lateral Direito
        x_p = LARGURA_CAM + 40
        w_p = LARGURA_JANELA - x_p - 20

        # Card 1: Jogador, Modo e Recursos (F4, F5, F6)
        pygame.draw.rect(tela, COR_CARD, (x_p, 108, w_p, 160), border_radius=14)
        tela.blit(fonte_titulo.render("Participante", True, COR_TEXTO), (x_p + 18, 116))
        pygame.draw.rect(tela, COR_FUNDO, (x_p + 18, 144, w_p - 36, 36), border_radius=8)
        cursor = "|" if estado == "MENU" and int(agora * 2) % 2 == 0 else ""
        tela.blit(fonte_media.render(nome_jogador + cursor, True, COR_PRIMARIA), (x_p + 28, 151))
        tela.blit(fonte_pequena.render(f"Modo (TAB): {cfg_modo['label']}", True, COR_SUBTEXTO), (x_p + 18, 188))

        # Status rápido F4 / F5 / F6
        cor_peg = COR_ERRO if pegadinha_habilitada else COR_SUBTEXTO
        cor_rx = COR_PRIMARIA if modo_raiox else COR_SUBTEXTO
        cor_cl = COR_SUCESSO if usar_clahe else COR_SUBTEXTO
        tela.blit(fonte_pequena.render(f"F4 Pegadinha: {'ON' if pegadinha_habilitada else 'OFF'}", True, cor_peg), (x_p + 18, 212))
        tela.blit(fonte_pequena.render(f"F5 Raio-X: {'ON' if modo_raiox else 'OFF'}", True, cor_rx), (x_p + 18, 236))
        tela.blit(fonte_pequena.render(f"F6 CLAHE: {'ON' if usar_clahe else 'OFF'}", True, cor_cl), (x_p + 205, 236))

        # Card 2: Seletor de Modelo MediaPipe + Guia Visual + Estabilidade
        pygame.draw.rect(tela, COR_CARD, (x_p, 278, w_p, 180), border_radius=14)
        tela.blit(fonte_titulo.render("Modelo & Guia Visual", True, COR_TEXTO), (x_p + 18, 286))

        badges = [("F1: LITE", "LITE"), ("F2: FULL", "FULL"), ("F3: HEAVY", "HEAVY")]
        larg_badge = (w_p - 52) // 3
        for i, (rotulo, chave) in enumerate(badges):
            bx = x_p + 18 + i * (larg_badge + 8)
            ativo = detector.modelo_atual == chave
            pygame.draw.rect(tela, COR_PRIMARIA if ativo else COR_FUNDO, (bx, 314, larg_badge, 26), border_radius=6)
            cor_txt_b = COR_FUNDO if ativo else COR_SUBTEXTO
            tela.blit(fonte_pequena.render(rotulo, True, cor_txt_b), (bx + 12, 318))

        if estado == "COMANDO" and comando_atual:
            cor_guia = COR_ERRO if eh_pegadinha else COR_DESTAQUE
            desenhar_icone_pose(tela, comando_atual, x_p + 76, 404, cor_guia, proibido=eh_pegadinha)
        else:
            desenhar_icone_pose(tela, "NEUTRO", x_p + 76, 404, COR_SUBTEXTO, proibido=False)

        lbl_estab = "Movimento indevido:" if (estado == "COMANDO" and eh_pegadinha) else "Confirmação da pose:"
        cor_estab = COR_ERRO if (estado == "COMANDO" and eh_pegadinha) else COR_SUCESSO
        tela.blit(fonte_pequena.render(lbl_estab, True, COR_SUBTEXTO), (x_p + 150, 358))
        pygame.draw.rect(tela, COR_FUNDO, (x_p + 150, 380, w_p - 168, 15), border_radius=7)
        pygame.draw.rect(
            tela, cor_estab, (x_p + 150, 380, int((w_p - 168) * filtro_estabilidade.progresso), 15), border_radius=7
        )
        tela.blit(
            fonte_pequena.render(f"FPS: {fps_atual:.1f}  |  Latência: {latencia_ms:.1f} ms", True, COR_PRIMARIA),
            (x_p + 150, 412),
        )

        # Card 3: Ranking Top 5
        pygame.draw.rect(tela, COR_CARD, (x_p, 468, w_p, 242), border_radius=14)
        tela.blit(fonte_titulo.render("Ranking (Top 5)", True, COR_TEXTO), (x_p + 18, 478))
        for idx, item in enumerate(ranking[:5], start=1):
            y_item = 510 + (idx - 1) * 36
            cor_pos = COR_ALERTA if idx == 1 else COR_TEXTO
            pygame.draw.rect(tela, COR_CARD_CLARO if idx == 1 else COR_FUNDO, (x_p + 16, y_item, w_p - 32, 29), border_radius=6)
            linha = f"#{idx}  {item['nome'][:11]:<11}  {item['media_s']:.2f}s  ({item['acertos']}/{item['total_rodadas']})"
            tela.blit(fonte_pequena.render(linha, True, cor_pos), (x_p + 24, y_item + 5))

        pygame.display.flip()
        clock.tick(60)

    # Salva métricas mesmo se o usuário sair no ESC após alternar entre modelos
    salvar_metricas_acumuladas(detector.modelo_atual, metricas_por_modelo, stats_poses_sessao)
    detector.fechar()
    cap.release()
    pygame.quit()


if __name__ == "__main__":
    main()