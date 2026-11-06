import { FileText, Sparkles } from 'lucide-react';

const prioridadeNome = { alta: 'Alta', media: 'Média', baixa: 'Baixa' };

function prazoLabel(validade) {
  if (!validade) return '—';
  if (validade.status === 'vencido') return `Vencido há ${Math.abs(validade.dias_restantes)} dias`;
  if (validade.status === 'vencendo') {
    return validade.dias_restantes === 0 ? 'Vence hoje' : `Vence em ${validade.dias_restantes} dias`;
  }
  if (validade.status === 'vigente') return 'No prazo';
  if (validade.status === 'indeterminado') return 'Validade não identificada';
  return 'Sem validade';
}

export default function DocumentsTable({ documents = [], onSelect }) {

  const getPriorityStyle = (priority) => {
    switch (priority) {
      case 'alta':
        return 'bg-rose-50 text-rose-600 border-rose-100';
      case 'media':
        return 'bg-amber-50 text-amber-600 border-amber-100';
      case 'baixa':
        return 'bg-emerald-50 text-emerald-600 border-emerald-100';
      default:
        return 'bg-slate-50 text-slate-600 border-slate-100';
    }
  };

  return (
    <div className="bg-white border border-slate-100 rounded-b-2xl shadow-sm overflow-x-auto">
      <table className="w-full text-left border-collapse">
        <thead>
          <tr className="border-b border-t border-slate-100 text-[10px] font-bold text-slate-400 uppercase tracking-wider bg-slate-50/50">
            <th className="py-3 px-4">Prioridade</th>
            <th className="py-3 px-4">Documento</th>
            <th className="py-3 px-4">Tipo</th>
            <th className="py-3 px-4">Setor</th>
            <th className="py-3 px-4">Prazo</th>
            <th className="py-3 px-4 text-right">Ação</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 text-xs">
          {documents.map((doc) => (
            <tr key={doc.id} className="hover:bg-slate-50/80 transition-colors">
              {/* Prioridade */}
              <td className="py-3.5 px-4">
                <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full font-semibold border ${getPriorityStyle(doc.prioridade)} text-[11px]`}>
                  <span className="w-1.5 h-1.5 rounded-full bg-current" />
                  {prioridadeNome[doc.prioridade] || doc.prioridade}
                </span>
              </td>

              {/* Documento */}
              <td className="py-3.5 px-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-slate-100 rounded-lg text-slate-500">
                    <FileText className="w-4 h-4" />
                  </div>
                  <div>
                    <p className="font-bold text-slate-800">{doc.titulo || doc.tipo_nome}</p>
                    <p className="text-[10px] text-slate-400 font-mono">{doc.codigo || doc.id}</p>
                  </div>
                </div>
              </td>

              {/* Tipo */}
              <td className="py-3.5 px-4">
                <span className="bg-slate-100 text-slate-600 px-2.5 py-1 rounded-md text-[11px] font-medium">
                  {doc.tipo_nome}
                </span>
              </td>

              {/* Setor */}
              <td className="py-3.5 px-4 text-slate-600 font-medium">
                {doc.setor}
              </td>

              {/* Prazo */}
              <td className="py-3.5 px-4">
                <p className={`font-semibold ${doc.prioridade === 'alta' ? 'text-rose-600' : 'text-slate-800'}`}>
                  {doc.validade?.data ? new Date(`${doc.validade.data}T12:00:00`).toLocaleDateString('pt-BR') : '—'}
                </p>
                <p className="text-[10px] text-slate-400">{prazoLabel(doc.validade)}</p>
              </td>

              {/* Ação */}
              <td className="py-3.5 px-4 text-right">
                <button onClick={() => onSelect?.(doc)} className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 border border-slate-200 rounded-xl px-3 py-1.5 hover:bg-slate-50 hover:text-slate-900 transition-colors">
                  <Sparkles className="w-3.5 h-3.5 text-slate-400" />
                  <span>Ver mais</span>
                </button>
              </td>
            </tr>
          ))}
          {!documents.length && <tr><td className="px-4 py-8 text-center text-sm text-slate-400" colSpan="6">Nenhum documento encontrado.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}