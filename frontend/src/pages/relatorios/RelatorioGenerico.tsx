import { FormEvent, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ChevronLeft } from 'lucide-react'
import {
  FiltrosPayload,
  listarRelatorios,
  RelatorioInfo,
} from '../../api/relatorios'
import { criarJobRelatorio } from '../../api/jobs'
import { mensagemErro } from '../../api/client'
import { Skeleton } from '../../components/ui/skeleton'
import { useToast } from '../../lib/toast'
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
    <div className="mx-auto max-w-3xl px-6 py-8 md:py-10">
      <button
        onClick={() => navigate('/menu')}
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-6"
      >
        <ChevronLeft className="h-4 w-4" />
        <span>Menu</span>
      </button>

      {carregando && (
        <div className="space-y-4">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-48 rounded-lg" />
        </div>
      )}

      {erroCarregamento && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive"
        >
          <p>{erroCarregamento}</p>
          <button
            onClick={() => navigate('/menu')}
            className="text-xs underline mt-3"
          >
            Voltar ao menu
          </button>
        </div>
      )}

      {relatorio && (
        <>
          <div className="mb-6">
            <h1 className="text-2xl font-bold tracking-tight">{relatorio.nome}</h1>
            <p className="text-sm text-muted-foreground mt-2">
              {relatorio.descricao}
            </p>
          </div>
          <div className="rounded-lg border border-border bg-surface shadow-sm p-6 md:p-8">
            <FormularioExtracao relatorio={relatorio} />
          </div>
        </>
      )}
    </div>
  )
}

// =============================================================================
// Formulário — dispatcher que escolhe o form pelo tipo de filtro
// =============================================================================

function FormularioExtracao({ relatorio }: { relatorio: RelatorioInfo }) {
  const { toast } = useToast()
  const navigate = useNavigate()
  const [erro, setErro] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  const executar = async (payload: FiltrosPayload) => {
    setErro(null)
    setEnviando(true)
    try {
      const r = await criarJobRelatorio(relatorio.id, payload)
      toast({
        title: 'Job criado',
        description: 'Acompanhe o progresso em "Meus jobs".',
        variant: 'success',
      })
      // Redireciona pra /jobs destacando o job recém-criado.
      navigate(`/jobs?focus=${encodeURIComponent(r.job_id)}`)
    } catch (e) {
      const msg = mensagemErro(e, 'Falha ao enviar o job.')
      setErro(msg)
      toast({
        title: 'Não foi possível enviar',
        description: msg,
        variant: 'destructive',
      })
      setEnviando(false)
    }
  }

  // "livre" tem UI própria: combo de tabela + colunas dinâmicas + validações
  // específicas. Delegamos tudo pra FormLivre.tsx, que também cuida do
  // próprio estado de envio / erro.
  if (relatorio.filtros === 'livre') {
    return <FormLivre />
  }

  return (
    <>
      {relatorio.filtros === 'nenhum' && (
        <FormNenhum extraindo={enviando} onExtrair={() => executar({})} />
      )}
      {relatorio.filtros === 'periodo' && (
        <FormPeriodo
          extraindo={enviando}
          onExtrair={(f) => executar(f)}
          onErroValidacao={setErro}
        />
      )}
      {relatorio.filtros === 'filial_periodo' && (
        <FormFilialPeriodo
          extraindo={enviando}
          onExtrair={(f) => executar(f)}
          onErroValidacao={setErro}
        />
      )}

      {erro && (
        <div
          role="alert"
          className="mt-4 border border-destructive/30 bg-destructive/10 text-destructive text-sm rounded-lg p-3"
        >
          {erro}
        </div>
      )}

      <p className="text-xs text-muted-foreground mt-3">
        A extração roda em background — pode fechar a aba que o CSV estará esperando em
        <button type="button" className="underline ml-1" onClick={() => navigate('/jobs')}>
          Meus jobs
        </button>.
      </p>
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
      <p className="text-sm text-muted-foreground mb-4">
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
          className="w-full md:w-60 rounded-lg border border-border bg-surface px-3 py-2 outline-none focus:ring-2 focus:ring-ring disabled:opacity-50 font-mono"
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
        className="w-full rounded-lg border border-border bg-surface px-3 py-2 outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
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
      className="w-full md:w-auto px-6 bg-primary text-primary-foreground rounded-lg py-2 font-medium disabled:opacity-50"
    >
      {extraindo ? 'Enviando...' : 'Extrair em background'}
    </button>
  )
}
