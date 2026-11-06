import { Search, Bell, LogOut } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/useAuth';

export default function Header() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <header className="h-16 border-b border-slate-100 bg-white flex items-center justify-between px-8 sticky top-0 z-10">
      {/* Search Input */}
      <div className="relative w-96">
        <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <input
          type="text"
          placeholder="Buscar documentos..."
          className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-12 py-1.5 text-sm outline-none focus:border-indigo-500 focus:bg-white transition-all text-slate-700 placeholder:text-slate-400"
        />
        <kbd className="absolute right-3 top-1/2 -translate-y-1/2 bg-white border border-slate-200 rounded px-1.5 text-[10px] font-mono text-slate-400 shadow-sm">
          ⌘ K
        </kbd>
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-4">
        <button className="p-2 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-50 transition-colors relative">
          <Bell className="w-5 h-5" />
          <span className="w-2 h-2 bg-indigo-600 rounded-full absolute top-2 right-2 border-2 border-white" />
        </button>

        <div className="h-6 w-px bg-slate-200" />

        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-indigo-100 text-indigo-700 font-semibold text-xs flex items-center justify-center">
            {user?.login?.slice(0, 2).toUpperCase() || 'U'}
          </div>
          <div className="text-left">
            <p className="text-xs font-bold text-slate-800">{user?.login || 'Usuário'}</p>
            <p className="text-[10px] text-slate-400">{user?.perfil || 'Conta'}</p>
          </div>
          <button
            aria-label="Sair da conta"
            className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-50 hover:text-slate-700"
            onClick={() => {
              logout();
              navigate('/login', { replace: true });
            }}
            title="Sair"
            type="button"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </header>
  );
}