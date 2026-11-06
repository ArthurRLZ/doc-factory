import { Calendar, Download } from 'lucide-react';

export default function ReportsHeader() {
  return (
    <div className="flex items-center justify-between">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Relatórios</h1>
        <p className="text-xs text-slate-500 mt-1">
          Visão geral do desempenho e do volume de documentos.
        </p>
      </div>

      <div className="flex items-center gap-3">
        <div className="relative">
          <button className="flex items-center gap-2 bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50 transition-colors">
            <Calendar className="w-3.5 h-3.5 text-slate-400" />
            <span>Últimos 30 dias</span>
          </button>
        </div>

        <button className="flex items-center gap-2 bg-indigo-950 hover:bg-indigo-900 text-white text-xs font-semibold px-4 py-2 rounded-xl shadow-sm transition-colors">
          <Download className="w-4 h-4" />
          <span>Exportar relatório</span>
        </button>
      </div>
    </div>
  );
}