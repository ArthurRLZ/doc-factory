import { ChevronRight } from 'lucide-react';

const cores = ['bg-indigo-950', 'bg-indigo-500', 'bg-emerald-500', 'bg-amber-500'];
const numero = new Intl.NumberFormat('pt-BR');

export default function SectorVolume({ sectors = [] }) {
  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex flex-col justify-between">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h4 className="font-bold text-slate-800 text-sm">Documentos por setor</h4>
          <p className="text-xs text-slate-400">Volume processado e participação no total</p>
        </div>
        <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
      </div>

      <div className="space-y-4">
        {sectors.map((sector, index) => (
          <div key={sector.setor} className="flex items-center justify-between gap-4">
            <span className="w-32 text-xs font-semibold text-slate-600">{sector.setor}</span>
            <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
              <div style={{ width: `${sector.percentual}%` }} className={`h-full ${cores[index % cores.length]} rounded-full`} />
            </div>
            <span className="w-12 text-right text-xs font-bold text-slate-800">{numero.format(sector.total)}</span>
          </div>
        ))}
        {!sectors.length && <p className="text-sm text-slate-400">Ainda não há documentos por setor.</p>}
      </div>
    </div>
  );
}
