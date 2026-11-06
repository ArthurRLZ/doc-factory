// Documentos por setor no período (GET /relatorios → por_setor).
import { num, pct } from '../../utils/formatar';

const CORES = ['bg-indigo-950', 'bg-indigo-500', 'bg-emerald-500', 'bg-amber-500', 'bg-sky-500', 'bg-rose-400'];

export default function SectorVolume({ setores = [] }) {
  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex flex-col justify-between">
      <div className="mb-4">
        <h4 className="font-bold text-slate-800 text-sm">Documentos por setor</h4>
        <p className="text-xs text-slate-400">Volume processado e participação no total</p>
      </div>
      {setores.length === 0 ? <p className="text-xs text-slate-500">Sem documentos no período.</p> :
        <div className="space-y-4">
          {setores.map((s, i) => (
            <div key={s.setor} className="flex items-center justify-between gap-4" title={pct(s.percentual)}>
              <span className="w-40 text-xs font-semibold text-slate-600">{s.setor}</span>
              <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                <div style={{ width: `${s.percentual}%` }} className={`h-full ${CORES[i % CORES.length]} rounded-full`} />
              </div>
              <span className="w-12 text-right text-xs font-bold text-slate-800">{num(s.total)}</span>
            </div>
          ))}
        </div>}
    </div>
  );
}
