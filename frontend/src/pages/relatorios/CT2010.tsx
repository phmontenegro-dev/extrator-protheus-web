import { FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { extrairCT2010 } from '../../api/relatorios'
import { mensagemErro } from '../../api/client'

export default function CT2010() {
  const navigate = useNavigate()
  const [dataInicio, setDataInicio] = useState('')
  const [dataFim, setDataFim] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const [extraindo, setExtraindo] = useState(false)

  const submeter = async (e: FormEvent) => {
    e.preventDefault()
    if (!dataInicio || !dataFim) {
      setErro('Informe a data inicial e final.')
      return
    }
    if (dataInicio > dataFim) {
      setErro('Data inicial não pode ser maior que data final.')
      return
    }
    setErro(null)
    setExtraindo(true)
    try {
      await extrairCT2010(dataInicio, dataFim)
      // O download foi disparado pelo navegador. Nada a fazer na tela.
    } catch (e) {
      setErro(mensagemErro(e, 'Falha ao extrair o relatório.'))
    } finally {
      setExtraindo(false)
    }
  }

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
          <h1 className="text-lg font-semibold">CT2010 — Lançamentos Contábeis</h1>
          <span className="w-16" />
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-10">
        <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-lg p-8">
          <p className="text-sm text-slate-500 dark:text-slate-400 mb-6">
            Lançamentos contábeis do período, com partida dobrada, PROCV de
            Plano de Contas e Centro de Custo, e NF origem via CV3.
          </p>

          <form onSubmit={submeter} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label htmlFor="data_inicio" className="block text-sm font-medium mb-1">
                  Data inicial
                </label>
                <input
                  id="data_inicio"
                  type="date"
                  value={dataInicio}
                  onChange={(e) => setDataInicio(e.target.value)}
                  disabled={extraindo}
                  className="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 outline-none focus:ring-2 focus:ring-slate-400 disabled:opacity-50"
                />
              </div>
              <div>
                <label htmlFor="data_fim" className="block text-sm font-medium mb-1">
                  Data final
                </label>
                <input
                  id="data_fim"
                  type="date"
                  value={dataFim}
                  onChange={(e) => setDataFim(e.target.value)}
                  disabled={extraindo}
                  className="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 outline-none focus:ring-2 focus:ring-slate-400 disabled:opacity-50"
                />
              </div>
            </div>

            {erro && (
              <div
                role="alert"
                className="bg-red-100 dark:bg-red-950/40 text-red-700 dark:text-red-300 text-sm rounded-lg p-3"
              >
                {erro}
              </div>
            )}

            <div className="pt-2">
              <button
                type="submit"
                disabled={extraindo}
                className="w-full md:w-auto px-6 bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 rounded-lg py-2 font-medium disabled:opacity-50"
              >
                {extraindo ? 'Extraindo (pode levar alguns minutos)...' : 'Extrair CSV'}
              </button>
              {extraindo && (
                <p className="text-xs text-slate-500 mt-2">
                  Não feche esta aba. Relatórios com muitos lançamentos podem demorar.
                </p>
              )}
            </div>
          </form>
        </div>
      </main>
    </div>
  )
}
