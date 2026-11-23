import json
import numpy as np
import matplotlib.pyplot as plt

with open("metricas_execucao.json", "r", encoding="utf-8") as f:
    metricas = json.load(f)

try:
    with open("ranking.json", "r", encoding="utf-8") as f:
        ranking = json.load(f)
except FileNotFoundError:
    ranking = []

por_modelo = metricas.get("por_modelo", {})
stats_poses = metricas.get("estatisticas_poses", {})

# Ordem fixa dos modelos disponíveis no JSON
modelos = [m for m in ["LITE", "FULL", "HEAVY"] if m in por_modelo and por_modelo[m]["fps"]]
fps_medias = [np.mean(por_modelo[m]["fps"]) for m in modelos]
fps_stds = [np.std(por_modelo[m]["fps"]) for m in modelos]
lat_medias = [np.mean(por_modelo[m]["latencia_ms"]) for m in modelos]
lat_stds = [np.std(por_modelo[m]["latencia_ms"]) for m in modelos]

# Resumo no terminal (pronto para colar nos slides)
print("=== RESUMO DE DESEMPENHO POR MODELO ===")
for m, fm, fs, lm, ls in zip(modelos, fps_medias, fps_stds, lat_medias, lat_stds):
    print(f"{m:<6} | FPS: {fm:5.1f} (±{fs:4.1f}) | Latência: {lm:5.1f} ms (±{ls:4.1f})")

fig, axes = plt.subplots(2, 2, figsize=(14, 9))
fig.suptitle("Avaliação Técnica — Desafio de Reação Corporal (PDI)", fontsize=15, fontweight="bold")
cores_modelos = ["#10B981", "#38BDF8", "#A855F7"][: len(modelos)]

# 1. Comparativo de FPS (Lite vs. Full vs. Heavy)
ax = axes[0, 0]
if modelos:
    barras = ax.bar(modelos, fps_medias, yerr=fps_stds, capsize=5, color=cores_modelos)
    for b, val in zip(barras, fps_medias):
        ax.text(b.get_x() + b.get_width() / 2, val + 1.0, f"{val:.1f}", ha="center", fontweight="bold")
ax.set_title("FPS Médio por Modelo (maior é melhor)")
ax.set_ylabel("Frames por segundo (FPS)")
ax.grid(axis="y", linestyle="--", alpha=0.4)

# 2. Comparativo de Latência (Lite vs. Full vs. Heavy)
ax = axes[0, 1]
if modelos:
    barras = ax.bar(modelos, lat_medias, yerr=lat_stds, capsize=5, color=cores_modelos)
    for b, val in zip(barras, lat_medias):
        ax.text(b.get_x() + b.get_width() / 2, val + 1.0, f"{val:.1f} ms", ha="center", fontweight="bold")
ax.set_title("Latência Média de Inferência (menor é melhor)")
ax.set_ylabel("Milissegundos (ms)")
ax.grid(axis="y", linestyle="--", alpha=0.4)

# 3. Taxa de Acerto por Pose (%)
ax = axes[1, 0]
if stats_poses:
    nomes_poses = list(stats_poses.keys())
    taxas = [
        (stats_poses[p]["acertos"] / stats_poses[p]["tentativas"]) * 100
        if stats_poses[p]["tentativas"] > 0 else 0
        for p in nomes_poses
    ]
    barras = ax.barh(nomes_poses, taxas, color="#F59E0B")
    ax.set_xlim(0, 115)
    for b, val, p in zip(barras, taxas, nomes_poses):
        ac = stats_poses[p]["acertos"]
        tt = stats_poses[p]["tentativas"]
        ax.text(val + 1.5, b.get_y() + b.get_height() / 2, f"{val:.0f}% ({ac}/{tt})", va="center", fontsize=9)
ax.set_title("Taxa de Acerto por Pose")
ax.set_xlabel("Acerto (%)")
ax.grid(axis="x", linestyle="--", alpha=0.4)

# 4. Ranking de Tempo Médio de Reação
ax = axes[1, 1]
if ranking:
    top = ranking[:6]
    nomes = [r["nome"] for r in top]
    medias = [r["media_s"] for r in top]
    barras = ax.bar(nomes, medias, color="#38BDF8")
    for b, val in zip(barras, medias):
        ax.text(b.get_x() + b.get_width() / 2, val + 0.03, f"{val:.2f}s", ha="center", fontsize=9)
    ax.tick_params(axis="x", rotation=20)
ax.set_title("Tempo Médio de Reação — Ranking")
ax.set_ylabel("Segundos (menor é melhor)")
ax.grid(axis="y", linestyle="--", alpha=0.4)

plt.tight_layout(rect=[0, 0, 1, 0.96])
plt.savefig("relatorio_avaliacao.png", dpi=150)
plt.show()