"""
Estimador de duração de um job.

Oracle não devolve "estou em 70%" durante uma query, então a gente
estima o progresso pelo **tempo decorrido** relativo à **mediana histórica**
daquele mesmo relatório. Isso é honesto: se o relatório X geralmente leva
40s, com 20s decorridos a barra marca 50%.

Fonte de dados: logs_acesso, filtrando por relatorio_id, acao de extração e
sucesso=True. Pega os últimos 10 e tira a mediana.

Se não há histórico: retorna None — o front mostra barra indeterminada.
"""
import math
import statistics
from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.log_acesso import LogAcesso

# Quantos logs recentes consultar pra mediana. 10 equilibra "resposta a
# melhorias" (não demora tanto a recalibrar) com "robustez a outliers".
JANELA_HISTORICO = 10

# Se não há histórico, nenhum ETA é devolvido (None). Front → barra indeterminada.


def calcular_mediana_duracao_s(
    db: Session, relatorio_id: str, acao: str = "extrair_relatorio"
) -> Optional[int]:
    """
    Mediana (em segundos) das últimas N durações de sucesso desse relatório.

    Retorna None quando não há histórico suficiente (0 execuções bem-sucedidas).
    """
    rows = (
        db.query(LogAcesso.duracao_ms)
        .filter(
            LogAcesso.relatorio_id == relatorio_id,
            LogAcesso.acao == acao,
            LogAcesso.sucesso.is_(True),
            LogAcesso.duracao_ms.isnot(None),
        )
        .order_by(desc(LogAcesso.timestamp))
        .limit(JANELA_HISTORICO)
        .all()
    )
    duracoes_ms = [r[0] for r in rows if r[0] and r[0] > 0]
    if not duracoes_ms:
        return None
    # Mediana em segundos, arredondando pra cima pra não "terminar antes".
    mediana_ms = statistics.median(duracoes_ms)
    return max(1, math.ceil(mediana_ms / 1000))


def progresso_estimado(
    elapsed_s: float, duracao_estimada_s: Optional[int], teto: int = 95
) -> int:
    """
    Dado o tempo decorrido e a estimativa, retorna um % 0..teto.

    - Sem estimativa: 0 (front mostra barra indeterminada quando pct=0 e
      status é ativo).
    - Com estimativa: clampa em [0, teto] — o teto garante que não cole em
      100% antes do job de fato terminar. Quando o executor marca concluído,
      ele mesmo seta pct=100.
    """
    if not duracao_estimada_s or duracao_estimada_s <= 0:
        return 0
    pct_bruto = (elapsed_s / duracao_estimada_s) * 100.0
    return max(0, min(teto, int(pct_bruto)))
