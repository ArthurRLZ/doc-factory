export default function ChartSection() {
  const data = [
    { day: 'Sex', val: 83, height: '52%' },
    { day: 'Sáb', val: 112, height: '70%' },
    { day: 'Dom', val: 97, height: '60%' },
    { day: 'Seg', val: 140, height: '88%' },
    { day: 'Ter', val: 124, height: '78%' },
    { day: 'Qua', val: 158, height: '100%' },
    { day: 'Hoje', val: 130, height: '82%', isCurrent: true },
  ];

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex flex-col justify-between">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h4 className="font-bold text-slate-800 text-sm">Documentos processados</h4>
          <p className="text-xs text-slate-400">Volume nos últimos 7 dias</p>
        </div>
        <div className="text-right">
          <span className="text-xs font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">+12,5%</span>
          <p className="text-[10px] text-slate-400 mt-1">vs. semana anterior</p>
        </div>
      </div>

      <div className="h-44 flex items-end justify-between gap-3 pt-6 border-b border-slate-100 pb-2">
        {data.map((item) => (
          <div key={item.day} className="flex-1 flex flex-col items-center h-full justify-end group">
            <span className="text-[11px] font-medium text-slate-400 mb-1 opacity-0 group-hover:opacity-100 transition-opacity">
              {item.val}
            </span>
            <div
              style={{ height: item.height }}
              className={`w-full rounded-t-md transition-all duration-300 ${
                item.isCurrent ? 'bg-emerald-500' : 'bg-indigo-600 group-hover:bg-indigo-700'
              }`}
            />
            <span className="text-xs text-slate-400 font-medium mt-2">{item.day}</span>
          </div>
        ))}
      </div>
    </div>
  );
}