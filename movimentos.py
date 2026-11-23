import numpy as np

# Índices dos landmarks do MediaPipe Pose
NARIZ = 0
ORELHA_ESQ, ORELHA_DIR = 7, 8
OMBRO_ESQ, OMBRO_DIR = 11, 12
COTOVELO_ESQ, COTOVELO_DIR = 13, 14
PUNHO_ESQ, PUNHO_DIR = 15, 16
QUADRIL_ESQ, QUADRIL_DIR = 23, 24

COMANDOS_DISPONIVEIS = {
    "BRACO_DIR_CIMA": "LEVANTE O BRAÇO DIREITO!",
    "BRACO_ESQ_CIMA": "LEVANTE O BRAÇO ESQUERDO!",
    "AMBOS_CIMA": "LEVANTE OS DOIS BRAÇOS!",
    "BRACOS_EM_T": "ABRA OS BRAÇOS EM 'T'!",
    "MAOS_CRUZADAS": "CRUZE OS BRAÇOS NO PEITO!",
    "MAOS_NA_CABECA": "MÃOS NA CABEÇA!",
    "SUPER_HEROI": "MÃOS NA CINTURA (HERÓI)!",
    "INCLINAR_DIR": "INCLINE PARA A DIREITA!",
    "INCLINAR_ESQ": "INCLINE PARA A ESQUERDA!",
    "ABAIXAR": "ABAIXE-SE RÁPIDO!",
}


def calcular_angulo(a, b, c):
    """Calcula o ângulo (em graus) no vértice b formado pelos pontos a-b-c."""
    va = np.array([a.x - b.x, a.y - b.y])
    vc = np.array([c.x - b.x, c.y - b.y])

    norma = np.linalg.norm(va) * np.linalg.norm(vc)
    if norma == 0:
        return 0.0

    cosseno = np.clip(np.dot(va, vc) / norma, -1.0, 1.0)
    return float(np.degrees(np.arccos(cosseno)))


def distancia_2d(a, b):
    return float(np.hypot(a.x - b.x, a.y - b.y))


def pontos_visiveis(landmarks, indices, limiar=0.45):
    return all(landmarks[i].visibility >= limiar for i in indices)


def verificar_movimento(landmarks, codigo_comando, calibracao=None):
    """Retorna True se os landmarks satisfazem a geometria do comando."""
    if not landmarks:
        return False

    obrigatorios = [NARIZ, OMBRO_ESQ, OMBRO_DIR, COTOVELO_ESQ, COTOVELO_DIR, PUNHO_ESQ, PUNHO_DIR]
    if not pontos_visiveis(landmarks, obrigatorios):
        return False

    nariz = landmarks[NARIZ]
    ore_e, ore_d = landmarks[ORELHA_ESQ], landmarks[ORELHA_DIR]
    oe, od = landmarks[OMBRO_ESQ], landmarks[OMBRO_DIR]
    ce, cd = landmarks[COTOVELO_ESQ], landmarks[COTOVELO_DIR]
    pe, pd = landmarks[PUNHO_ESQ], landmarks[PUNHO_DIR]
    qe, qd = landmarks[QUADRIL_ESQ], landmarks[QUADRIL_DIR]

    # Escala normalizada pela largura dos ombros (invariante à distância da webcam)
    largura_ombros = abs(oe.x - od.x) + 1e-6

    ang_dir = calcular_angulo(od, cd, pd)
    ang_esq = calcular_angulo(oe, ce, pe)

    dir_levantado = pd.y < nariz.y - 0.15 * largura_ombros and ang_dir > 130
    esq_levantado = pe.y < nariz.y - 0.15 * largura_ombros and ang_esq > 130

    if codigo_comando == "NEUTRO":
        # Punhos abaixo dos ombros e braços relativamente relaxados (tronco ereto)
        tronco_reto = abs(od.y - oe.y) < 0.20 * largura_ombros
        bracos_baixos = (
            pd.y > od.y + 0.15 * largura_ombros
            and pe.y > oe.y + 0.15 * largura_ombros
            and ang_dir > 125
            and ang_esq > 125
        )
        return tronco_reto and bracos_baixos

    if codigo_comando == "BRACO_DIR_CIMA":
        return dir_levantado and pe.y > oe.y

    if codigo_comando == "BRACO_ESQ_CIMA":
        return esq_levantado and pd.y > od.y

    if codigo_comando == "AMBOS_CIMA":
        return dir_levantado and esq_levantado

    if codigo_comando == "BRACOS_EM_T":
        altura_ok = (
            abs(pd.y - od.y) < 0.45 * largura_ombros
            and abs(pe.y - oe.y) < 0.45 * largura_ombros
        )
        abertura_ok = abs(pe.x - pd.x) > 2.2 * largura_ombros
        return ang_dir > 145 and ang_esq > 145 and altura_ok and abertura_ok

    if codigo_comando == "MAOS_CRUZADAS":
        punhos_no_tronco = (
            od.y - 0.2 * largura_ombros < pd.y < od.y + 0.9 * largura_ombros
            and oe.y - 0.2 * largura_ombros < pe.y < oe.y + 0.9 * largura_ombros
        )
        cruzados = pd.x > oe.x - 0.4 * largura_ombros and pe.x < od.x + 0.4 * largura_ombros
        return ang_dir < 115 and ang_esq < 115 and punhos_no_tronco and cruzados

    if codigo_comando == "MAOS_NA_CABECA":
        # Punhos próximos às orelhas/cabeça com cotovelos dobrados
        dist_dir = distancia_2d(pd, ore_d) < 0.65 * largura_ombros
        dist_esq = distancia_2d(pe, ore_e) < 0.65 * largura_ombros
        acima_ombros = pd.y < od.y and pe.y < oe.y
        return dist_dir and dist_esq and acima_ombros and ang_dir < 115 and ang_esq < 115

    if codigo_comando == "SUPER_HEROI":
        # Mãos na cintura/quadril com cotovelos dobrados para fora
        if not pontos_visiveis(landmarks, [QUADRIL_ESQ, QUADRIL_DIR], limiar=0.35):
            return False
        dist_dir = distancia_2d(pd, qd) < 0.65 * largura_ombros
        dist_esq = distancia_2d(pe, qe) < 0.65 * largura_ombros
        cotovelos_abertos = abs(ce.x - cd.x) > 1.35 * largura_ombros
        return dist_dir and dist_esq and cotovelos_abertos and 60 < ang_dir < 140 and 60 < ang_esq < 140

    if codigo_comando == "INCLINAR_DIR":
        # No frame sem espelho, inclinar para a direita real faz o ombro direito descer (od.y > oe.y)
        return (od.y - oe.y) > 0.25 * largura_ombros

    if codigo_comando == "INCLINAR_ESQ":
        # Inclinar para a esquerda real faz o ombro esquerdo descer (oe.y > od.y)
        return (oe.y - od.y) > 0.25 * largura_ombros

    if codigo_comando == "ABAIXAR":
        if not calibracao or "nariz_y" not in calibracao:
            return False
        deslocamento_minimo = 0.45 * calibracao["largura_ombros"]
        return nariz.y > calibracao["nariz_y"] + deslocamento_minimo

    return False


class FiltroEstabilidade:
    """Exige N frames consecutivos válidos antes de confirmar o movimento."""
    def __init__(self, frames_confirmacao=4):
        self.frames_confirmacao = frames_confirmacao
        self.contador = 0

    def resetar(self):
        self.contador = 0

    @property
    def progresso(self):
        return min(1.0, self.contador / self.frames_confirmacao)

    def atualizar(self, condicao_atendida):
        if condicao_atendida:
            self.contador += 1
        else:
            self.contador = 0
        return self.contador >= self.frames_confirmacao