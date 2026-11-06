import { BrowserRouter as Router, Navigate, Outlet, Route, Routes } from 'react-router-dom';
import AuthPage from './pages/Auth/AuthPage';
import Home from './pages/Home/Home';
import Documents from './pages/Documents/Documents';
import ReviewQueue from './pages/ReviewQueue/ReviewQueue';
import Reports from './pages/Reports/Reports';
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
          <Route element={<RequireAuth />}>
            <Route path="/" element={<Home />} />
            <Route path="/documentos" element={<Documents />} />
            <Route path="/fila-revisao" element={<ReviewQueue />} />
            <Route path="/relatorios" element={<Reports />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </Router>
  );
}