import numpy as np
import pygame


class GerenciadorSons:
    def __init__(self):
        self.ativo = False
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            self.ativo = True
            self.som_comando = self._gerar_tom(660, 0.12, volume=0.25)
            self.som_pegadinha = self._gerar_acorde([311.13, 277.18], 0.20, volume=0.28)
            self.som_acerto = self._gerar_acorde([523.25, 659.25, 783.99], 0.22, volume=0.25)
            self.som_erro = self._gerar_tom(190, 0.30, volume=0.28)
            self.som_fim = self._gerar_acorde([523.25, 659.25, 783.99, 1046.5], 0.40, volume=0.25)
        except Exception:
            self.ativo = False

    def _gerar_tom(self, freq, duracao_s, volume=0.25, sr=44100):
        t = np.linspace(0, duracao_s, int(sr * duracao_s), False)
        onda = np.sin(2 * np.pi * freq * t)
        envelope = np.linspace(1.0, 0.0, len(t))
        audio = (onda * envelope * volume * 32767).astype(np.int16)
        return pygame.sndarray.make_sound(np.column_stack((audio, audio)))

    def _gerar_acorde(self, frequencias, duracao_s, volume=0.25, sr=44100):
        t = np.linspace(0, duracao_s, int(sr * duracao_s), False)
        onda = sum(np.sin(2 * np.pi * f * t) for f in frequencias) / len(frequencias)
        envelope = np.linspace(1.0, 0.0, len(t))
        audio = (onda * envelope * volume * 32767).astype(np.int16)
        return pygame.sndarray.make_sound(np.column_stack((audio, audio)))

    def tocar(self, nome):
        if not self.ativo:
            return
        mapa = {
            "comando": self.som_comando,
            "pegadinha": self.som_pegadinha,
            "acerto": self.som_acerto,
            "erro": self.som_erro,
            "fim": self.som_fim,
        }
        som = mapa.get(nome)
        if som:
            som.play()