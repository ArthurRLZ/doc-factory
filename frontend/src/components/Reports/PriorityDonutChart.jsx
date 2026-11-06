export default function PriorityDonutChart() {
  const priorities = [
    { label: 'Alta', count: '986', percentage: '25,7%', color: 'bg-rose-500' },
    { label: 'Média', count: '1.742', percentage: '45,3%', color: 'bg-amber-500' },
    { label: 'Baixa', count: '1.114', percentage: '29,0%', color: 'bg-emerald-500' },
  ];

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex flex-col justify-between">
      <div>
        <h4 className="font-bold text-slate-800 text-sm">Por prioridade</h4>
        <p className="text-xs text-slate-400 mb-6">Distribuição dos documentos</p>
      </div>

      <div className="flex items-center justify-around">
        <div className="relative w-36 h-36 flex items-center justify-center">
          <svg className="w-full h-full -rotate-90" viewBox="0 0 36 36">
            <path
              className="text-slate-100"
              strokeWidth="4"
              stroke="currentColor"
              fill="none"
              d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
            />
            <path
              className="text-emerald-500"
              strokeDasharray="29, 100"
              strokeWidth="4"
              strokeLinecap="round"
              stroke="currentColor"
              fill="none"
              d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
            />
            <path
              className="text-amber-500"
              strokeDasharray="45, 100"
              strokeDashoffset="-29"
              strokeWidth="4"
              strokeLinecap="round"
              stroke="currentColor"
              fill="none"
              d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
            />
            <path
              className="text-rose-500"
              strokeDasharray="26, 100"
              strokeDashoffset="-74"
              strokeWidth="4"
              strokeLinecap="round"
              stroke="currentColor"
              fill="none"
              d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
            />
          </svg>
          <div className="absolute flex flex-col items-center justify-center text-center">
            <span className="text-xl font-extrabold text-slate-800">3.842</span>
            <span className="text-[10px] text-slate-400 font-medium">Total</span>
          </div>
        </div>

        <div className="space-y-3">
          {priorities.map((p) => (
            <div key={p.label} className="flex items-center gap-3 text-xs">
              <span className={`w-2.5 h-2.5 rounded-full ${p.color}`} />
              <div>
                <p className="font-bold text-slate-700">{p.label}</p>
                <p className="text-[10px] text-slate-400">{p.percentage}</p>
              </div>
              <span className="font-bold text-slate-900 ml-2">{p.count}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}