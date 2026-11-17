"""
Endpoints administrativos para gerenciar áreas e atribuição de relatórios
a áreas.

  GET    /admin/areas                  lista áreas ordenadas
  POST   /admin/areas                  cria área nova
  PATCH  /admin/areas/{id}             edita (nome/descricao/ordem)
  DELETE /admin/areas/{id}             remove (atribuições são apagadas em cascata)
  PUT    /admin/areas/ordem            reordena (lista de IDs na ordem desejada)

  GET    /admin/relatorio-areas        lista todas as atribuições relatorio→area
  PUT    /admin/relatorio-areas/{rid}  atribui (ou desatribui com area_id=null)
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_admin_atual
from app.database import get_db
from app.models.area import Area
from app.models.relatorio_area import RelatorioArea
from app.models.usuario import Usuario
from app.relatorios_prontos.registry import existe as relatorio_existe
from app.schemas.areas import (
    AreaCreate,
    AreaDetalhe,
    AreaUpdate,
    AtribuirRelatorioPayload,
    RelatorioAreaInfo,
    ReordenarAreasPayload,
)
from app.utils import logs


router = APIRouter(prefix="/admin", tags=["admin-areas"])


# =============================================================================
# Áreas — CRUD
# =============================================================================

@router.get("/areas", response_model=list[AreaDetalhe])
def listar_areas(
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(get_admin_atual),
) -> list[AreaDetalhe]:
    """Lista áreas ordenadas por ordem, nome (desempate)."""
    rows = db.query(Area).order_by(Area.ordem, Area.nome).all()
    return [AreaDetalhe.model_validate(a) for a in rows]


@router.post("/areas", response_model=AreaDetalhe, status_code=status.HTTP_201_CREATED)
def criar_area(
    payload: AreaCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(get_admin_atual),
) -> AreaDetalhe:
    nome = payload.nome.strip()
    if not nome:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Nome vazio.")
    existente = db.query(Area).filter(Area.nome == nome).first()
    if existente is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Área '{nome}' já existe.")

    nova = Area(
        nome=nome,
        descricao=(payload.descricao or "").strip() or None,
        ordem=payload.ordem,
    )
    db.add(nova)
    db.commit()
    db.refresh(nova)

    logs.registrar(
        db, acao="admin_criou_area", request=request,
        usuario_id=admin.id, username=admin.username,
        parametros={"area_id": nova.id, "nome": nova.nome},
    )
    return AreaDetalhe.model_validate(nova)


@router.patch("/areas/{area_id}", response_model=AreaDetalhe)
def editar_area(
    area_id: int,
    payload: AreaUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(get_admin_atual),
) -> AreaDetalhe:
    area = db.query(Area).filter(Area.id == area_id).first()
    if area is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Área não encontrada.")

    mudancas: dict = {}
    if payload.nome is not None:
        novo_nome = payload.nome.strip()
        if not novo_nome:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Nome vazio.")
        if novo_nome != area.nome:
            # Checa colisão com outra área
            outra = db.query(Area).filter(
                Area.nome == novo_nome, Area.id != area.id
            ).first()
            if outra is not None:
                raise HTTPException(
                    status.HTTP_409_CONFLICT, f"Área '{novo_nome}' já existe.",
                )
            mudancas["nome"] = (area.nome, novo_nome)
            area.nome = novo_nome

    if payload.descricao is not None:
        nova_desc = payload.descricao.strip() or None
        if nova_desc != area.descricao:
            mudancas["descricao"] = (area.descricao, nova_desc)
            area.descricao = nova_desc

    if payload.ordem is not None and payload.ordem != area.ordem:
        mudancas["ordem"] = (area.ordem, payload.ordem)
        area.ordem = payload.ordem

    if not mudancas:
        return AreaDetalhe.model_validate(area)

    db.commit()
    db.refresh(area)

    logs.registrar(
        db, acao="admin_editou_area", request=request,
        usuario_id=admin.id, username=admin.username,
        parametros={"area_id": area.id, "mudancas":
                    {k: {"de": str(a), "para": str(b)} for k, (a, b) in mudancas.items()}},
    )
    return AreaDetalhe.model_validate(area)


@router.delete("/areas/{area_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_area(
    area_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(get_admin_atual),
):
    area = db.query(Area).filter(Area.id == area_id).first()
    if area is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Área não encontrada.")

    nome_antigo = area.nome
    # Atribuições (relatorio_areas) caem em cascata pela FK ondelete="CASCADE"
    db.delete(area)
    db.commit()

    logs.registrar(
        db, acao="admin_removeu_area", request=request,
        usuario_id=admin.id, username=admin.username,
        parametros={"area_id": area_id, "nome": nome_antigo},
    )


@router.put("/areas/ordem", response_model=list[AreaDetalhe])
def reordenar_areas(
    payload: ReordenarAreasPayload,
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(get_admin_atual),
) -> list[AreaDetalhe]:
    """
    Reordena as áreas segundo a lista de IDs recebida. IDs não listados
    mantêm a posição relativa (ficam no fim, mantendo ordem_original).
    """
    # Busca todas as áreas existentes
    todas = {a.id: a for a in db.query(Area).all()}
    ids_validos = [i for i in payload.ids if i in todas]

    # Primeiro aplica a ordem da lista
    for idx, area_id in enumerate(ids_validos):
        todas[area_id].ordem = idx

    # IDs fora da lista: ficam após a última, mantendo ordem relativa anterior
    restantes = [a for aid, a in todas.items() if aid not in set(ids_validos)]
    restantes.sort(key=lambda a: (a.ordem, a.nome))
    for idx, a in enumerate(restantes, start=len(ids_validos)):
        a.ordem = idx

    db.commit()

    logs.registrar(
        db, acao="admin_reordenou_areas", request=request,
        usuario_id=admin.id, username=admin.username,
        parametros={"ids_na_ordem": payload.ids},
    )
    rows = db.query(Area).order_by(Area.ordem, Area.nome).all()
    return [AreaDetalhe.model_validate(a) for a in rows]


# =============================================================================
# Atribuição relatório → área
# =============================================================================

@router.get("/relatorio-areas", response_model=list[RelatorioAreaInfo])
def listar_atribuicoes(
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(get_admin_atual),
) -> list[RelatorioAreaInfo]:
    """Lista todas as atribuições relatorio → area no banco."""
    rows = db.query(RelatorioArea).all()
    return [
        RelatorioAreaInfo(relatorio_id=r.relatorio_id, area_id=r.area_id)
        for r in rows
    ]


@router.put("/relatorio-areas/{relatorio_id}", response_model=RelatorioAreaInfo)
def atribuir_relatorio(
    relatorio_id: str,
    payload: AtribuirRelatorioPayload,
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(get_admin_atual),
) -> RelatorioAreaInfo:
    """
    Atribui uma área ao relatório. area_id=null desatribui (vira "Outros").
    Idempotente — chamar repetido com mesmo valor não gera erro.
    """
    # Valida que o relatório existe no registry
    if not relatorio_existe(relatorio_id):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Relatório '{relatorio_id}' não existe no registry.",
        )

    # Se area_id foi informado, valida que a área existe
    if payload.area_id is not None:
        area = db.query(Area).filter(Area.id == payload.area_id).first()
        if area is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"Área {payload.area_id} não encontrada.",
            )

    atrib = db.query(RelatorioArea).filter(
        RelatorioArea.relatorio_id == relatorio_id
    ).first()

    if payload.area_id is None:
        # Desatribui
        if atrib is not None:
            db.delete(atrib)
            db.commit()
        _log(db, request, admin, relatorio_id, None)
        return RelatorioAreaInfo(relatorio_id=relatorio_id, area_id=None)

    if atrib is None:
        atrib = RelatorioArea(relatorio_id=relatorio_id, area_id=payload.area_id)
        db.add(atrib)
    else:
        atrib.area_id = payload.area_id

    db.commit()
    _log(db, request, admin, relatorio_id, payload.area_id)
    return RelatorioAreaInfo(relatorio_id=relatorio_id, area_id=payload.area_id)


def _log(db: Session, request: Request, admin: Usuario,
         relatorio_id: str, area_id: Optional[int]) -> None:
    logs.registrar(
        db, acao="admin_atribuiu_area", request=request,
        usuario_id=admin.id, username=admin.username,
        relatorio_id=relatorio_id,
        parametros={"area_id": area_id},
    )
