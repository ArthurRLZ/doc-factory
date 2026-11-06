import { ChevronRight } from 'lucide-react';

export default function SectorVolume() {
  const sectors = [
    { name: 'Jurídico', count: '1.284', width: '90%', color: 'bg-indigo-950' },
    { name: 'Financeiro', count: '1.102', width: '75%', color: 'bg-indigo-500' },
    { name: 'Operações', count: '876', width: '60%', color: 'bg-emerald-500' },
    { name: 'Recursos Humanos', count: '580', width: '40%', color: 'bg-amber-500' },
  ];

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex flex-col justify-between">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h4 className="font-bold text-slate-800 text-sm">Documentos por setor</h4>
          <p className="text-xs text-slate-400">Volume processado e participação no total</p>
        </div>
        <button className="flex items-center text-xs font-semibold text-indigo-600 hover:text-indigo-800">
          <span>Ver detalhes</span>
          <ChevronRight className="w-3.5 h-3.5 ml-0.5" />
        </button>
      </div>

      <div className="space-y-4">
        {sectors.map((s) => (
          <div key={s.name} className="flex items-center justify-between gap-4">
            <span className="w-32 text-xs font-semibold text-slate-600">{s.name}</span>
            <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
              <div style={{ width: s.width }} className={`h-full ${s.color} rounded-full`} />
            </div>
            <span className="w-12 text-right text-xs font-bold text-slate-800">{s.count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}