import { FormEvent, useEffect, useState } from 'react'
import {
  ArrowDown,
  ArrowUp,
  Pencil,
  Plus,
  Trash2,
  X,
} from 'lucide-react'
import { AdminLayout } from './AdminLayout'
import {
  Area,
  atribuirRelatorio,
  criarArea,
  editarArea,
  listarAreas,
  listarAtribuicoes,
  removerArea,
  reordenarAreas,
} from '../../api/areas'
import { listarRelatorios, RelatorioInfo } from '../../api/relatorios'
import { mensagemErro } from '../../api/client'
import { Button } from '../../components/ui/button'
import { Card } from '../../components/ui/card'
import { Input } from '../../components/ui/input'
import { Label } from '../../components/ui/label'
import { Skeleton } from '../../components/ui/skeleton'
import { useToast } from '../../lib/toast'

/**
 * Tela única que cuida de áreas em duas dimensões:
 *   1) Lista de áreas (criar, editar, remover, reordenar)
 *   2) Atribuir cada relatório a uma área (combo por relatório)
 *
 * Uma única tela em vez de duas separadas porque as duas operações
 * acontecem juntas no mesmo fluxo (admin cria uma área, imediatamente
 * quer mover relatórios pra ela).
 */
export default function Areas() {
  const { toast } = useToast()
  const [areas, setAreas] = useState<Area[]>([])
  const [relatorios, setRelatorios] = useState<RelatorioInfo[]>([])
  const [atribuicoes, setAtribuicoes] = useState<Record<string, number | null>>({})
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)
  const [modal, setModal] = useState<{ aberta: boolean; alvo?: Area }>({ aberta: false })

  const recarregar = async () => {
    setCarregando(true)
    setErro(null)
    try {
      const [as, rs, ats] = await Promise.all([
        listarAreas(),
        listarRelatorios(),
        listarAtribuicoes(),
      ])
      setAreas(as)
      setRelatorios(rs)
      const map: Record<string, number | null> = {}
      for (const a of ats) map[a.relatorio_id] = a.area_id
      setAtribuicoes(map)
    } catch (e) {
      setErro(mensagemErro(e, 'Não foi possível carregar.'))
    } finally {
      setCarregando(false)
    }
  }

  useEffect(() => {
    recarregar()
  }, [])

  const subir = async (i: number) => {
    if (i === 0) return
    const nova = [...areas]
    ;[nova[i - 1], nova[i]] = [nova[i], nova[i - 1]]
    setAreas(nova)
    try {
      await reordenarAreas(nova.map((a) => a.id))
    } catch (e) {
      toast({
        title: 'Falha ao reordenar',
        description: mensagemErro(e),
        variant: 'destructive',
      })
      recarregar()
    }
  }

  const descer = async (i: number) => {
    if (i === areas.length - 1) return
    const nova = [...areas]
    ;[nova[i], nova[i + 1]] = [nova[i + 1], nova[i]]
    setAreas(nova)
    try {
      await reordenarAreas(nova.map((a) => a.id))
    } catch (e) {
      toast({
        title: 'Falha ao reordenar',
        description: mensagemErro(e),
        variant: 'destructive',
      })
      recarregar()
    }
  }

  const remover = async (a: Area) => {
    const qtdRel = Object.values(atribuicoes).filter((id) => id === a.id).length
    const msg = qtdRel > 0
      ? `Remover a área "${a.nome}"? ${qtdRel} relatório(s) atribuído(s) vão pra "Outros".`
      : `Remover a área "${a.nome}"?`
    if (!window.confirm(msg)) return

    try {
      await removerArea(a.id)
      toast({ title: 'Área removida', variant: 'success' })
      recarregar()
    } catch (e) {
      toast({
        title: 'Falha ao remover',
        description: mensagemErro(e),
        variant: 'destructive',
      })
    }
  }

  const alterarAtribuicao = async (relId: string, novaAreaId: number | null) => {
    const anterior = atribuicoes[relId] ?? null
    // Otimista
    setAtribuicoes({ ...atribuicoes, [relId]: novaAreaId })
    try {
      await atribuirRelatorio(relId, novaAreaId)
    } catch (e) {
      setAtribuicoes({ ...atribuicoes, [relId]: anterior })
      toast({
        title: 'Falha ao atribuir',
        description: mensagemErro(e),
        variant: 'destructive',
      })
    }
  }

  return (
    <AdminLayout titulo="Áreas" voltarPara="/admin" rotuloVoltar="Painel">
      {/* SEÇÃO 1: Lista de áreas */}
      <section className="mb-10">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-base font-semibold">Lista de áreas</h2>
            <p className="text-sm text-muted-foreground">
              Áreas aparecem no menu nesta ordem. Use as setas pra reordenar.
            </p>
          </div>
          <Button onClick={() => setModal({ aberta: true })}>
            <Plus className="h-4 w-4" />
            Nova área
          </Button>
        </div>

        {carregando && (
          <Card className="p-4 space-y-3">
            {[...Array(3)].map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </Card>
        )}

        {erro && (
          <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {erro}
          </div>
        )}

        {!carregando && !erro && areas.length === 0 && (
          <Card className="p-8 text-center text-muted-foreground">
            Nenhuma área cadastrada. Crie a primeira para começar a organizar o menu.
          </Card>
        )}

        {!carregando && areas.length > 0 && (
          <Card className="overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted text-left text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 w-16">Ordem</th>
                  <th className="px-4 py-3">Nome</th>
                  <th className="px-4 py-3">Descrição</th>
                  <th className="px-4 py-3 w-20 text-center">Relatórios</th>
                  <th className="px-4 py-3 w-40"></th>
                </tr>
              </thead>
              <tbody>
                {areas.map((a, i) => {
                  const qtd = Object.values(atribuicoes).filter((id) => id === a.id).length
                  return (
                    <tr key={a.id} className="border-t border-border">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => subir(i)}
                            disabled={i === 0}
                            className="p-1 rounded hover:bg-accent disabled:opacity-30"
                            aria-label="Subir"
                          >
                            <ArrowUp className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => descer(i)}
                            disabled={i === areas.length - 1}
                            className="p-1 rounded hover:bg-accent disabled:opacity-30"
                            aria-label="Descer"
                          >
                            <ArrowDown className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </td>
                      <td className="px-4 py-3 font-medium">{a.nome}</td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {a.descricao || <span className="opacity-40">—</span>}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className="px-2 py-0.5 rounded bg-primary/15 text-primary text-xs font-semibold">
                          {qtd}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex justify-end gap-1">
                          <button
                            onClick={() => setModal({ aberta: true, alvo: a })}
                            className="p-2 rounded hover:bg-accent text-muted-foreground hover:text-foreground"
                            aria-label="Editar"
                          >
                            <Pencil className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => remover(a)}
                            className="p-2 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive"
                            aria-label="Remover"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </Card>
        )}
      </section>

      {/* SEÇÃO 2: Atribuição de relatórios */}
      {!carregando && areas.length > 0 && (
        <section>
          <div className="mb-3">
            <h2 className="text-base font-semibold">Atribuição de relatórios</h2>
            <p className="text-sm text-muted-foreground">
              Escolha a área de cada relatório. Sem área = aparece em "Outros".
            </p>
          </div>

          <Card className="overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted text-left text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">Relatório</th>
                  <th className="px-4 py-3 w-64">Área</th>
                </tr>
              </thead>
              <tbody>
                {relatorios.map((r) => (
                  <tr key={r.id} className="border-t border-border">
                    <td className="px-4 py-3">
                      <div className="font-medium">{r.nome}</div>
                      <div className="text-xs text-muted-foreground font-mono">{r.id}</div>
                    </td>
                    <td className="px-4 py-3">
                      <select
                        value={atribuicoes[r.id] ?? ''}
                        onChange={(e) =>
                          alterarAtribuicao(
                            r.id,
                            e.target.value === '' ? null : Number(e.target.value),
                          )
                        }
                        className="w-full h-9 rounded-md border border-input bg-surface px-2 text-sm"
                      >
                        <option value="">— Outros —</option>
                        {areas.map((a) => (
                          <option key={a.id} value={a.id}>
                            {a.nome}
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </section>
      )}

      {modal.aberta && (
        <ModalArea
          area={modal.alvo}
          onFechar={() => setModal({ aberta: false })}
          onSalvo={async () => {
            setModal({ aberta: false })
            await recarregar()
          }}
        />
      )}
    </AdminLayout>
  )
}

function ModalArea({
  area,
  onFechar,
  onSalvo,
}: {
  area?: Area
  onFechar: () => void
  onSalvo: () => void
}) {
  const { toast } = useToast()
  const [nome, setNome] = useState(area?.nome ?? '')
  const [descricao, setDescricao] = useState(area?.descricao ?? '')
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const editando = area !== undefined

  const submeter = async (e: FormEvent) => {
    e.preventDefault()
    setErro(null)
    setEnviando(true)
    try {
      if (editando) {
        await editarArea(area.id, {
          nome: nome.trim(),
          descricao: descricao.trim() || null,
        })
        toast({ title: 'Área atualizada', variant: 'success' })
      } else {
        await criarArea({
          nome: nome.trim(),
          descricao: descricao.trim() || null,
        })
        toast({ title: 'Área criada', variant: 'success' })
      }
      onSalvo()
    } catch (e) {
      setErro(mensagemErro(e, 'Não foi possível salvar.'))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50"
      onClick={onFechar}
    >
      <Card className="w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">
            {editando ? 'Editar área' : 'Nova área'}
          </h2>
          <button
            onClick={onFechar}
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={submeter} className="space-y-3">
          <div className="space-y-2">
            <Label htmlFor="a-nome">Nome</Label>
            <Input
              id="a-nome"
              value={nome}
              onChange={(e) => setNome(e.target.value)}
              placeholder="Ex: Contábil"
              required
              autoFocus
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="a-desc">
              Descrição <span className="text-muted-foreground text-xs">(opcional)</span>
            </Label>
            <Input
              id="a-desc"
              value={descricao}
              onChange={(e) => setDescricao(e.target.value)}
              placeholder="Ex: Lançamentos e relatórios contábeis"
            />
          </div>

          {erro && (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {erro}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onFechar}>
              Cancelar
            </Button>
            <Button type="submit" disabled={enviando}>
              {enviando ? 'Salvando...' : editando ? 'Salvar' : 'Criar'}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  )
}
