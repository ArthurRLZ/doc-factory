import { CheckCircle2, Clock, AlertTriangle } from 'lucide-react';

export default function StatusPrazos() {
  const statuses = [
    {
      icon: CheckCircle2,
      iconBg: 'bg-emerald-50 text-emerald-600',
      title: '142',
      subtitle: 'No prazo',
      percentage: '87%',
      badgeBg: 'text-emerald-700',
    },
    {
      icon: Clock,
      iconBg: 'bg-amber-50 text-amber-600',
      title: '12',
      subtitle: 'Vencem em breve',
      percentage: '7%',
      badgeBg: 'text-amber-700',
    },
    {
      icon: AlertTriangle,
      iconBg: 'bg-rose-50 text-rose-600',
      title: '9',
      subtitle: 'Vencidos',
      percentage: '6%',
      badgeBg: 'text-rose-700',
    },
  ];

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex flex-col justify-between">
      <div>
        <h4 className="font-bold text-slate-800 text-sm">Situação dos prazos</h4>
        <p className="text-xs text-slate-400 mb-4">Resumo dos documentos ativos</p>
      </div>

      <div className="space-y-3">
        {statuses.map((item, idx) => {
          const Icon = item.icon;
          return (
            <div
              key={idx}
              className="flex items-center justify-between p-3.5 rounded-xl border border-slate-50 bg-slate-50/50 hover:bg-slate-50 transition-colors"
            >
              <div className="flex items-center gap-3">
                <div className={`p-2.5 rounded-lg ${item.iconBg}`}>
                  <Icon className="w-4 h-4" />
                </div>
                <div>
                  <p className="text-sm font-extrabold text-slate-800">{item.title}</p>
                  <p className="text-[11px] text-slate-400 font-medium">{item.subtitle}</p>
                </div>
              </div>
              <span className={`text-xs font-bold ${item.badgeBg}`}>{item.percentage}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}