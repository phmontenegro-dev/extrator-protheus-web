import { FormEvent, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ChevronLeft, Save } from 'lucide-react'
import {
  AgendamentoCriadoResponse,
  AgendamentoPayload,
  AgendamentoResumo,
  criarAgendamento,
  DIAS_SEMANA_LABEL,
  editarAgendamento,
  Frequencia,
  listarAgendamentos,
  PresetDatas,
  PRESETS_LABELS,
} from '../api/agendamentos'
import { listarRelatorios, RelatorioInfo, TipoFiltro } from '../api/relatorios'
import { mensagemErro } from '../api/client'
import { Button } from '../components/ui/button'
import { Card } from '../components/ui/card'
import { Skeleton } from '../components/ui/skeleton'
import { TokenModal } from '../components/TokenModal'
import { useToast } from '../lib/toast'
import { cn } from '../lib/utils'

/**
 * Formulário de criação/edição de agendamento.
 *
 * Rota única atende os dois casos:
 *   - `/agendamentos/novo`        → criação
 *   - `/agendamentos/:id/editar`  → edição (carrega os dados do agendamento)
 *
 * UI adaptativa:
 *   - Após selecionar o relatório, o formulário descobre o tipo de filtros
 *     (`nenhum` | `periodo` | `filial_periodo` | `livre` | `sql`) e mostra
 *     os campos relevantes.
 *   - Preset de datas só aparece se o tipo exige data (periodo / filial_periodo).
 *   - Frequência semanal → checkboxes de dias; mensal → input 1-28.
 */
export default function AgendamentoForm() {
  const navigate = useNavigate()
  const { toast } = useToast()
  const params = useParams<{ id: string }>()
  const idEditando = params.id ? Number(params.id) : null
  const modo = idEditando ? 'editar' : 'criar'

  // ------- estado principal -------
  const [relatorios, setRelatorios] = useState<RelatorioInfo[]>([])
  const [carregandoBase, setCarregandoBase] = useState(true)

  const [nome, setNome] = useState('')
  const [descricao, setDescricao] = useState('')
  const [relatorioId, setRelatorioId] = useState('')
  const [filial, setFilial] = useState('')
  const [sqlTexto, setSqlTexto] = useState('')
  const [preset, setPreset] = useState<PresetDatas | ''>('')
  const [frequencia, setFrequencia] = useState<Frequencia>('diario')
  const [diasSemana, setDiasSemana] = useState<number[]>([1, 2, 3, 4, 5])
  const [diaMes, setDiaMes] = useState<number>(1)
  const [hora, setHora] = useState<number>(8)
  const [minuto, setMinuto] = useState<number>(0)
  const [ativo, setAtivo] = useState(true)
  const [estrategiaNome, setEstrategiaNome] = useState<'padrao' | 'sobrescrever'>('padrao')
  const [retencaoDias, setRetencaoDias] = useState<number>(7)

  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  // Modal token aparece logo após criar
  const [tokenNovoResponse, setTokenNovoResponse] = useState<AgendamentoCriadoResponse | null>(null)

  // Carrega catálogo de relatórios + (se editar) os dados atuais
  useEffect(() => {
    let vivo = true
    Promise.all([
      listarRelatorios(),
      idEditando ? listarAgendamentos() : Promise.resolve([] as AgendamentoResumo[]),
    ])
      .then(([rels, ags]) => {
        if (!vivo) return
        setRelatorios(rels)
        if (idEditando) {
          const ag = ags.find((a) => a.id === idEditando)
          if (!ag) {
            setErro('Agendamento não encontrado.')
            return
          }
          preencherDe(ag)
        }
      })
      .catch((e) => {
        if (vivo) setErro(mensagemErro(e, 'Falha ao carregar.'))
      })
      .finally(() => {
        if (vivo) setCarregandoBase(false)
      })
    return () => {
      vivo = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idEditando])

  function preencherDe(ag: AgendamentoResumo) {
    setNome(ag.nome)
    setDescricao(ag.descricao ?? '')
    setRelatorioId(ag.relatorio_id)
    setFilial((ag.filtros_base?.filial as string | undefined) ?? '')
    setSqlTexto(ag.sql_texto ?? '')
    setPreset(ag.preset_datas ?? '')
    setFrequencia(ag.frequencia)
    setDiasSemana(ag.dias_semana ?? [1, 2, 3, 4, 5])
    setDiaMes(ag.dia_mes ?? 1)
    setHora(ag.hora)
    setMinuto(ag.minuto)
    setAtivo(ag.ativo)
    setEstrategiaNome(ag.estrategia_nome)
    setRetencaoDias(ag.retencao_dias)
  }

  const relSelecionado = useMemo(
    () => relatorios.find((r) => r.id === relatorioId) ?? null,
    [relatorios, relatorioId],
  )

  const tipoFiltro: TipoFiltro | null = relSelecionado?.filtros ?? null
  const precisaDatas = tipoFiltro === 'periodo' || tipoFiltro === 'filial_periodo'
  const precisaFilial = tipoFiltro === 'filial_periodo'
  const precisaSql = tipoFiltro === 'sql'

  // ------- submit -------
  const submeter = async (e: FormEvent) => {
    e.preventDefault()
    setErro(null)

    if (!nome.trim()) return setErro('Dê um nome ao agendamento.')
    if (!relSelecionado) return setErro('Escolha um relatório.')
    if (precisaDatas && !preset) return setErro('Escolha o preset de datas.')
    if (precisaFilial && !filial.trim()) return setErro('Informe a filial.')
    if (precisaSql && !sqlTexto.trim()) return setErro('Cole o SQL a executar.')
    if (frequencia === 'semanal' && diasSemana.length === 0)
      return setErro('Escolha pelo menos 1 dia da semana.')
    if (frequencia === 'mensal' && (!diaMes || diaMes < 1 || diaMes > 28))
      return setErro('Dia do mês deve estar entre 1 e 28.')

    const tipo =
      tipoFiltro === 'livre' ? 'relatorio_livre' :
      tipoFiltro === 'sql'   ? 'codigo_sql' :
      'relatorio_pronto'

    const filtros_base: Record<string, unknown> | null =
      precisaFilial ? { filial: filial.trim() } : null

    const payload: AgendamentoPayload = {
      nome: nome.trim(),
      descricao: descricao.trim() || null,
      tipo,
      relatorio_id: relSelecionado.id,
      filtros_base,
      sql_texto: precisaSql ? sqlTexto : null,
      preset_datas: precisaDatas ? (preset as PresetDatas) : null,
      frequencia,
      dias_semana: frequencia === 'semanal' ? diasSemana : null,
      dia_mes: frequencia === 'mensal' ? diaMes : null,
      hora,
      minuto,
      ativo,
      estrategia_nome: estrategiaNome,
      retencao_dias: retencaoDias,
    }

    setSalvando(true)
    try {
      if (modo === 'criar') {
        const r = await criarAgendamento(payload)
        setTokenNovoResponse(r)
        toast({ title: 'Agendamento criado', variant: 'success' })
        // Não navega agora — espera o usuário fechar o modal do token
      } else {
        await editarAgendamento(idEditando!, payload)
        toast({ title: 'Agendamento atualizado', variant: 'success' })
        navigate(`/agendamentos/${idEditando}`)
      }
    } catch (e) {
      const msg = mensagemErro(e, 'Falha ao salvar.')
      setErro(msg)
      toast({ title: 'Não foi possível salvar', description: msg, variant: 'destructive' })
    } finally {
      setSalvando(false)
    }
  }

  // ------- render -------
  if (carregandoBase) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-8 md:py-10">
        <Skeleton className="h-8 w-48 mb-4" />
        <Skeleton className="h-96 rounded-lg" />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl px-6 py-8 md:py-10">
      <button
        onClick={() => navigate('/agendamentos')}
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-6"
      >
        <ChevronLeft className="h-4 w-4" />
        <span>Agendamentos</span>
      </button>

      <h1 className="text-2xl font-bold tracking-tight mb-1">
        {modo === 'criar' ? 'Novo agendamento' : 'Editar agendamento'}
      </h1>
      <p className="text-sm text-muted-foreground mb-6">
        A execução roda automaticamente no horário programado. O CSV fica disponível
        por {retencaoDias} dias, e o script sincronizador no PC baixa automaticamente.
      </p>

      <Card className="p-6">
        <form onSubmit={submeter} className="space-y-6">
          {/* --- Identificação --- */}
          <div>
            <label className="block text-sm font-medium mb-1">Nome</label>
            <input
              type="text"
              value={nome}
              onChange={(e) => setNome(e.target.value)}
              placeholder="Ex: CT2010 diário 8am"
              className={campoClasse}
              disabled={salvando}
              maxLength={100}
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              Descrição <span className="text-muted-foreground text-xs">(opcional)</span>
            </label>
            <input
              type="text"
              value={descricao}
              onChange={(e) => setDescricao(e.target.value)}
              placeholder="Pra que serve esse agendamento..."
              className={campoClasse}
              disabled={salvando}
              maxLength={500}
            />
          </div>

          {/* --- Relatório --- */}
          <div>
            <label className="block text-sm font-medium mb-1">Relatório</label>
            <select
              value={relatorioId}
              onChange={(e) => setRelatorioId(e.target.value)}
              className={campoClasse}
              disabled={salvando || modo === 'editar'}
            >
              <option value="">Selecione...</option>
              {relatorios.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.nome}
                </option>
              ))}
            </select>
            {modo === 'editar' && (
              <p className="text-xs text-muted-foreground mt-1">
                Pra trocar de relatório, apague este e crie outro.
              </p>
            )}
            {relSelecionado?.descricao && (
              <p className="text-xs text-muted-foreground mt-1">
                {relSelecionado.descricao}
              </p>
            )}
          </div>

          {/* --- Filtros específicos --- */}
          {precisaFilial && (
            <div>
              <label className="block text-sm font-medium mb-1">Filial</label>
              <input
                type="text"
                value={filial}
                onChange={(e) => setFilial(e.target.value)}
                placeholder="Ex: 0101001"
                className={cn(campoClasse, 'font-mono w-full md:w-60')}
                disabled={salvando}
              />
            </div>
          )}

          {precisaSql && (
            <div>
              <label className="block text-sm font-medium mb-1">SQL</label>
              <textarea
                value={sqlTexto}
                onChange={(e) => setSqlTexto(e.target.value)}
                placeholder="SELECT ... FROM ..."
                className={cn(campoClasse, 'font-mono min-h-[180px] resize-y')}
                disabled={salvando}
                maxLength={50000}
              />
              <p className="text-xs text-muted-foreground mt-1">
                SELECT/WITH only. O validador rejeita qualquer DML/DDL.
              </p>
            </div>
          )}

          {precisaDatas && (
            <div>
              <label className="block text-sm font-medium mb-1">Período (preset relativo)</label>
              <select
                value={preset}
                onChange={(e) => setPreset(e.target.value as PresetDatas | '')}
                className={campoClasse}
                disabled={salvando}
              >
                <option value="">Selecione...</option>
                {Object.entries(PRESETS_LABELS).map(([valor, label]) => (
                  <option key={valor} value={valor}>{label}</option>
                ))}
              </select>
              <p className="text-xs text-muted-foreground mt-1">
                As datas são calculadas na hora do disparo. Ex: "Ontem" roda sempre
                com data de ontem, não da data em que foi agendado.
              </p>
            </div>
          )}

          {/* --- Frequência --- */}
          <div>
            <label className="block text-sm font-medium mb-1">Frequência</label>
            <div className="flex gap-2">
              {(['diario', 'semanal', 'mensal'] as const).map((f) => (
                <button
                  key={f}
                  type="button"
                  onClick={() => setFrequencia(f)}
                  disabled={salvando}
                  className={cn(
                    'px-3 py-1.5 rounded-md text-sm border transition-colors',
                    frequencia === f
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border hover:bg-accent',
                  )}
                >
                  {f === 'diario' ? 'Diário' : f === 'semanal' ? 'Semanal' : 'Mensal'}
                </button>
              ))}
            </div>
          </div>

          {frequencia === 'semanal' && (
            <div>
              <label className="block text-sm font-medium mb-1">Dias da semana</label>
              <div className="flex gap-1.5 flex-wrap">
                {DIAS_SEMANA_LABEL.map((lab, i) => {
                  const dia = i + 1
                  const selecionado = diasSemana.includes(dia)
                  return (
                    <button
                      key={dia}
                      type="button"
                      onClick={() =>
                        setDiasSemana(
                          selecionado
                            ? diasSemana.filter((d) => d !== dia)
                            : [...diasSemana, dia].sort(),
                        )
                      }
                      disabled={salvando}
                      className={cn(
                        'w-11 h-9 rounded-md text-xs font-medium border transition-colors',
                        selecionado
                          ? 'border-primary bg-primary text-primary-foreground'
                          : 'border-border hover:bg-accent',
                      )}
                    >
                      {lab}
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          {frequencia === 'mensal' && (
            <div>
              <label className="block text-sm font-medium mb-1">Dia do mês (1-28)</label>
              <input
                type="number"
                min={1}
                max={28}
                value={diaMes}
                onChange={(e) => setDiaMes(Number(e.target.value))}
                className={cn(campoClasse, 'w-28')}
                disabled={salvando}
              />
              <p className="text-xs text-muted-foreground mt-1">
                Limitado a 28 pra funcionar em todos os meses, incluindo fevereiro.
              </p>
            </div>
          )}

          {/* --- Horário --- */}
          <div>
            <label className="block text-sm font-medium mb-1">Horário (America/Sao_Paulo)</label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min={0}
                max={23}
                value={hora}
                onChange={(e) => setHora(Number(e.target.value))}
                className={cn(campoClasse, 'w-20 text-center')}
                disabled={salvando}
              />
              <span className="text-lg font-mono">:</span>
              <input
                type="number"
                min={0}
                max={59}
                value={minuto}
                onChange={(e) => setMinuto(Number(e.target.value))}
                className={cn(campoClasse, 'w-20 text-center')}
                disabled={salvando}
              />
            </div>
          </div>

          {/* --- Avançado --- */}
          <details className="rounded-md border border-border">
            <summary className="cursor-pointer px-3 py-2 text-sm font-medium select-none">
              Opções avançadas
            </summary>
            <div className="px-3 py-3 space-y-4 border-t border-border">
              <div>
                <label className="block text-sm font-medium mb-1">
                  Estratégia de nome de arquivo
                </label>
                <select
                  value={estrategiaNome}
                  onChange={(e) =>
                    setEstrategiaNome(e.target.value as 'padrao' | 'sobrescrever')
                  }
                  className={campoClasse}
                  disabled={salvando}
                >
                  <option value="padrao">
                    Sempre novo arquivo (acumula no destino)
                  </option>
                  <option value="sobrescrever">
                    Mesmo nome sempre (sobrescreve o anterior)
                  </option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">
                  Retenção no servidor (dias)
                </label>
                <input
                  type="number"
                  min={1}
                  max={90}
                  value={retencaoDias}
                  onChange={(e) => setRetencaoDias(Number(e.target.value))}
                  className={cn(campoClasse, 'w-28')}
                  disabled={salvando}
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Passado isso, o CSV é apagado automaticamente — deixe o
                  tempo suficiente pra o script no PC puxar.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="ativo"
                  checked={ativo}
                  onChange={(e) => setAtivo(e.target.checked)}
                  disabled={salvando}
                  className="rounded"
                />
                <label htmlFor="ativo" className="text-sm font-medium cursor-pointer">
                  Ativo (desmarque pra pausar temporariamente)
                </label>
              </div>
            </div>
          </details>

          {/* --- Erro + Submit --- */}
          {erro && (
            <div
              role="alert"
              className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
            >
              {erro}
            </div>
          )}

          <div className="flex items-center gap-2 pt-2">
            <Button type="submit" disabled={salvando}>
              <Save className="h-4 w-4" />
              {salvando ? 'Salvando...' : modo === 'criar' ? 'Criar agendamento' : 'Salvar alterações'}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => navigate('/agendamentos')}
              disabled={salvando}
            >
              Cancelar
            </Button>
          </div>
        </form>
      </Card>

      {/* Modal token — aparece logo após criar */}
      {tokenNovoResponse && (
        <TokenModal
          tokenClaro={tokenNovoResponse.token_claro}
          onFechar={() => {
            const id = tokenNovoResponse.id
            setTokenNovoResponse(null)
            navigate(`/agendamentos/${id}`)
          }}
        />
      )}
    </div>
  )
}

const campoClasse =
  'w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring disabled:opacity-50'
