// Volume dos últimos 7 dias (GET /painel → volume_7_dias).
import { pct } from '../utils/formatar';

const DIAS = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];

export default function ChartSection({ volume }) {
  const dias = volume?.dias || [];
  const maior = Math.max(1, ...dias.map(d => d.total));
  const variacao = volume?.variacao_semana_anterior;

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex flex-col justify-between">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h4 className="font-bold text-slate-800 text-sm">Documentos processados</h4>
          <p className="text-xs text-slate-400">Volume nos últimos 7 dias · {volume?.total ?? 0} no total</p>
        </div>
        {variacao !== null && variacao !== undefined && <div className="text-right">
          <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${variacao >= 0 ? 'text-emerald-600 bg-emerald-50' : 'text-rose-600 bg-rose-50'}`}>
            {variacao >= 0 ? '+' : ''}{pct(variacao)}
          </span>
          <p className="text-[10px] text-slate-400 mt-1">vs. semana anterior</p>
        </div>}
      </div>

      <div className="h-44 flex items-end justify-between gap-3 pt-6 border-b border-slate-100 pb-2">
        {dias.map((item, i) => {
          const hoje = i === dias.length - 1;
          const rotulo = hoje ? 'Hoje' : DIAS[new Date(`${item.data}T12:00:00`).getDay()];
          return (
            <div key={item.data} className="flex-1 flex flex-col items-center h-full justify-end group" title={`${item.total} documento(s)`}>
              <span className="text-[11px] font-medium text-slate-400 mb-1">{item.total}</span>
              <div style={{ height: `${Math.max(2, (100 * item.total) / maior)}%` }}
                   className={`w-full rounded-t-md transition-all duration-300 ${hoje ? 'bg-emerald-500' : 'bg-indigo-600 group-hover:bg-indigo-700'}`} />
              <span className="text-xs text-slate-400 font-medium mt-2">{rotulo}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
