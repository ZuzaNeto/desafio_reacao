import json
from pathlib import Path
from datetime import datetime

ARQUIVO_RANKING = Path("ranking.json")


def carregar_ranking():
    if not ARQUIVO_RANKING.exists():
        return []
    with open(ARQUIVO_RANKING, "r", encoding="utf-8") as f:
        return json.load(f)


def salvar_resultado(nome, tempos_reacao, total_rodadas, acertos_totais=None):
    ranking = carregar_ranking()
    acertos = acertos_totais if acertos_totais is not None else len(tempos_reacao)
    media = sum(tempos_reacao) / len(tempos_reacao) if tempos_reacao else 99.9
    melhor = min(tempos_reacao) if tempos_reacao else 99.9

    registro = {
        "nome": nome.strip() or "Anônimo",
        "media_s": round(media, 3),
        "melhor_s": round(melhor, 3),
        "acertos": acertos,
        "total_rodadas": total_rodadas,
        "taxa_acerto_pct": round((acertos / total_rodadas) * 100, 1),
        "tempos": [round(t, 3) for t in tempos_reacao],
        "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    ranking.append(registro)
    ranking.sort(key=lambda r: (-r["acertos"], r["media_s"]))

    with open(ARQUIVO_RANKING, "w", encoding="utf-8") as f:
        json.dump(ranking, f, ensure_ascii=False, indent=2)

    return registro, ranking