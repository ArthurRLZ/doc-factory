import { FileText } from 'lucide-react';

export default function RecentDocuments() {
  const docs = [
    { title: 'Notificação 4521', type: 'Notificação judicial - Jurídico', priority: 'Alta', time: 'há 4 min' },
    { title: 'Laudo técnico 77', type: 'Laudo - Operações', priority: 'Alta', time: 'há 18 min' },
    { title: 'NF 98231', type: 'Nota fiscal - Financeiro', priority: 'Média', time: 'há 32 min' },
  ];

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h4 className="font-bold text-slate-800 text-sm">Documentos recentes</h4>
          <p className="text-xs text-slate-400">Últimos itens processados pela plataforma</p>
        </div>
        <button className="text-xs font-semibold text-indigo-600 hover:text-indigo-800">Ver documentos</button>
      </div>

      <div className="space-y-3">
        {docs.map((doc, idx) => (
          <div key={idx} className="flex items-center justify-between p-3 rounded-xl border border-slate-50 hover:bg-slate-50 transition-colors">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-slate-100 rounded-lg text-slate-500">
                <FileText className="w-4 h-4" />
              </div>
              <div>
                <p className="text-xs font-bold text-slate-800">{doc.title}</p>
                <p className="text-[11px] text-slate-400">{doc.type}</p>
              </div>
            </div>

            <div className="flex items-center gap-4">
              <span
                className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                  doc.priority === 'Alta' ? 'bg-rose-50 text-rose-600 border border-rose-100' : 'bg-amber-50 text-amber-600 border border-amber-100'
                }`}
              >
                {doc.priority}
              </span>
              <span className="text-[11px] text-slate-400 w-16 text-right">{doc.time}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}