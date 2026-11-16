import { FormEvent, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  extrairRelatorio,
  FiltrosPayload,
  listarRelatorios,
  RelatorioInfo,
  TipoFiltro,
} from '../../api/relatorios'
import { mensagemErro } from '../../api/client'
import { useAuth } from '../../auth/AuthContext'
import FormLivre from './FormLivre'

/**
 * Página única que atende todos os relatórios do registry.
 *
 * Lê o :id da URL, busca a lista de relatórios disponíveis (que o /relatorios
 * já filtra por permissão), pega o metadata do relatório e renderiza o
 * formulário certo baseado no campo `filtros`.
 *
 * Decisão de arquitetura: UMA página genérica em vez de 10 componentes. Dado
 * que os formulários são combinações de 3 campos (filial, data_inicio, data_fim),
 * um componente dinâmico simples é mais sustentável que 10 páginas quase
 * idênticas. Se um dia um relatório tiver filtros exóticos (ex: multi-select
 * com dados do banco), aí sim justifica uma página dedicada.
 */
export default function RelatorioGenerico() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { usuario, logout } = useAuth()

  const [relatorio, setRelatorio] = useState<RelatorioInfo | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [erroCarregamento, setErroCarregamento] = useState<string | null>(null)

  useEffect(() => {
    let ativo = true
    setCarregando(true)
    setErroCarregamento(null)
    listarRelatorios()
      .then((rs) => {
        if (!ativo) return
        const encontrado = rs.find((r) => r.id === id) ?? null
        setRelatorio(encontrado)
        if (!encontrado) {
          setErroCarregamento(
            'Relatório não disponível. Pode não existir ou você pode não ter permissão.',
          )
        }
      })
      .catch((e) => {
        if (ativo) setErroCarregamento(mensagemErro(e, 'Não foi possível carregar.'))
      })
      .finally(() => {
        if (ativo) setCarregando(false)
      })
    return () => {
      ativo = false
    }
  }, [id])

  return (
    <div className="min-h-screen">
      <header className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800">
        <div className="max-w-3xl mx-auto px-6 py-4 flex items-center justify-between">
          <button
            onClick={() => navigate('/menu')}
            className="text-sm text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100"
          >
            ← Menu
          </button>
          <h1 className="text-lg font-semibold text-center flex-1 px-4 truncate">
            {relatorio?.nome ?? 'Relatório'}
          </h1>
          <div className="flex items-center gap-2 text-sm">
            <span className="text-slate-500 dark:text-slate-400 text-xs hidden sm:inline">
              @{usuario?.username}
            </span>
            <button
              onClick={logout}
              className="px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 text-xs hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              Sair
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-10">
        {carregando && <p className="text-slate-500">Carregando relatório...</p>}

        {erroCarregamento && (
          <div
            role="alert"
            className="bg-red-100 dark:bg-red-950/40 text-red-700 dark:text-red-300 text-sm rounded-lg p-4"
          >
            {erroCarregamento}
            <div className="mt-3">
              <button
                onClick={() => navigate('/menu')}
                className="text-xs underline"
              >
                Voltar ao menu
              </button>
            </div>
          </div>
        )}

        {relatorio && (
          <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-lg p-8">
            <p className="text-sm text-slate-500 dark:text-slate-400 mb-6">
              {relatorio.descricao}
            </p>
            <FormularioExtracao relatorio={relatorio} />
          </div>
        )}
      </main>
    </div>
  )
}

// =============================================================================
// Formulário — dispatcher que escolhe o form pelo tipo de filtro
// =============================================================================

function FormularioExtracao({ relatorio }: { relatorio: RelatorioInfo }) {
  const [erro, setErro] = useState<string | null>(null)
  const [extraindo, setExtraindo] = useState(false)

  const executar = async (payload: FiltrosPayload) => {
    setErro(null)
    setExtraindo(true)
    try {
      await extrairRelatorio(relatorio.id, payload)
    } catch (e) {
      setErro(mensagemErro(e, 'Falha ao extrair o relatório.'))
    } finally {
      setExtraindo(false)
    }
  }

  // "livre" tem UI própria: combo de tabela + colunas dinâmicas + validações
  // específicas. Delegamos tudo pra FormLivre.tsx, que também cuida do
  // próprio estado de "extraindo" / erro, então pulamos os blocos genéricos.
  if (relatorio.filtros === 'livre') {
    return <FormLivre />
  }

  return (
    <>
      {relatorio.filtros === 'nenhum' && (
        <FormNenhum extraindo={extraindo} onExtrair={() => executar({})} />
      )}
      {relatorio.filtros === 'periodo' && (
        <FormPeriodo
          extraindo={extraindo}
          onExtrair={(f) => executar(f)}
          onErroValidacao={setErro}
        />
      )}
      {relatorio.filtros === 'filial_periodo' && (
        <FormFilialPeriodo
          extraindo={extraindo}
          onExtrair={(f) => executar(f)}
          onErroValidacao={setErro}
        />
      )}

      {erro && (
        <div
          role="alert"
          className="mt-4 bg-red-100 dark:bg-red-950/40 text-red-700 dark:text-red-300 text-sm rounded-lg p-3"
        >
          {erro}
        </div>
      )}

      {extraindo && (
        <p className="text-xs text-slate-500 mt-3">
          Não feche esta aba. Relatórios grandes podem levar alguns minutos.
        </p>
      )}
    </>
  )
}

// =============================================================================
// Sub-formulários por tipo
// =============================================================================

type PropsForm<T> = {
  extraindo: boolean
  onExtrair: (payload: T) => void
  onErroValidacao?: (msg: string) => void
}

/** Sem filtros — só botão. */
function FormNenhum({
  extraindo,
  onExtrair,
}: {
  extraindo: boolean
  onExtrair: () => void
}) {
  return (
    <div>
      <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
        Este relatório não requer filtros. Clique abaixo para gerar o CSV.
      </p>
      <BotaoExtrair extraindo={extraindo} onClick={onExtrair} />
    </div>
  )
}

/** Data inicial + final. */
function FormPeriodo({
  extraindo,
  onExtrair,
  onErroValidacao,
}: PropsForm<{ data_inicio: string; data_fim: string }>) {
  const [dataInicio, setDataInicio] = useState('')
  const [dataFim, setDataFim] = useState('')

  const submeter = (e: FormEvent) => {
    e.preventDefault()
    if (!dataInicio || !dataFim) {
      onErroValidacao?.('Informe a data inicial e final.')
      return
    }
    if (dataInicio > dataFim) {
      onErroValidacao?.('Data inicial não pode ser maior que data final.')
      return
    }
    onExtrair({ data_inicio: dataInicio, data_fim: dataFim })
  }

  return (
    <form onSubmit={submeter} className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <CampoData id="data_inicio" label="Data inicial"
          value={dataInicio} onChange={setDataInicio} disabled={extraindo} />
        <CampoData id="data_fim" label="Data final"
          value={dataFim} onChange={setDataFim} disabled={extraindo} />
      </div>
      <BotaoExtrair extraindo={extraindo} type="submit" />
    </form>
  )
}

/** Filial + data inicial + final. */
function FormFilialPeriodo({
  extraindo,
  onExtrair,
  onErroValidacao,
}: PropsForm<{ filial: string; data_inicio: string; data_fim: string }>) {
  const [filial, setFilial] = useState('')
  const [dataInicio, setDataInicio] = useState('')
  const [dataFim, setDataFim] = useState('')

  const submeter = (e: FormEvent) => {
    e.preventDefault()
    const filialLimpa = filial.trim()
    if (!filialLimpa) {
      onErroValidacao?.('Informe a filial.')
      return
    }
    if (!dataInicio || !dataFim) {
      onErroValidacao?.('Informe a data inicial e final.')
      return
    }
    if (dataInicio > dataFim) {
      onErroValidacao?.('Data inicial não pode ser maior que data final.')
      return
    }
    onExtrair({
      filial: filialLimpa,
      data_inicio: dataInicio,
      data_fim: dataFim,
    })
  }

  return (
    <form onSubmit={submeter} className="space-y-4">
      <div>
        <label htmlFor="filial" className="block text-sm font-medium mb-1">
          Filial
        </label>
        <input
          id="filial"
          type="text"
          placeholder="Ex.: 0101001"
          value={filial}
          onChange={(e) => setFilial(e.target.value)}
          disabled={extraindo}
          className="w-full md:w-60 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 outline-none focus:ring-2 focus:ring-slate-400 disabled:opacity-50 font-mono"
        />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <CampoData id="data_inicio" label="Data inicial"
          value={dataInicio} onChange={setDataInicio} disabled={extraindo} />
        <CampoData id="data_fim" label="Data final"
          value={dataFim} onChange={setDataFim} disabled={extraindo} />
      </div>
      <BotaoExtrair extraindo={extraindo} type="submit" />
    </form>
  )
}

// =============================================================================
// Átomos de UI
// =============================================================================

function CampoData({
  id, label, value, onChange, disabled,
}: {
  id: string
  label: string
  value: string
  onChange: (v: string) => void
  disabled: boolean
}) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium mb-1">
        {label}
      </label>
      <input
        id={id}
        type="date"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 outline-none focus:ring-2 focus:ring-slate-400 disabled:opacity-50"
      />
    </div>
  )
}

function BotaoExtrair({
  extraindo,
  type = 'button',
  onClick,
}: {
  extraindo: boolean
  type?: 'button' | 'submit'
  onClick?: () => void
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={extraindo}
      className="w-full md:w-auto px-6 bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 rounded-lg py-2 font-medium disabled:opacity-50"
    >
      {extraindo ? 'Extraindo (pode levar alguns minutos)...' : 'Extrair CSV'}
    </button>
  )
}
