const numero = new Intl.NumberFormat('pt-BR');

export default function ChartSection({ volume }) {
  const data = volume?.dias || [];
  const max = Math.max(...data.map((item) => item.total), 1);
  const variacao = volume?.variacao_semana_anterior;

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex flex-col justify-between">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h4 className="font-bold text-slate-800 text-sm">Documentos processados</h4>
          <p className="text-xs text-slate-400">Volume nos últimos 7 dias</p>
        </div>
        <div className="text-right">
          {variacao !== null && variacao !== undefined
            ? <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${variacao >= 0 ? 'text-emerald-600 bg-emerald-50' : 'text-rose-600 bg-rose-50'}`}>{variacao > 0 ? '+' : ''}{numero.format(variacao)}%</span>
            : <span className="text-xs text-slate-400">Sem comparação</span>}
          <p className="text-[10px] text-slate-400 mt-1">vs. semana anterior</p>
        </div>
      </div>

      <div className="relative h-44 flex items-end justify-between gap-3 pt-6 border-b border-slate-100 pb-2">
        {data.map((item) => (
          <div key={item.data} className="flex-1 flex flex-col items-center h-full justify-end group">
            <span className="text-[11px] font-medium text-slate-400 mb-1 opacity-0 group-hover:opacity-100 transition-opacity">
              {numero.format(item.total)}
            </span>
            <div
              style={{ height: `${Math.max((item.total / max) * 100, item.total ? 4 : 0)}%` }}
              className={`w-full rounded-t-md transition-all duration-300 ${
                item.rotulo === 'Hoje' ? 'bg-emerald-500' : 'bg-indigo-600 group-hover:bg-indigo-700'
              }`}
            />
            <span className="text-xs text-slate-400 font-medium mt-2">{item.rotulo}</span>
          </div>
        ))}
        {!data.length && <p className="absolute inset-0 flex items-center justify-center text-sm text-slate-400">Sem documentos no período.</p>}
      </div>
    </div>
  );
}