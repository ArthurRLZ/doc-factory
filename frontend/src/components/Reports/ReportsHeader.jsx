import { Calendar, Download } from 'lucide-react';

// Período do relatório e exportação (JSON do próprio GET /relatorios, sem dado pessoal).
export default function ReportsHeader({ dias, onDias, dados }) {
  function exportar() {
    const blob = new Blob([JSON.stringify(dados, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `relatorio-${dias}-dias.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="flex items-center justify-between">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Relatórios</h1>
        <p className="text-xs text-slate-500 mt-1">Visão geral do desempenho e do volume de documentos.</p>
      </div>

      <div className="flex items-center gap-3">
        <label className="flex items-center gap-2 bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs font-semibold text-slate-700 shadow-sm">
          <Calendar className="w-3.5 h-3.5 text-slate-400" aria-hidden="true" />
          <span className="sr-only">Período</span>
          <select className="bg-transparent outline-none" value={dias} onChange={e => onDias(Number(e.target.value))}>
            <option value={7}>Últimos 7 dias</option>
            <option value={30}>Últimos 30 dias</option>
            <option value={90}>Últimos 90 dias</option>
          </select>
        </label>
        <button type="button" disabled={!dados} onClick={exportar}
                className="flex items-center gap-2 bg-indigo-950 hover:bg-indigo-900 text-white text-xs font-semibold px-4 py-2 rounded-xl shadow-sm transition-colors disabled:opacity-50">
          <Download className="w-4 h-4" aria-hidden="true" />
          <span>Exportar relatório</span>
        </button>
      </div>
    </div>
  );
}
