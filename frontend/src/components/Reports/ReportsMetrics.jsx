import { FileText, Clock, CheckSquare, Send } from 'lucide-react';

export default function ReportsMetrics() {
  const metrics = [
    {
      title: 'Documentos processados',
      value: '3.842',
      subtext: '↑ 12,5% vs. período anterior',
      icon: FileText,
      iconBg: 'bg-indigo-50 text-indigo-600',
    },
    {
      title: 'Tempo médio de análise',
      value: '1m 42s',
      subtext: '↓ 8,2% mais rápido',
      icon: Clock,
      iconBg: 'bg-purple-50 text-purple-600',
    },
    {
      title: 'Concluídos sem revisão',
      value: '94,8%',
      subtext: '↑ 2,1% vs. período anterior',
      icon: CheckSquare,
      iconBg: 'bg-emerald-50 text-emerald-600',
    },
    {
      title: 'Enviados para revisão',
      value: '198',
      subtext: '↑ 14 documentos',
      icon: Send,
      iconBg: 'bg-amber-50 text-amber-600',
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {metrics.map((item, index) => {
        const Icon = item.icon;
        return (
          <div key={index} className="bg-white p-5 rounded-2xl border border-slate-100 shadow-sm">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-medium text-slate-400 mb-1">{item.title}</p>
                <h3 className="text-2xl font-extrabold text-slate-900">{item.value}</h3>
              </div>
              <div className={`p-2.5 rounded-xl ${item.iconBg}`}>
                <Icon className="w-5 h-5" />
              </div>
            </div>
            <p className="text-[11px] text-emerald-600 font-medium mt-3">{item.subtext}</p>
          </div>
        );
      })}
    </div>
  );
}