import os
import time
import urllib.request
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from movimentos import calcular_angulo

MODELOS_DISPONIVEIS = {
    "LITE": (
        "pose_landmarker_lite.task",
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task",
    ),
    "FULL": (
        "pose_landmarker_full.task",
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task",
    ),
    "HEAVY": (
        "pose_landmarker_heavy.task",
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/latest/pose_landmarker_heavy.task",
    ),
}

CONEXOES_POSE = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),  # Tronco superior e braços
    (11, 23), (12, 24), (23, 24),                      # Quadril
    (23, 25), (25, 27), (24, 26), (26, 28)             # Pernas
]


class DetectorPose:
    def __init__(self, modelo_inicial="FULL"):
        self.landmarker = None
        self.modelo_atual = None
        self._ultimo_ts_ms = 0
        # Pré-processamento clássico de PDI: CLAHE para correção de iluminação
        self.clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        self.trocar_modelo(modelo_inicial)

    def trocar_modelo(self, nome_modelo):
        """Alterna dinamicamente entre LITE, FULL e HEAVY, baixando se necessário."""
        nome_modelo = nome_modelo.upper()
        if nome_modelo not in MODELOS_DISPONIVEIS:
            return False, f"Modelo '{nome_modelo}' inválido."

        caminho, url = MODELOS_DISPONIVEIS[nome_modelo]
        if not os.path.exists(caminho):
            try:
                print(f"Baixando modelo {nome_modelo} ({caminho})...")
                urllib.request.urlretrieve(url, caminho)
                print(f"Download do modelo {nome_modelo} concluído.")
            except Exception as e:
                return False, f"Erro ao baixar {nome_modelo}: {e}"

        if self.modelo_atual == nome_modelo and self.landmarker is not None:
            return True, f"Modelo {nome_modelo} já está ativo."

        if self.landmarker is not None:
            self.landmarker.close()

        base_options = python.BaseOptions(model_asset_path=caminho)
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.landmarker = vision.PoseLandmarker.create_from_options(options)
        self.modelo_atual = nome_modelo
        return True, f"Modelo alterado para {nome_modelo}"

    def aplicar_clahe(self, frame_bgr):
        """Equalização adaptativa de histograma apenas no canal L (espaço LAB)."""
        lab = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2LAB)
        l_canal, a_canal, b_canal = cv2.split(lab)
        l_eq = self.clahe.apply(l_canal)
        lab_eq = cv2.merge((l_eq, a_canal, b_canal))
        return cv2.cvtColor(lab_eq, cv2.COLOR_LAB2BGR)

    def processar_frame(self, frame_bgr):
        inicio = time.perf_counter()

        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)

        ts_ms = int(time.perf_counter() * 1000)
        if ts_ms <= self._ultimo_ts_ms:
            ts_ms = self._ultimo_ts_ms + 1
        self._ultimo_ts_ms = ts_ms

        resultado = self.landmarker.detect_for_video(mp_image, ts_ms)
        latencia_ms = (time.perf_counter() - inicio) * 1000.0

        landmarks = resultado.pose_landmarks[0] if resultado.pose_landmarks else None
        return landmarks, latencia_ms

    def desenhar_esqueleto_espelhado(self, frame_espelhado, landmarks):
        if not landmarks:
            return frame_espelhado

        h, w, _ = frame_espelhado.shape

        for i, j in CONEXOES_POSE:
            lm_a, lm_b = landmarks[i], landmarks[j]
            if lm_a.visibility > 0.5 and lm_b.visibility > 0.5:
                pt_a = (int((1.0 - lm_a.x) * w), int(lm_a.y * h))
                pt_b = (int((1.0 - lm_b.x) * w), int(lm_b.y * h))
                cv2.line(frame_espelhado, pt_a, pt_b, (0, 255, 180), 3)

        for idx in [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]:
            lm = landmarks[idx]
            if lm.visibility > 0.5:
                cx, cy = int((1.0 - lm.x) * w), int(lm.y * h)
                cv2.circle(frame_espelhado, (cx, cy), 6, (255, 80, 0), -1)

        return frame_espelhado

    def desenhar_telemetria_espelhada(self, frame_espelhado, landmarks):
        """Modo Raio-X: exibe ângulos articulares, inclinação e visibilidade em tempo real."""
        if not landmarks:
            return frame_espelhado

        h, w, _ = frame_espelhado.shape
        oe, od = landmarks[11], landmarks[12]
        ce, cd = landmarks[13], landmarks[14]
        pe, pd = landmarks[15], landmarks[16]

        ang_dir = calcular_angulo(od, cd, pd)
        ang_esq = calcular_angulo(oe, ce, pe)

        # Inclinação dos ombros em graus em relação à horizontal
        inclinacao_graus = float(np.degrees(np.arctan2(od.y - oe.y, abs(oe.x - od.x) + 1e-6)))
        visibilidade_media = float(np.mean([landmarks[i].visibility for i in [0, 11, 12, 13, 14, 15, 16]]))

        def desenhar_tag(texto, x, y, cor=(56, 189, 248)):
            cv2.rectangle(frame_espelhado, (x - 4, y - 16), (x + 76, y + 6), (15, 23, 42), -1)
            cv2.putText(frame_espelhado, texto, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, cor, 1, cv2.LINE_AA)

        # Etiquetas nos cotovelos
        if cd.visibility > 0.5:
            desenhar_tag(f"D:{ang_dir:.0f}o", int((1.0 - cd.x) * w) + 10, int(cd.y * h))
        if ce.visibility > 0.5:
            desenhar_tag(f"E:{ang_esq:.0f}o", int((1.0 - ce.x) * w) + 10, int(ce.y * h))

        # Painel HUD no canto inferior esquerdo da webcam
        overlay = frame_espelhado.copy()
        cv2.rectangle(overlay, (12, h - 92), (310, h - 12), (15, 23, 42), -1)
        cv2.addWeighted(overlay, 0.78, frame_espelhado, 0.22, 0, frame_espelhado)

        cv2.putText(frame_espelhado, "MODO RAIO-X (TELEMETRIA)", (22, h - 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (56, 189, 248), 1, cv2.LINE_AA)
        cv2.putText(frame_espelhado, f"Cotovelos -> D: {ang_dir:.1f}o | E: {ang_esq:.1f}o", (22, h - 48),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.46, (240, 244, 248), 1, cv2.LINE_AA)
        cv2.putText(frame_espelhado, f"Inclinacao: {inclinacao_graus:+.1f}o | Visib: {visibilidade_media*100:.0f}%",
                    (22, h - 24), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (16, 185, 129), 1, cv2.LINE_AA)

        return frame_espelhado

    def fechar(self):
        if self.landmarker is not None:
            self.landmarker.close()