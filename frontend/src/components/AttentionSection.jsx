import { AlertCircle, Clock, CheckCircle } from 'lucide-react';

export default function AttentionSection() {
  const items = [
    {
      icon: AlertCircle,
      iconBg: 'bg-rose-50 text-rose-500',
      title: '3 documentos vencem hoje',
      subtitle: 'Jurídico e Financeiro',
      action: 'Ver',
    },
    {
      icon: Clock,
      iconBg: 'bg-amber-50 text-amber-500',
      title: 'Revisões pendentes',
      subtitle: '2 documentos de alta prioridade',
      action: 'Revisar',
    },
    {
      icon: CheckCircle,
      iconBg: 'bg-emerald-50 text-emerald-500',
      title: '148 processados hoje',
      subtitle: 'Todos os documentos classificados',
      action: 'Abrir',
    },
  ];

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex flex-col justify-between">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h4 className="font-bold text-slate-800 text-sm">Precisa de atenção</h4>
          <p className="text-xs text-slate-400">Itens prioritários para hoje</p>
        </div>
        <button className="text-xs font-semibold text-indigo-600 hover:text-indigo-800">Ver todos</button>
      </div>

      <div className="space-y-3">
        {items.map((item, index) => {
          const Icon = item.icon;
          return (
            <div key={index} className="flex items-center justify-between p-3 rounded-xl border border-slate-50 bg-slate-50/50 hover:bg-slate-50 transition-colors">
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-lg ${item.iconBg}`}>
                  <Icon className="w-4 h-4" />
                </div>
                <div>
                  <p className="text-xs font-bold text-slate-800">{item.title}</p>
                  <p className="text-[11px] text-slate-400">{item.subtitle}</p>
                </div>
              </div>
              <button className="text-xs font-semibold text-slate-600 hover:text-slate-900">{item.action}</button>
            </div>
          );
        })}
      </div>
    </div>
  );
}