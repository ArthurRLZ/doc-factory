import { FileText, CheckSquare, TrendingUp } from 'lucide-react';

export default function DocumentsMetrics() {
  const metrics = [
    {
      title: 'Vencem esta semana',
      value: '12',
      subtext: '↑ 3 desde ontem',
      icon: FileText,
      iconBg: 'bg-rose-50 text-rose-500',
    },
    {
      title: 'Em revisão',
      value: '5',
      subtext: 'Aguardando conferência',
      icon: CheckSquare,
      iconBg: 'bg-amber-50 text-amber-500',
    },
    {
      title: 'Processados hoje',
      value: '148',
      subtext: '↑ 12% esta semana',
      icon: TrendingUp,
      iconBg: 'bg-emerald-50 text-emerald-500',
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {metrics.map((item, index) => {
        const Icon = item.icon;
        return (
          <div key={index} className="bg-white p-5 rounded-2xl border border-slate-100 shadow-sm flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className={`p-3 rounded-xl ${item.iconBg}`}>
                <Icon className="w-6 h-6" />
              </div>
              <div>
                <p className="text-xs font-medium text-slate-400 mb-1">{item.title}</p>
                <h3 className="text-2xl font-extrabold text-slate-900">{item.value}</h3>
              </div>
            </div>
            <span className="text-[11px] text-slate-400 font-medium self-end">{item.subtext}</span>
          </div>
        );
      })}
    </div>
  );
}