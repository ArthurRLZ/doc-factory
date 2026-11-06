// Distribuição por prioridade (GET /relatorios → por_prioridade), rosca em SVG.
import { num, pct } from '../../utils/formatar';

const ESTILO = {
  alta: { rotulo: 'Alta', bolinha: 'bg-rose-500', traco: 'text-rose-500' },
  media: { rotulo: 'Média', bolinha: 'bg-amber-500', traco: 'text-amber-500' },
  baixa: { rotulo: 'Baixa', bolinha: 'bg-emerald-500', traco: 'text-emerald-500' },
};
const ARCO = 'M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831';

export default function PriorityDonutChart({ prioridades = [] }) {
  const total = prioridades.reduce((s, p) => s + p.total, 0);
  const partes = prioridades.filter(p => p.total > 0).map(p => ({ ...p, parte: (100 * p.total) / Math.max(total, 1) }));
  const arcos = partes.map((p, i) => ({ ...p, offset: -partes.slice(0, i).reduce((s, x) => s + x.parte, 0) }));

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex flex-col justify-between">
      <div>
        <h4 className="font-bold text-slate-800 text-sm">Por prioridade</h4>
        <p className="text-xs text-slate-400 mb-6">Distribuição dos documentos</p>
      </div>
      <div className="flex items-center justify-around">
        <div className="relative w-36 h-36 flex items-center justify-center">
          <svg className="w-full h-full -rotate-90" viewBox="0 0 36 36" role="img" aria-label="Documentos por prioridade">
            <path className="text-slate-100" strokeWidth="4" stroke="currentColor" fill="none" d={ARCO} />
            {arcos.map(a => <path key={a.prioridade} className={ESTILO[a.prioridade]?.traco} strokeDasharray={`${a.parte}, 100`}
                                  strokeDashoffset={a.offset} strokeWidth="4" stroke="currentColor" fill="none" d={ARCO} />)}
          </svg>
          <div className="absolute flex flex-col items-center justify-center text-center">
            <span className="text-xl font-extrabold text-slate-800">{num(total)}</span>
            <span className="text-[10px] text-slate-400 font-medium">Total</span>
          </div>
        </div>
        <div className="space-y-3">
          {prioridades.map(p => (
            <div key={p.prioridade} className="flex items-center gap-3 text-xs">
              <span className={`w-2.5 h-2.5 rounded-full ${ESTILO[p.prioridade]?.bolinha}`} />
              <div>
                <p className="font-bold text-slate-700">{ESTILO[p.prioridade]?.rotulo || p.prioridade}</p>
                <p className="text-[10px] text-slate-400">{pct(p.percentual)}</p>
              </div>
              <span className="font-bold text-slate-900 ml-2">{num(p.total)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
