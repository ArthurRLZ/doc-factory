// Distribuição por setor (GET /painel → por_setor).
const CORES = ['bg-indigo-600', 'bg-indigo-500', 'bg-emerald-500', 'bg-amber-500', 'bg-sky-500', 'bg-rose-400'];

export default function SectorDistribution({ setores = [] }) {
  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex flex-col justify-between">
      <div>
        <h4 className="font-bold text-slate-800 text-sm">Por setor</h4>
        <p className="text-xs text-slate-400 mb-6">Distribuição dos documentos ativos</p>
        {setores.length === 0 ? <p className="text-xs text-slate-500">Sem documentos.</p> :
          <div className="space-y-4">
            {setores.map((sec, i) => (
              <div key={sec.setor}>
                <div className="flex justify-between text-xs font-semibold mb-1">
                  <span className="text-slate-600">{sec.setor}</span>
                  <span className="text-slate-900">{sec.total}</span>
                </div>
                <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                  <div style={{ width: `${sec.percentual}%` }} className={`h-full ${CORES[i % CORES.length]} rounded-full`} />
                </div>
              </div>
            ))}
          </div>}
      </div>
    </div>
  );
}
