"""
Endpoints do Relatório Livre.

  GET  /relatorio-livre/tabelas              → lista as tabelas Protheus
  GET  /relatorio-livre/colunas/{tabela}     → colunas da tabela (sem binários)
  POST /relatorio-livre/extrair              → extração crua + download CSV

Autorização: todos exigem permissão "relatorio_livre" (admin passa; usuário
comum precisa estar em permissoes_relatorio com relatorio_id='relatorio_livre').

Essa escolha mantém o modelo de permissão uniforme — a mesma tela admin que
libera os relatórios prontos libera também o Livre (que aparece como mais um
"id" no sistema de permissões, apesar de ter rota própria).
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import get_usuario_atual
from app.database import get_db
from app.models.usuario import Usuario
from app.relatorio_livre.config_tabelas import TABELAS_CONHECIDAS
from app.relatorio_livre.consulta_colunas import listar_colunas, listar_tabelas
from app.relatorio_livre.extrair import extrair
from app.schemas.relatorio_livre import ColunasResponse, FiltrosLivre, TabelaInfo
from app.utils import logs
from app.utils.permissoes import pode_acessar
from app.utils.relatorio_runner import executar_e_responder_csv


RELATORIO_ID = "relatorio_livre"

router = APIRouter(prefix="/relatorio-livre", tags=["relatorio-livre"])


def _exigir_permissao(db: Session, usuario: Usuario, request: Request) -> None:
    """Checa permissão e registra log de acesso negado quando bloqueia."""
    if not pode_acessar(db, usuario, RELATORIO_ID):
        logs.registrar(
            db, acao="acesso_negado", request=request,
            usuario_id=usuario.id, username=usuario.username,
            relatorio_id=RELATORIO_ID, sucesso=False,
            erro_mensagem="sem permissão para relatorio_livre",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para o Relatório Livre.",
        )


@router.get("/tabelas", response_model=list[TabelaInfo])
def tabelas(
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
) -> list[TabelaInfo]:
    """Lista todas as tabelas Protheus visíveis (filtro regex do config)."""
    _exigir_permissao(db, usuario, request)
    nomes = listar_tabelas()
    resultado: list[TabelaInfo] = []
    for n in nomes:
        info = TABELAS_CONHECIDAS.get(n)
        if info:
            resultado.append(TabelaInfo(
                nome=n,
                descricao=info.get("descricao"),
                campo_data_sugerido=info.get("campo_data"),
            ))
        else:
            resultado.append(TabelaInfo(nome=n))
    return resultado


@router.get("/colunas/{tabela}", response_model=ColunasResponse)
def colunas(
    tabela: str,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
) -> ColunasResponse:
    """Colunas da tabela (sem binários/LONG/BLOB), em ordem de column_id."""
    _exigir_permissao(db, usuario, request)
    tabela_upper = tabela.upper()
    # Validação dupla: garante que a tabela realmente existe no dicionário
    # (listar_colunas aceita qualquer string, mas se não houver colunas,
    # provavelmente é tabela inválida).
    if tabela_upper not in set(listar_tabelas()):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tabela '{tabela_upper}' não encontrada.",
        )
    return ColunasResponse(tabela=tabela_upper, colunas=listar_colunas(tabela_upper))


@router.post("/extrair")
def extrair_endpoint(
    filtros: FiltrosLivre,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
) -> StreamingResponse:
    """Extração crua + download CSV."""
    tabela = filtros.tabela.upper()
    di, df = filtros.datas_aaaammdd()
    campo_data = filtros.campo_data

    # Monta um nome descritivo pro arquivo. Sem data quando "sem filtro".
    if di and df:
        nome_arquivo = f"Livre_{tabela}_{di}_a_{df}.csv"
    else:
        nome_arquivo = f"Livre_{tabela}.csv"

    parametros = {
        "tabela": tabela,
        "colunas": filtros.colunas,
        "campo_data": campo_data,
        "data_inicio": di,
        "data_fim": df,
        "max_linhas": filtros.max_linhas,
    }

    return executar_e_responder_csv(
        db=db, request=request, usuario=usuario,
        relatorio_id=RELATORIO_ID,
        nome_arquivo=nome_arquivo,
        extrair_fn=lambda: extrair(
            tabela=tabela,
            colunas=filtros.colunas,
            campo_data=campo_data,
            data_inicio=di,
            data_fim=df,
            max_linhas=filtros.max_linhas,
        ),
        tratar_fn=None,  # Livre não aplica tratamento — extração crua
        parametros_log=parametros,
    )
