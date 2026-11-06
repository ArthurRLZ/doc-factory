import { FileText, Sparkles } from 'lucide-react';

export default function DocumentsTable() {
  const documents = [
    {
      id: 'DOC-2026-04521',
      name: 'Notificação 4521',
      type: 'Notificação judicial',
      sector: 'Jurídico',
      date: '08 Nov, 2026',
      subdate: 'Vence em 2 dias',
      priority: 'Alta',
    },
    {
      id: 'DOC-2026-01984',
      name: 'Laudo técnico 77',
      type: 'Laudo',
      sector: 'Operações',
      date: '12 Nov, 2026',
      subdate: 'Vence em 6 dias',
      priority: 'Alta',
    },
    {
      id: 'DOC-2026-09823',
      name: 'NF 98231',
      type: 'Nota fiscal',
      sector: 'Financeiro',
      date: '15 Nov, 2026',
      subdate: 'Vence em 9 dias',
      priority: 'Média',
    },
    {
      id: 'DOC-2026-00712',
      name: 'Contrato Fornecedor X',
      type: 'Contrato',
      sector: 'Jurídico',
      date: '30 Nov, 2026',
      subdate: 'Vence em 24 dias',
      priority: 'Média',
    },
    {
      id: 'DOC-2026-00349',
      name: 'Atestado Maria S.',
      type: 'Atestado',
      sector: 'RH',
      date: '20 Dez, 2026',
      subdate: 'No prazo',
      priority: 'Baixa',
    },
    {
      id: 'DOC-2026-00187',
      name: 'Apólice patrimonial',
      type: 'Apólice',
      sector: 'Financeiro',
      date: '14 Jan, 2027',
      subdate: 'No prazo',
      priority: 'Baixa',
    },
  ];

  const getPriorityStyle = (priority) => {
    switch (priority) {
      case 'Alta':
        return 'bg-rose-50 text-rose-600 border-rose-100';
      case 'Média':
        return 'bg-amber-50 text-amber-600 border-amber-100';
      case 'Baixa':
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
                <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full font-semibold border ${getPriorityStyle(doc.priority)} text-[11px]`}>
                  <span className="w-1.5 h-1.5 rounded-full bg-current" />
                  {doc.priority}
                </span>
              </td>

              {/* Documento */}
              <td className="py-3.5 px-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-slate-100 rounded-lg text-slate-500">
                    <FileText className="w-4 h-4" />
                  </div>
                  <div>
                    <p className="font-bold text-slate-800">{doc.name}</p>
                    <p className="text-[10px] text-slate-400 font-mono">{doc.id}</p>
                  </div>
                </div>
              </td>

              {/* Tipo */}
              <td className="py-3.5 px-4">
                <span className="bg-slate-100 text-slate-600 px-2.5 py-1 rounded-md text-[11px] font-medium">
                  {doc.type}
                </span>
              </td>

              {/* Setor */}
              <td className="py-3.5 px-4 text-slate-600 font-medium">
                {doc.sector}
              </td>

              {/* Prazo */}
              <td className="py-3.5 px-4">
                <p className={`font-semibold ${doc.priority === 'Alta' ? 'text-rose-600' : 'text-slate-800'}`}>
                  {doc.date}
                </p>
                <p className="text-[10px] text-slate-400">{doc.subdate}</p>
              </td>

              {/* Ação */}
              <td className="py-3.5 px-4 text-right">
                <button className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 border border-slate-200 rounded-xl px-3 py-1.5 hover:bg-slate-50 hover:text-slate-900 transition-colors">
                  <Sparkles className="w-3.5 h-3.5 text-slate-400" />
                  <span>Ver mais</span>
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}