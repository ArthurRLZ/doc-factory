export default function SectorDistribution() {
  const sectors = [
    { name: 'Jurídico', count: 48, color: 'bg-indigo-600', width: '80%' },
    { name: 'Financeiro', count: 41, color: 'bg-indigo-500', width: '70%' },
    { name: 'Operações', count: 39, color: 'bg-emerald-500', width: '65%' },
    { name: 'Recursos Humanos', count: 35, color: 'bg-amber-500', width: '58%' },
  ];

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex flex-col justify-between">
      <div>
        <h4 className="font-bold text-slate-800 text-sm">Por setor</h4>
        <p className="text-xs text-slate-400 mb-6">Distribuição dos documentos ativos</p>

        <div className="space-y-4">
          {sectors.map((sec) => (
            <div key={sec.name}>
              <div className="flex justify-between text-xs font-semibold mb-1">
                <span className="text-slate-600">{sec.name}</span>
                <span className="text-slate-900">{sec.count}</span>
              </div>
              <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                <div style={{ width: sec.width }} className={`h-full ${sec.color} rounded-full`} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}