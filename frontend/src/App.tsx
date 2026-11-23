import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { RedirectIfAuth, RequireAuth } from './auth/RequireAuth'
import { RequireAdmin } from './auth/RequireAdmin'
import { AppLayout } from './components/AppLayout'
import Login from './pages/Login'
import Menu from './pages/Menu'
import NotFound from './pages/NotFound'
import CodigoSql from './pages/CodigoSql'
import Jobs from './pages/Jobs'
import Agendamentos from './pages/Agendamentos'
import AgendamentoForm from './pages/AgendamentoForm'
import AgendamentoDetalhe from './pages/AgendamentoDetalhe'
import RelatorioGenerico from './pages/relatorios/RelatorioGenerico'
import Admin from './pages/admin/Admin'
import Usuarios from './pages/admin/Usuarios'
import UsuarioEditar from './pages/admin/UsuarioEditar'
import Areas from './pages/admin/Areas'
import Logs from './pages/admin/Logs'

/**
 * Login e 404 não usam o AppLayout (não têm sidebar).
 * Tudo mais fica envolvido em <AppLayout> via um pequeno wrapper.
 */
function Protegida({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <AppLayout>{children}</AppLayout>
    </RequireAuth>
  )
}

function Admin_({ children }: { children: React.ReactNode }) {
  return (
    <RequireAdmin>
      <AppLayout>{children}</AppLayout>
    </RequireAdmin>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route
            path="/login"
            element={
              <RedirectIfAuth>
                <Login />
              </RedirectIfAuth>
            }
          />
          <Route path="/menu" element={<Protegida><Menu /></Protegida>} />
          <Route
            path="/relatorios/:id"
            element={<Protegida><RelatorioGenerico /></Protegida>}
          />
          <Route path="/sql" element={<Protegida><CodigoSql /></Protegida>} />
          <Route path="/jobs" element={<Protegida><Jobs /></Protegida>} />
          <Route path="/agendamentos" element={<Protegida><Agendamentos /></Protegida>} />
          <Route path="/agendamentos/novo" element={<Protegida><AgendamentoForm /></Protegida>} />
          <Route path="/agendamentos/:id" element={<Protegida><AgendamentoDetalhe /></Protegida>} />
          <Route path="/agendamentos/:id/editar" element={<Protegida><AgendamentoForm /></Protegida>} />
          <Route path="/admin" element={<Admin_><Admin /></Admin_>} />
          <Route path="/admin/usuarios" element={<Admin_><Usuarios /></Admin_>} />
          <Route path="/admin/usuarios/:id" element={<Admin_><UsuarioEditar /></Admin_>} />
          <Route path="/admin/areas" element={<Admin_><Areas /></Admin_>} />
          <Route path="/admin/logs" element={<Admin_><Logs /></Admin_>} />
          {/* Qualquer URL desconhecida — página 404 dedicada (em vez de
              redirecionar silenciosamente). O usuário vê o erro e pode
              voltar/ir pro menu. */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
