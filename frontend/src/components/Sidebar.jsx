import { useNavigate, useLocation } from 'react-router-dom';
import { LayoutDashboard, FileText, ListOrdered, BarChart2, Settings, ChevronRight } from 'lucide-react';
import { useAuth } from '../context/useAuth';

export default function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();

  const menuItems = [
    { icon: LayoutDashboard, label: 'Visão geral', path: '/' },
    { icon: FileText, label: 'Documentos', path: '/documentos' },
    { icon: ListOrdered, label: 'Fila de revisão', path: '/fila-revisao', badge: 5 },
    { icon: BarChart2, label: 'Relatórios', path: '/relatorios' },
  ];

  return (
    <aside className="w-64 bg-white border-r border-slate-100 flex flex-col justify-between h-screen p-5 fixed left-0 top-0 z-20">
      <div>
        {/* Logo */}
        <div 
          onClick={() => navigate('/')} 
          className="flex items-center gap-2 mb-8 px-2 cursor-pointer"
        >
          <div className="w-7 h-7 bg-indigo-600 rounded-lg flex items-center justify-center text-white font-bold text-sm">
            ilı
          </div>
          <span className="text-xl font-bold text-slate-800 tracking-tight">prioriza</span>
        </div>

        {/* Navegação do Menu */}
        <div className="space-y-6">
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3 px-2">Menu</p>
            <nav className="space-y-1">
              {menuItems.map((item) => {
                const Icon = item.icon;
                const isActive = location.pathname === item.path;

                return (
                  <button
                    key={item.label}
                    onClick={() => navigate(item.path)}
                    className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-indigo-50 text-indigo-700 font-semibold'
                        : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <Icon className={`w-5 h-5 ${isActive ? 'text-indigo-600' : 'text-slate-500'}`} />
                      <span>{item.label}</span>
                    </div>
                    {item.badge && (
                      <span className="bg-indigo-100 text-indigo-700 text-xs px-2 py-0.5 rounded-full font-semibold">
                        {item.badge}
                      </span>
                    )}
                  </button>
                );
              })}
            </nav>
          </div>

          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3 px-2">Conta</p>
            <nav>
              <button 
                onClick={() => navigate('/configuracoes')}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${
                  location.pathname === '/configuracoes'
                    ? 'bg-indigo-50 text-indigo-700 font-semibold'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                }`}
              >
                <Settings className="w-5 h-5 text-slate-500" />
                <span>Configurações</span>
              </button>
            </nav>
          </div>
        </div>
      </div>

      {/* Cartão de Usuário / Suporte */}
      <div className="space-y-4">
        <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-100 flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center text-slate-600 font-bold text-xs">
            ?
          </div>
          <div className="flex-1">
            <p className="text-xs font-semibold text-slate-800">Precisa de ajuda?</p>
            <p className="text-[11px] text-slate-500">Fale com o suporte</p>
          </div>
        </div>

        <div className="pt-2 border-t border-slate-100 flex items-center justify-between px-1">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-full bg-indigo-100 text-indigo-700 font-bold text-xs flex items-center justify-center">
              {user?.login?.slice(0, 2).toUpperCase() || 'U'}
            </div>
            <div>
              <p className="text-xs font-bold text-slate-800">{user?.login || 'Usuário'}</p>
              <p className="text-[11px] text-slate-400">{user?.perfil || 'Conta'}</p>
            </div>
          </div>
          <ChevronRight className="w-4 h-4 text-slate-400" />
        </div>
      </div>
    </aside>
  );
}