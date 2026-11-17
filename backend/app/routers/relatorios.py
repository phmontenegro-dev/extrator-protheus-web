"""
Endpoints de relatórios.

  GET  /relatorios                                lista os disponíveis
  POST /relatorios/{id}/extrair                   um endpoint por relatório

Padrão: toda extração passa por `executar_e_responder_csv`, que faz:
permissão + log + extração + tratamento + resposta CSV. Isso mantém os
endpoints enxutos — cada um é só uma closure chamando extrair_X + tratar_X
+ um nome de arquivo.

Para adicionar um novo relatório:
  1. Criar app/relatorios_prontos/<id>/extrair.py + tratar.py
  2. Registrar em app/relatorios_prontos/registry.py
  3. Adicionar endpoint aqui
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import get_usuario_atual
from app.database import get_db
from app.models.usuario import Usuario

from app.relatorios_prontos.registry import RELATORIOS
from app.relatorios_prontos.ct2010.extrair import extrair_ct2010
from app.relatorios_prontos.ct2010.tratar import tratar_dataframe as tratar_ct2010
from app.relatorios_prontos.qpr010.extrair import extrair_qpr010
from app.relatorios_prontos.qpr010.tratar import tratar_dataframe as tratar_qpr010
from app.relatorios_prontos.sft010.extrair import extrair_sft010
from app.relatorios_prontos.sft010.tratar import tratar_dataframe as tratar_sft010
from app.relatorios_prontos.sd3010.extrair import extrair_sd3010
from app.relatorios_prontos.sd3010.tratar import tratar_dataframe as tratar_sd3010
from app.relatorios_prontos.sb8_suzano.extrair import extrair_sb8_suzano
from app.relatorios_prontos.sb8_suzano.tratar import tratar_dataframe as tratar_sb8_suzano
from app.relatorios_prontos.sd1_suzano.extrair import extrair_sd1_suzano
from app.relatorios_prontos.sd1_suzano.tratar import tratar_dataframe as tratar_sd1_suzano
from app.relatorios_prontos.sd2_suzano.extrair import extrair_sd2_suzano
from app.relatorios_prontos.sd2_suzano.tratar import tratar_dataframe as tratar_sd2_suzano
from app.relatorios_prontos.sd4_suzano.extrair import extrair_sd4_suzano
from app.relatorios_prontos.sd4_suzano.tratar import tratar_dataframe as tratar_sd4_suzano
from app.relatorios_prontos.sh6_suzano.extrair import extrair_sh6_suzano
from app.relatorios_prontos.sh6_suzano.tratar import tratar_dataframe as tratar_sh6_suzano
from app.relatorios_prontos.consolidado_suzano_jhon.extrair import extrair_consolidado_suzano_jhon
from app.relatorios_prontos.consolidado_suzano_jhon.tratar import tratar_dataframe as tratar_consolidado_suzano_jhon
from app.relatorios_prontos.paradas_maquina.extrair import extrair_paradas_maquina
from app.relatorios_prontos.paradas_maquina.tratar import tratar_dataframe as tratar_paradas_maquina

from app.models.area import Area
from app.models.relatorio_area import RelatorioArea
from app.schemas.relatorios import FiltrosFilialPeriodo, FiltrosPeriodo, RelatorioInfo
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
    # Carrega todas as atribuições relatório→área em uma query só (inner join
    # com Area). Dict por relatorio_id pra lookup O(1).
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
# Relatórios com filtros de PERÍODO (data_inicio + data_fim)
# =============================================================================

@router.post("/ct2010/extrair")
def ct2010(filtros: FiltrosPeriodo, request: Request,
           db: Session = Depends(get_db),
           usuario: Usuario = Depends(get_usuario_atual)) -> StreamingResponse:
    di, df = filtros.para_aaaammdd()
    return executar_e_responder_csv(
        db=db, request=request, usuario=usuario,
        relatorio_id="ct2010",
        nome_arquivo=f"CT2010_tratado_{di}_a_{df}.csv",
        extrair_fn=lambda: extrair_ct2010(di, df),
        tratar_fn=tratar_ct2010,
        parametros_log={"data_inicio": di, "data_fim": df},
    )


@router.post("/sft010/extrair")
def sft010(filtros: FiltrosPeriodo, request: Request,
           db: Session = Depends(get_db),
           usuario: Usuario = Depends(get_usuario_atual)) -> StreamingResponse:
    di, df = filtros.para_aaaammdd()
    return executar_e_responder_csv(
        db=db, request=request, usuario=usuario,
        relatorio_id="sft010",
        nome_arquivo=f"SFT010_tratado_{di}_a_{df}.csv",
        extrair_fn=lambda: extrair_sft010(di, df),
        tratar_fn=tratar_sft010,
        parametros_log={"data_inicio": di, "data_fim": df},
    )


@router.post("/sd3010/extrair")
def sd3010(filtros: FiltrosPeriodo, request: Request,
           db: Session = Depends(get_db),
           usuario: Usuario = Depends(get_usuario_atual)) -> StreamingResponse:
    di, df = filtros.para_aaaammdd()
    return executar_e_responder_csv(
        db=db, request=request, usuario=usuario,
        relatorio_id="sd3010",
        nome_arquivo=f"SD3010_tratado_{di}_a_{df}.csv",
        extrair_fn=lambda: extrair_sd3010(di, df),
        tratar_fn=tratar_sd3010,
        parametros_log={"data_inicio": di, "data_fim": df},
    )


@router.post("/sd4_suzano/extrair")
def sd4_suzano(filtros: FiltrosPeriodo, request: Request,
               db: Session = Depends(get_db),
               usuario: Usuario = Depends(get_usuario_atual)) -> StreamingResponse:
    di, df = filtros.para_aaaammdd()
    return executar_e_responder_csv(
        db=db, request=request, usuario=usuario,
        relatorio_id="sd4_suzano",
        nome_arquivo=f"SD4_SUZANO_tratado_{di}_a_{df}.csv",
        extrair_fn=lambda: extrair_sd4_suzano(di, df),
        tratar_fn=tratar_sd4_suzano,
        parametros_log={"data_inicio": di, "data_fim": df},
    )


@router.post("/sh6_suzano/extrair")
def sh6_suzano(filtros: FiltrosPeriodo, request: Request,
               db: Session = Depends(get_db),
               usuario: Usuario = Depends(get_usuario_atual)) -> StreamingResponse:
    di, df = filtros.para_aaaammdd()
    return executar_e_responder_csv(
        db=db, request=request, usuario=usuario,
        relatorio_id="sh6_suzano",
        nome_arquivo=f"SH6_SUZANO_tratado_{di}_a_{df}.csv",
        extrair_fn=lambda: extrair_sh6_suzano(di, df),
        tratar_fn=tratar_sh6_suzano,
        parametros_log={"data_inicio": di, "data_fim": df},
    )


@router.post("/consolidado_suzano_jhon/extrair")
def consolidado_suzano_jhon(filtros: FiltrosPeriodo, request: Request,
                            db: Session = Depends(get_db),
                            usuario: Usuario = Depends(get_usuario_atual)) -> StreamingResponse:
    di, df = filtros.para_aaaammdd()
    return executar_e_responder_csv(
        db=db, request=request, usuario=usuario,
        relatorio_id="consolidado_suzano_jhon",
        nome_arquivo=f"ConsolidadoSuzanoJhon_tratado_{di}_a_{df}.csv",
        extrair_fn=lambda: extrair_consolidado_suzano_jhon(di, df),
        tratar_fn=tratar_consolidado_suzano_jhon,
        parametros_log={"data_inicio": di, "data_fim": df},
    )


@router.post("/paradas_maquina/extrair")
def paradas_maquina(filtros: FiltrosPeriodo, request: Request,
                    db: Session = Depends(get_db),
                    usuario: Usuario = Depends(get_usuario_atual)) -> StreamingResponse:
    di, df = filtros.para_aaaammdd()
    return executar_e_responder_csv(
        db=db, request=request, usuario=usuario,
        relatorio_id="paradas_maquina",
        nome_arquivo=f"ParadasMaquina_{di}_a_{df}.csv",
        extrair_fn=lambda: extrair_paradas_maquina(di, df),
        tratar_fn=tratar_paradas_maquina,
        parametros_log={"data_inicio": di, "data_fim": df},
    )


# =============================================================================
# Relatório com filtros de FILIAL + PERÍODO
# =============================================================================

@router.post("/qpr010/extrair")
def qpr010(filtros: FiltrosFilialPeriodo, request: Request,
           db: Session = Depends(get_db),
           usuario: Usuario = Depends(get_usuario_atual)) -> StreamingResponse:
    di, df = filtros.para_aaaammdd()
    filial = filtros.filial.strip()
    return executar_e_responder_csv(
        db=db, request=request, usuario=usuario,
        relatorio_id="qpr010",
        nome_arquivo=f"QPR010_{filial}_{di}_a_{df}.csv",
        extrair_fn=lambda: extrair_qpr010(filial, di, df),
        tratar_fn=tratar_qpr010,
        parametros_log={"filial": filial, "data_inicio": di, "data_fim": df},
    )


# =============================================================================
# Relatórios SEM filtros (Suzano fixos)
# =============================================================================

@router.post("/sb8_suzano/extrair")
def sb8_suzano(request: Request,
               db: Session = Depends(get_db),
               usuario: Usuario = Depends(get_usuario_atual)) -> StreamingResponse:
    return executar_e_responder_csv(
        db=db, request=request, usuario=usuario,
        relatorio_id="sb8_suzano",
        nome_arquivo="SB8_SUZANO_tratado.csv",
        extrair_fn=lambda: extrair_sb8_suzano(),
        tratar_fn=tratar_sb8_suzano,
    )


@router.post("/sd1_suzano/extrair")
def sd1_suzano(request: Request,
               db: Session = Depends(get_db),
               usuario: Usuario = Depends(get_usuario_atual)) -> StreamingResponse:
    return executar_e_responder_csv(
        db=db, request=request, usuario=usuario,
        relatorio_id="sd1_suzano",
        nome_arquivo="SD1_SUZANO_tratado.csv",
        extrair_fn=lambda: extrair_sd1_suzano(),
        tratar_fn=tratar_sd1_suzano,
    )


@router.post("/sd2_suzano/extrair")
def sd2_suzano(request: Request,
               db: Session = Depends(get_db),
               usuario: Usuario = Depends(get_usuario_atual)) -> StreamingResponse:
    return executar_e_responder_csv(
        db=db, request=request, usuario=usuario,
        relatorio_id="sd2_suzano",
        nome_arquivo="SD2_SUZANO_tratado.csv",
        extrair_fn=lambda: extrair_sd2_suzano(),
        tratar_fn=tratar_sd2_suzano,
    )
