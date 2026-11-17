import { FormEvent, useEffect, useMemo, useState } from 'react'
import {
  extrairLivre,
  listarColunas,
  listarTabelas,
  TabelaInfo,
} from '../../api/relatorioLivre'
import { mensagemErro } from '../../api/client'

/**
 * Formulário do Relatório Livre.
 *
 * Fluxo:
 *   1. Carrega a lista de tabelas Protheus (pode demorar — consulta ALL_TABLES)
 *   2. Usuário escolhe uma tabela via combo com autocomplete (datalist nativo)
 *   3. Ao escolher, buscamos as colunas (ALL_TAB_COLUMNS, sem binários)
 *   4. Usuário marca as colunas + escolhe campo_data (opcional)
 *   5. Preenche datas (se campo_data informado) e max_linhas (opcional)
 *   6. Extrair → download direto do CSV
 *
 * Datalist HTML nativo escolhido em vez de um combo custom: zero JS, suporta
 * digitação+filtro automaticamente e aproveita o UI do navegador.
 */
export default function FormLivre() {
  const [tabelas, setTabelas] = useState<TabelaInfo[]>([])
  const [tabelasCarregando, setTabelasCarregando] = useState(true)
  const [erroGeral, setErroGeral] = useState<string | null>(null)

  // Seleção do usuário.
  const [tabelaInput, setTabelaInput] = useState('')
  const [colunasDisponiveis, setColunasDisponiveis] = useState<string[]>([])
  const [colunasSelecionadas, setColunasSelecionadas] = useState<Set<string>>(new Set())
  const [carregandoColunas, setCarregandoColunas] = useState(false)
  const [erroColunas, setErroColunas] = useState<string | null>(null)

  const [campoData, setCampoData] = useState<string>('')    // "" = sem filtro de data
  const [dataInicio, setDataInicio] = useState('')
  const [dataFim, setDataFim] = useState('')
  const [maxLinhas, setMaxLinhas] = useState('')

  const [extraindo, setExtraindo] = useState(false)
  const [erroExtracao, setErroExtracao] = useState<string | null>(null)

  // Bootstrap: lista de tabelas.
  useEffect(() => {
    let ativo = true
    listarTabelas()
      .then((ts) => {
        if (ativo) setTabelas(ts)
      })
      .catch((e) => {
        if (ativo) setErroGeral(mensagemErro(e, 'Não foi possível carregar as tabelas.'))
      })
      .finally(() => {
        if (ativo) setTabelasCarregando(false)
      })
    return () => {
      ativo = false
    }
  }, [])

  // Lookup rápido de metadata (descrição + campo_data sugerido).
  const mapaTabelas = useMemo(() => {
    const m = new Map<string, TabelaInfo>()
    tabelas.forEach((t) => m.set(t.nome, t))
    return m
  }, [tabelas])

  const tabelaSelecionada = mapaTabelas.get(tabelaInput.toUpperCase().trim())

  // Ao trocar de tabela (válida), busca as colunas e aplica a sugestão de
  // campo_data se a tabela estiver no TABELAS_CONHECIDAS.
  useEffect(() => {
    if (!tabelaSelecionada) {
      setColunasDisponiveis([])
      setColunasSelecionadas(new Set())
      setCampoData('')
      setErroColunas(null)
      return
    }

    let ativo = true
    setCarregandoColunas(true)
    setErroColunas(null)
    setColunasSelecionadas(new Set())

    listarColunas(tabelaSelecionada.nome)
      .then((r) => {
        if (!ativo) return
        setColunasDisponiveis(r.colunas)
        // Pré-seleciona o campo de data se sugerido E se existe na tabela.
        const sugestao = tabelaSelecionada.campo_data_sugerido
        if (sugestao && r.colunas.includes(sugestao)) {
          setCampoData(sugestao)
        } else {
          setCampoData('')
        }
      })
      .catch((e) => {
        if (ativo) setErroColunas(mensagemErro(e, 'Não foi possível carregar as colunas.'))
      })
      .finally(() => {
        if (ativo) setCarregandoColunas(false)
      })

    return () => {
      ativo = false
    }
  }, [tabelaSelecionada])

  const toggleColuna = (col: string) => {
    const nova = new Set(colunasSelecionadas)
    if (nova.has(col)) nova.delete(col)
    else nova.add(col)
    setColunasSelecionadas(nova)
  }

  const marcarTodas = () => setColunasSelecionadas(new Set(colunasDisponiveis))
  const limparSelecao = () => setColunasSelecionadas(new Set())

  const submeter = async (e: FormEvent) => {
    e.preventDefault()
    setErroExtracao(null)

    if (!tabelaSelecionada) {
      setErroExtracao('Escolha uma tabela válida da lista.')
      return
    }
    if (colunasSelecionadas.size === 0) {
      setErroExtracao('Selecione pelo menos uma coluna.')
      return
    }

    const temCampoData = campoData.trim() !== ''
    if (temCampoData) {
      if (!dataInicio || !dataFim) {
        setErroExtracao('Informe as duas datas quando o campo de data estiver definido.')
        return
      }
      if (dataInicio > dataFim) {
        setErroExtracao('Data inicial não pode ser maior que data final.')
        return
      }
    } else {
      // Aviso duplo — "sem filtro de data" pode gerar MUITA linha.
      const prosseguir = window.confirm(
        'Você escolheu NÃO filtrar por data. A extração pode retornar milhões de linhas e ' +
        'demorar bastante. Deseja continuar?'
      )
      if (!prosseguir) return
    }

    const max = maxLinhas.trim()
    let maxNum: number | null = null
    if (max) {
      const n = Number(max)
      if (!Number.isInteger(n) || n <= 0) {
        setErroExtracao('Máximo de linhas deve ser um inteiro positivo.')
        return
      }
      maxNum = n
    }

    setExtraindo(true)
    try {
      await extrairLivre({
        tabela: tabelaSelecionada.nome,
        colunas: Array.from(colunasSelecionadas),
        campo_data: temCampoData ? campoData : null,
        data_inicio: temCampoData ? dataInicio : null,
        data_fim: temCampoData ? dataFim : null,
        max_linhas: maxNum,
      })
    } catch (e) {
      setErroExtracao(mensagemErro(e, 'Falha ao extrair.'))
    } finally {
      setExtraindo(false)
    }
  }

  // ---- Render ----

  if (tabelasCarregando) {
    return <p className="text-muted-foreground">Carregando lista de tabelas...</p>
  }

  if (erroGeral) {
    return (
      <div className="border border-destructive/30 bg-destructive/10 text-destructive text-sm rounded-lg p-3">
        {erroGeral}
      </div>
    )
  }

  const nomeDigitadoENaoReconhecido =
    tabelaInput.trim() !== '' && !tabelaSelecionada

  return (
    <form onSubmit={submeter} className="space-y-6">
      {/* 1) Tabela */}
      <div>
        <label htmlFor="tabela" className="block text-sm font-medium mb-1">
          Tabela
        </label>
        <input
          id="tabela"
          list="lista-tabelas"
          type="text"
          value={tabelaInput}
          onChange={(e) => setTabelaInput(e.target.value.toUpperCase())}
          disabled={extraindo}
          placeholder="Digite para filtrar (ex.: SB1010)"
          className="w-full rounded-lg border border-border bg-surface px-3 py-2 outline-none focus:ring-2 focus:ring-ring disabled:opacity-50 font-mono"
        />
        <datalist id="lista-tabelas">
          {tabelas.map((t) => (
            <option key={t.nome} value={t.nome}>
              {t.descricao ?? t.nome}
            </option>
          ))}
        </datalist>
        {tabelaSelecionada?.descricao && (
          <p className="text-xs text-muted-foreground mt-1">{tabelaSelecionada.descricao}</p>
        )}
        {nomeDigitadoENaoReconhecido && (
          <p className="text-xs text-primary mt-1">
            Tabela não reconhecida. Escolha uma da lista.
          </p>
        )}
        <p className="text-xs text-muted-foreground mt-1">
          {tabelas.length} tabelas disponíveis.
        </p>
      </div>

      {/* 2) Colunas */}
      {tabelaSelecionada && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="block text-sm font-medium">Colunas a extrair</label>
            {colunasDisponiveis.length > 0 && (
              <div className="flex gap-2 text-xs">
                <button
                  type="button"
                  onClick={marcarTodas}
                  className="px-2 py-1 rounded border border-border"
                >
                  Marcar todas
                </button>
                <button
                  type="button"
                  onClick={limparSelecao}
                  className="px-2 py-1 rounded border border-border"
                >
                  Limpar
                </button>
              </div>
            )}
          </div>

          {carregandoColunas && (
            <p className="text-sm text-muted-foreground">Carregando colunas...</p>
          )}
          {erroColunas && (
            <div className="border border-destructive/30 bg-destructive/10 text-destructive text-sm rounded-lg p-3">
              {erroColunas}
            </div>
          )}

          {!carregandoColunas && !erroColunas && (
            <>
              <div className="border border-border rounded-lg p-3 max-h-72 overflow-y-auto grid grid-cols-2 md:grid-cols-3 gap-y-1 gap-x-3">
                {colunasDisponiveis.map((c) => (
                  <label key={c} className="flex items-center gap-2 text-xs font-mono">
                    <input
                      type="checkbox"
                      checked={colunasSelecionadas.has(c)}
                      onChange={() => toggleColuna(c)}
                      className="rounded"
                    />
                    {c}
                  </label>
                ))}
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                {colunasSelecionadas.size} selecionadas / {colunasDisponiveis.length} disponíveis.
                Campos binários (BLOB, LONG, RAW) são ocultados automaticamente.
              </p>
            </>
          )}
        </div>
      )}

      {/* 3) Campo de data + período */}
      {tabelaSelecionada && colunasDisponiveis.length > 0 && (
        <div className="space-y-3">
          <div>
            <label htmlFor="campo_data" className="block text-sm font-medium mb-1">
              Campo de data
            </label>
            <select
              id="campo_data"
              value={campoData}
              onChange={(e) => setCampoData(e.target.value)}
              disabled={extraindo}
              className="w-full md:w-80 rounded-lg border border-border bg-surface px-3 py-2 font-mono text-sm"
            >
              <option value="">(sem filtro de data)</option>
              {colunasDisponiveis.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
            <p className="text-xs text-muted-foreground mt-1">
              Escolha a coluna que será usada no BETWEEN, ou deixe "(sem filtro de data)".
            </p>
          </div>

          {campoData && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label htmlFor="di" className="block text-sm font-medium mb-1">Data inicial</label>
                <input
                  id="di"
                  type="date"
                  value={dataInicio}
                  onChange={(e) => setDataInicio(e.target.value)}
                  disabled={extraindo}
                  className="w-full rounded-lg border border-border bg-surface px-3 py-2"
                />
              </div>
              <div>
                <label htmlFor="df" className="block text-sm font-medium mb-1">Data final</label>
                <input
                  id="df"
                  type="date"
                  value={dataFim}
                  onChange={(e) => setDataFim(e.target.value)}
                  disabled={extraindo}
                  className="w-full rounded-lg border border-border bg-surface px-3 py-2"
                />
              </div>
            </div>
          )}
        </div>
      )}

      {/* 4) Max linhas */}
      {tabelaSelecionada && colunasDisponiveis.length > 0 && (
        <div>
          <label htmlFor="max_linhas" className="block text-sm font-medium mb-1">
            Máximo de linhas <span className="text-muted-foreground text-xs">(opcional)</span>
          </label>
          <input
            id="max_linhas"
            type="number"
            min="1"
            step="1"
            value={maxLinhas}
            onChange={(e) => setMaxLinhas(e.target.value)}
            disabled={extraindo}
            placeholder="Sem limite"
            className="w-full md:w-48 rounded-lg border border-border bg-surface px-3 py-2"
          />
          <p className="text-xs text-muted-foreground mt-1">
            Aplica <span className="font-mono">ROWNUM &lt;= N</span>. Útil para teste rápido.
          </p>
        </div>
      )}

      {erroExtracao && (
        <div
          role="alert"
          className="border border-destructive/30 bg-destructive/10 text-destructive text-sm rounded-lg p-3"
        >
          {erroExtracao}
        </div>
      )}

      {tabelaSelecionada && colunasDisponiveis.length > 0 && (
        <div>
          <button
            type="submit"
            disabled={extraindo || colunasSelecionadas.size === 0}
            className="w-full md:w-auto px-6 bg-primary text-primary-foreground rounded-lg py-2 font-medium disabled:opacity-50"
          >
            {extraindo ? 'Extraindo (pode levar alguns minutos)...' : 'Extrair CSV'}
          </button>
          {extraindo && (
            <p className="text-xs text-muted-foreground mt-2">
              Não feche esta aba.
            </p>
          )}
        </div>
      )}
    </form>
  )
}
