const cores = ['bg-indigo-600', 'bg-indigo-500', 'bg-emerald-500', 'bg-amber-500'];
const numero = new Intl.NumberFormat('pt-BR');

export default function SectorDistribution({ sectors = [] }) {
  const max = Math.max(...sectors.map((sector) => sector.total), 1);

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex flex-col justify-between">
      <div>
        <h4 className="font-bold text-slate-800 text-sm">Por setor</h4>
        <p className="text-xs text-slate-400 mb-6">Distribuição dos documentos ativos</p>

        <div className="space-y-4">
          {sectors.map((sec, index) => (
            <div key={sec.setor}>
              <div className="flex justify-between text-xs font-semibold mb-1">
                <span className="text-slate-600">{sec.setor}</span>
                <span className="text-slate-900">{numero.format(sec.total)}</span>
              </div>
              <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                <div style={{ width: `${(sec.total / max) * 100}%` }} className={`h-full ${cores[index % cores.length]} rounded-full`} />
              </div>
            </div>
          ))}
          {!sectors.length && <p className="text-sm text-slate-400">Ainda não há documentos por setor.</p>}
        </div>
      </div>
    </div>
  );
}