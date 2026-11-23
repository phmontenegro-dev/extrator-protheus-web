"""
Endpoints de relatórios prontos (Etapa 11.6 — auto-descoberta).

  GET  /relatorios                           lista os disponíveis (filtrada por permissão)
  POST /relatorios/{id}/extrair              endpoint UNIVERSAL de extração síncrona

Cada relatório pronto é descoberto automaticamente a partir de
`app.relatorios_prontos.*` — ver `base.py`. Pra adicionar/remover relatório,
NÃO mexa aqui — crie o pacote/arquivo correspondente.
"""
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_usuario_atual
from app.database import get_db
from app.models.area import Area
from app.models.relatorio_area import RelatorioArea
from app.models.usuario import Usuario
from app.relatorios_prontos.base import RelatorioPronto
from app.relatorios_prontos.registry import (
    RELATORIOS,
    buscar_pronto,
)
from app.schemas.relatorios import (
    FiltrosFilialPeriodo,
    FiltrosPeriodo,
    RelatorioInfo,
)
from app.utils.permissoes import relatorios_permitidos
from app.utils.relatorio_runner import executar_e_responder_csv


router = APIRouter(prefix="/relatorios", tags=["relatorios"])


# =============================================================================
# Listagem
# =============================================================================

@router.get("", response_model=list[RelatorioInfo])
def listar(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
) -> list[RelatorioInfo]:
    """
    Admin vê todos; usuário comum só vê os em permissoes_relatorio.

    Cada relatório retorna também sua área atribuída (area_id, area_nome,
    area_ordem). Relatórios sem atribuição retornam None nos 3 campos, e
    o frontend os exibe na seção "Outros".
    """
    mapa_area: dict[str, tuple[int, str, int]] = {}
    for rel, area in (
        db.query(RelatorioArea, Area)
        .join(Area, Area.id == RelatorioArea.area_id)
        .all()
    ):
        mapa_area[rel.relatorio_id] = (area.id, area.nome, area.ordem)

    if usuario.is_admin:
        base = RELATORIOS
    else:
        permitidos = relatorios_permitidos(db, usuario)
        base = [r for r in RELATORIOS if r["id"] in permitidos]

    resultado: list[RelatorioInfo] = []
    for r in base:
        area_info = mapa_area.get(r["id"])
        resultado.append(RelatorioInfo(
            **r,
            area_id=area_info[0] if area_info else None,
            area_nome=area_info[1] if area_info else None,
            area_ordem=area_info[2] if area_info else None,
        ))
    return resultado


# =============================================================================
# POST /{id}/extrair — endpoint único que despacha por tipo de filtro
# =============================================================================

@router.post("/{relatorio_id}/extrair")
def extrair_generico(
    relatorio_id: str,
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
) -> StreamingResponse:
    """
    Endpoint síncrono universal. Despacha pela configuração do RelatorioPronto
    descoberto automaticamente.

    O payload varia conforme o tipo de filtros:
      - nenhum          → {}  (ou corpo vazio)
      - periodo         → {"data_inicio": "YYYY-MM-DD", "data_fim": "YYYY-MM-DD"}
      - filial_periodo  → {"filial": "...", "data_inicio": "...", "data_fim": "..."}
    """
    rel = buscar_pronto(relatorio_id)
    if rel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Relatório pronto '{relatorio_id}' não existe.",
        )

    try:
        filtros_runner, parametros_log = _validar_payload(rel, payload or {})
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=e.errors(),
        )

    nome_arquivo = rel.nome_arquivo(filtros_runner)

    return executar_e_responder_csv(
        db=db, request=request, usuario=usuario,
        relatorio_id=rel.id,
        nome_arquivo=nome_arquivo,
        extrair_fn=lambda: rel.extrair(**filtros_runner),
        tratar_fn=rel.tratar,
        parametros_log=parametros_log,
    )


# =============================================================================
# Helpers
# =============================================================================

def _validar_payload(
    rel: RelatorioPronto,
    payload: dict,
) -> tuple[dict, Optional[dict]]:
    """
    Valida o payload contra o schema correto baseado em rel.filtros.
    Retorna (filtros_para_extrair, parametros_para_log).
    """
    if rel.filtros == "nenhum":
        return {}, None

    if rel.filtros == "periodo":
        f = FiltrosPeriodo(**payload)
        di, df = f.para_aaaammdd()
        return {"data_inicio": di, "data_fim": df}, {"data_inicio": di, "data_fim": df}

    if rel.filtros == "filial_periodo":
        f = FiltrosFilialPeriodo(**payload)
        di, df = f.para_aaaammdd()
        fil = f.filial.strip()
        return (
            {"filial": fil, "data_inicio": di, "data_fim": df},
            {"filial": fil, "data_inicio": di, "data_fim": df},
        )

    # Defesa (tipo "livre" ou "sql" não deveriam cair aqui — têm rotas próprias)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Relatório '{rel.id}' tem filtros={rel.filtros!r} que usa endpoint específico.",
    )
