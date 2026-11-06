import { FileText } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const prioridades = {
  alta: 'bg-rose-50 text-rose-600 border-rose-100',
  media: 'bg-amber-50 text-amber-600 border-amber-100',
  baixa: 'bg-emerald-50 text-emerald-600 border-emerald-100',
};

export default function RecentDocuments({ documents = [] }) {
  const navigate = useNavigate();

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h4 className="font-bold text-slate-800 text-sm">Documentos recentes</h4>
          <p className="text-xs text-slate-400">Últimos itens processados pela plataforma</p>
        </div>
        <button onClick={() => navigate('/documentos')} className="text-xs font-semibold text-indigo-600 hover:text-indigo-800">Ver documentos</button>
      </div>

      <div className="space-y-3">
        {documents.map((doc) => (
          <div key={doc.id} className="flex items-center justify-between p-3 rounded-xl border border-slate-50 hover:bg-slate-50 transition-colors">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-slate-100 rounded-lg text-slate-500">
                <FileText className="w-4 h-4" />
              </div>
              <div>
                <p className="text-xs font-bold text-slate-800">{doc.titulo || doc.tipo_nome}</p>
                <p className="text-[11px] text-slate-400">{doc.tipo_nome} · {doc.setor}</p>
              </div>
            </div>

            <div className="flex items-center gap-4">
              <span
                className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${prioridades[doc.prioridade] || 'bg-slate-50 text-slate-600 border-slate-100'}`}
              >
                {{ alta: 'Alta', media: 'Média', baixa: 'Baixa' }[doc.prioridade] || doc.prioridade}
              </span>
              <span className="text-[11px] text-slate-400 w-24 text-right">{new Date(doc.criado_em).toLocaleDateString('pt-BR')}</span>
            </div>
            {!documents.length && <p className="text-sm text-slate-400">Ainda não há documentos processados.</p>}
          </div>
        ))}
      </div>
    </div>
  );
}