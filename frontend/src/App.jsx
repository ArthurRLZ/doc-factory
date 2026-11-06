import { BrowserRouter as Router, Navigate, Outlet, Route, Routes } from 'react-router-dom';
import AuthPage from './pages/Auth/AuthPage';
import Home from './pages/Home/Home';
import Documents from './pages/Documents/Documents';
import Reports from './pages/Reports/Reports';
import FilaRevisao from './pages/FilaRevisao/FilaRevisao';
import Trabalhadores from './pages/Trabalhadores/Trabalhadores';
import Vencimentos from './pages/Vencimentos/Vencimentos';
import Automacao from './pages/Automacao/Automacao';
import Alertas from './pages/Alertas/Alertas';
import Regras from './pages/Regras/Regras';
import Fornecedores from './pages/Fornecedores/Fornecedores';
import PortalFornecedor from './pages/Portal/PortalFornecedor';
import { AuthProvider } from './context/AuthContext';
import { useAuth } from './context/useAuth';

function RequireAuth() {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="flex min-h-screen items-center justify-center bg-slate-50 text-sm text-slate-500">Verificando sessão...</div>;
  }

  return user ? <Outlet /> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <Router>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<AuthPage />} />
          <Route path="/cadastro" element={<AuthPage />} />
          {/* público: o fornecedor entra só com o link (o token é a autenticação), sem menu nem sessão */}
          <Route path="/portal/:token" element={<PortalFornecedor />} />
          <Route element={<RequireAuth />}>
            <Route path="/" element={<Home />} />
            <Route path="/documentos" element={<Documents />} />
            <Route path="/fila-revisao" element={<FilaRevisao />} />
            <Route path="/trabalhadores" element={<Trabalhadores />} />
            <Route path="/vencimentos" element={<Vencimentos />} />
            <Route path="/automacao" element={<Automacao />} />
            <Route path="/alertas" element={<Alertas />} />
            <Route path="/regras" element={<Regras />} />
            <Route path="/portal" element={<Fornecedores />} />
            <Route path="/relatorios" element={<Reports />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </Router>
  );
}
