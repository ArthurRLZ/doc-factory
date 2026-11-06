import { LayoutDashboard, FileText, ListOrdered, BarChart2, Settings, ChevronRight } from 'lucide-react';

export default function Sidebar() {
  const menuItems = [
    { icon: LayoutDashboard, label: 'Visão geral', active: true },
    { icon: FileText, label: 'Documentos' },
    { icon: ListOrdered, label: 'Fila de revisão', badge: 5 },
    { icon: BarChart2, label: 'Relatórios' },
  ];

  return (
    <aside className="w-64 bg-white border-r border-slate-100 flex flex-col justify-between h-screen p-5 fixed left-0 top-0">
      <div>
        {/* Logo */}
        <div className="flex items-center gap-2 mb-8 px-2">
          <div className="w-7 h-7 bg-indigo-600 rounded-lg flex items-center justify-center text-white font-bold text-sm">
            ilı
          </div>
          <span className="text-xl font-bold text-slate-800 tracking-tight">prioriza</span>
        </div>

        {/* Menu Navigation */}
        <div className="space-y-6">
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3 px-2">Menu</p>
            <nav className="space-y-1">
              {menuItems.map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.label}
                    className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${
                      item.active
                        ? 'bg-indigo-50 text-indigo-700'
                        : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <Icon className="w-5 h-5" />
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
              <button className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition-colors">
                <Settings className="w-5 h-5" />
                <span>Configurações</span>
              </button>
            </nav>
          </div>
        </div>
      </div>

      {/* Footer / User Profile Card */}
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
              MC
            </div>
            <div>
              <p className="text-xs font-bold text-slate-800">Marina Costa</p>
              <p className="text-[11px] text-slate-400">Empresa Aster</p>
            </div>
          </div>
          <ChevronRight className="w-4 h-4 text-slate-400" />
        </div>
      </div>
    </aside>
  );
}