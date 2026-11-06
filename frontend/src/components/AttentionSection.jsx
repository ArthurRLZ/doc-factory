// "Precisa de atenção" (GET /painel → atencao), do mais grave ao informativo.
import { AlertCircle, Clock, CheckCircle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { rotaDaTela } from '../utils/formatar';

const ESTILO = {
  alta: { icon: AlertCircle, bg: 'bg-rose-50 text-rose-500' },
  media: { icon: Clock, bg: 'bg-amber-50 text-amber-500' },
  baixa: { icon: CheckCircle, bg: 'bg-emerald-50 text-emerald-500' },
};

export default function AttentionSection({ itens = [] }) {
  const navigate = useNavigate();
  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex flex-col justify-between">
      <div className="mb-4">
        <h4 className="font-bold text-slate-800 text-sm">Precisa de atenção</h4>
        <p className="text-xs text-slate-400">Itens prioritários para hoje</p>
      </div>

      {itens.length === 0 ? <p className="text-xs text-slate-500">Nada pendente agora.</p> :
        <div className="space-y-3">
          {itens.map((item) => {
            const { icon: Icon, bg } = ESTILO[item.gravidade] || ESTILO.baixa;
            return (
              <div key={item.tipo} className="flex items-center justify-between p-3 rounded-xl border border-slate-50 bg-slate-50/50 hover:bg-slate-50 transition-colors">
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg ${bg}`}><Icon className="w-4 h-4" aria-hidden="true" /></div>
                  <div>
                    <p className="text-xs font-bold text-slate-800">{item.titulo}</p>
                    <p className="text-[11px] text-slate-400">{item.subtitulo}</p>
                  </div>
                </div>
                {item.rota && <button type="button" onClick={() => navigate(rotaDaTela(item.rota))}
                                      className="text-xs font-semibold text-slate-600 hover:text-slate-900">{item.acao || 'Ver'}</button>}
              </div>
            );
          })}
        </div>}
    </div>
  );
}
