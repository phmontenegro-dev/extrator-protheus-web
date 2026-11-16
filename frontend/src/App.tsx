import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { RedirectIfAuth, RequireAuth } from './auth/RequireAuth'
import { RequireAdmin } from './auth/RequireAdmin'
import Login from './pages/Login'
import Menu from './pages/Menu'
import RelatorioGenerico from './pages/relatorios/RelatorioGenerico'
import Admin from './pages/admin/Admin'
import Usuarios from './pages/admin/Usuarios'
import UsuarioEditar from './pages/admin/UsuarioEditar'
import Logs from './pages/admin/Logs'

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
          <Route
            path="/menu"
            element={
              <RequireAuth>
                <Menu />
              </RequireAuth>
            }
          />
          {/* Rota única para TODOS os relatórios — o :id carrega a metadata
              do registry e a página renderiza o formulário certo pelo tipo
              de filtro. Vale para ct2010, qpr010, sft010, sd3010 e Suzano. */}
          <Route
            path="/relatorios/:id"
            element={
              <RequireAuth>
                <RelatorioGenerico />
              </RequireAuth>
            }
          />

          {/* Rotas administrativas */}
          <Route
            path="/admin"
            element={
              <RequireAdmin>
                <Admin />
              </RequireAdmin>
            }
          />
          <Route
            path="/admin/usuarios"
            element={
              <RequireAdmin>
                <Usuarios />
              </RequireAdmin>
            }
          />
          <Route
            path="/admin/usuarios/:id"
            element={
              <RequireAdmin>
                <UsuarioEditar />
              </RequireAdmin>
            }
          />
          <Route
            path="/admin/logs"
            element={
              <RequireAdmin>
                <Logs />
              </RequireAdmin>
            }
          />

          {/* Qualquer outra rota -> /menu (que decide login vs menu). */}
          <Route path="*" element={<Navigate to="/menu" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
