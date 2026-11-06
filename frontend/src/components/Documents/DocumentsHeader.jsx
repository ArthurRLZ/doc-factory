import { Upload } from 'lucide-react';

export default function DocumentsHeader() {
  return (
    <div className="flex items-center justify-between">
      <div>
        <div className="flex items-center gap-2 text-xs text-slate-400 font-medium mb-1">
          <span>Início</span>
          <span>/</span>
          <span className="text-slate-600">Documentos</span>
        </div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Documentos</h1>
        <p className="text-xs text-slate-500 mt-1">
          Acompanhe os documentos que precisam da sua atenção.
        </p>
      </div>

      <button className="flex items-center gap-2 bg-indigo-950 hover:bg-indigo-900 text-white text-xs font-semibold px-4 py-2.5 rounded-xl shadow-sm transition-colors">
        <Upload className="w-4 h-4" />
        <span>Enviar documentos</span>
      </button>
    </div>
  );
}