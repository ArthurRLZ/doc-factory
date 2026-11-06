import { Calendar, Download } from 'lucide-react';

export default function ReportsHeader({ days, onDaysChange, onExport, canExport }) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Relatórios</h1>
        <p className="text-xs text-slate-500 mt-1">
          Visão geral do desempenho e do volume de documentos.
        </p>
      </div>

      <div className="flex items-center gap-3">
        <label className="flex items-center gap-2 bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs font-semibold text-slate-700 shadow-sm">
          <Calendar className="w-3.5 h-3.5 text-slate-400" />
          <span className="sr-only">Período do relatório</span>
          <select aria-label="Período do relatório" className="bg-transparent outline-none" value={days} onChange={(event) => onDaysChange(event.target.value)}>
            <option value="7">Últimos 7 dias</option>
            <option value="30">Últimos 30 dias</option>
            <option value="90">Últimos 90 dias</option>
          </select>
        </label>

        <button onClick={onExport} disabled={!canExport} className="flex items-center gap-2 bg-indigo-950 hover:bg-indigo-900 text-white text-xs font-semibold px-4 py-2 rounded-xl shadow-sm transition-colors disabled:cursor-not-allowed disabled:opacity-50">
          <Download className="w-4 h-4" />
          <span>Exportar relatório</span>
        </button>
      </div>
    </div>
  );
}