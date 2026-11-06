// Últimos documentos processados (GET /painel → recentes).
import { FileText } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { dataHora } from '../utils/formatar';

const PRIORIDADE = {
  alta: ['Alta', 'bg-rose-50 text-rose-600 border border-rose-100'],
  media: ['Média', 'bg-amber-50 text-amber-600 border border-amber-100'],
  baixa: ['Baixa', 'bg-emerald-50 text-emerald-600 border border-emerald-100'],
};

export default function RecentDocuments({ documentos = [] }) {
  const navigate = useNavigate();
  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h4 className="font-bold text-slate-800 text-sm">Documentos recentes</h4>
          <p className="text-xs text-slate-400">Últimos itens processados pela plataforma</p>
        </div>
        <button type="button" onClick={() => navigate('/documentos')} className="text-xs font-semibold text-indigo-600 hover:text-indigo-800">Ver documentos</button>
      </div>

      {documentos.length === 0 ? <p className="text-xs text-slate-500">Nenhum documento ainda.</p> :
        <div className="space-y-3">
          {documentos.map((doc) => {
            const [rotulo, cor] = PRIORIDADE[doc.prioridade] || PRIORIDADE.media;
            return (
              <div key={doc.id} className="flex items-center justify-between p-3 rounded-xl border border-slate-50 hover:bg-slate-50 transition-colors">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="p-2.5 bg-slate-100 rounded-lg text-slate-500"><FileText className="w-4 h-4" aria-hidden="true" /></div>
                  <div className="min-w-0">
                    <p className="text-xs font-bold text-slate-800 truncate">{doc.titulo || doc.tipo_nome}</p>
                    <p className="text-[11px] text-slate-400">{doc.tipo_nome} — {doc.setor}{doc.origem_texto ? ` · ${doc.origem_texto}` : ''}</p>
                  </div>
                </div>
                <div className="flex items-center gap-4 shrink-0">
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${cor}`}>{rotulo}</span>
                  <span className="text-[11px] text-slate-400 w-24 text-right">{dataHora(doc.criado_em)}</span>
                </div>
              </div>
            );
          })}
        </div>}
    </div>
  );
}
