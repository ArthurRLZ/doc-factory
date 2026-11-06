const configuracao = [
  { prioridade: 'alta', nome: 'Alta', cor: 'text-rose-500', marcador: 'bg-rose-500' },
  { prioridade: 'media', nome: 'Média', cor: 'text-amber-500', marcador: 'bg-amber-500' },
  { prioridade: 'baixa', nome: 'Baixa', cor: 'text-emerald-500', marcador: 'bg-emerald-500' },
];
const numero = new Intl.NumberFormat('pt-BR');

export default function PriorityDonutChart({ priorities = [] }) {
  const dados = configuracao.map((item) => ({
    ...item,
    ...(priorities.find((prioridade) => prioridade.prioridade === item.prioridade) || { total: 0, percentual: 0 }),
  }));
  const total = dados.reduce((soma, item) => soma + item.total, 0);
  const comOffsets = dados.map((item, index) => ({
    ...item,
    offset: -dados.slice(0, index).reduce((soma, anterior) => soma + anterior.percentual, 0),
  }));

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex flex-col justify-between">
      <div>
        <h4 className="font-bold text-slate-800 text-sm">Por prioridade</h4>
        <p className="text-xs text-slate-400 mb-6">Distribuição dos documentos</p>
      </div>

      <div className="flex items-center justify-around">
        <div className="relative w-36 h-36 flex items-center justify-center">
          <svg className="w-full h-full -rotate-90" viewBox="0 0 36 36" role="img" aria-label="Distribuição por prioridade">
            <circle cx="18" cy="18" r="15.9155" className="text-slate-100" strokeWidth="4" stroke="currentColor" fill="none" />
            {comOffsets.map((item) => {
              if (!item.percentual) return null;
              return (
                <circle
                  key={item.prioridade}
                  cx="18"
                  cy="18"
                  r="15.9155"
                  className={item.cor}
                  strokeDasharray={`${item.percentual} ${100 - item.percentual}`}
                  strokeDashoffset={item.offset}
                  strokeWidth="4"
                  stroke="currentColor"
                  fill="none"
                />
              );
            })}
          </svg>
          <div className="absolute flex flex-col items-center justify-center text-center">
            <span className="text-xl font-extrabold text-slate-800">{numero.format(total)}</span>
            <span className="text-[10px] text-slate-400 font-medium">Total</span>
          </div>
        </div>

        <div className="space-y-3">
          {dados.map((item) => (
            <div key={item.prioridade} className="flex items-center gap-3 text-xs">
              <span className={`w-2.5 h-2.5 rounded-full ${item.marcador}`} />
              <div>
                <p className="font-bold text-slate-700">{item.nome}</p>
                <p className="text-[10px] text-slate-400">{numero.format(item.percentual)}%</p>
              </div>
              <span className="font-bold text-slate-900 ml-2">{numero.format(item.total)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
