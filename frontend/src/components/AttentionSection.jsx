import { useNavigate } from 'react-router-dom';
import { AlertCircle, Clock, CheckCircle, ShieldAlert } from 'lucide-react';

const icones = {
  vencidos: AlertCircle,
  vencem_semana: Clock,
  revisao: Clock,
  fraude: ShieldAlert,
  trabalhadores_irregulares: ShieldAlert,
  processados_hoje: CheckCircle,
};

const cores = {
  alta: 'bg-rose-50 text-rose-500',
  media: 'bg-amber-50 text-amber-500',
  ok: 'bg-emerald-50 text-emerald-500',
};

export default function AttentionSection({ items = [] }) {
  const navigate = useNavigate();

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex flex-col justify-between">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h4 className="font-bold text-slate-800 text-sm">Precisa de atenção</h4>
          <p className="text-xs text-slate-400">Itens prioritários para hoje</p>
        </div>
        <button onClick={() => navigate('/documentos')} className="text-xs font-semibold text-indigo-600 hover:text-indigo-800">Ver todos</button>
      </div>

      <div className="space-y-3">
        {items.map((item) => {
          const Icon = icones[item.tipo] || AlertCircle;
          return (
            <div key={item.tipo} className="flex items-center justify-between p-3 rounded-xl border border-slate-50 bg-slate-50/50 hover:bg-slate-50 transition-colors">
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-lg ${cores[item.gravidade] || cores.media}`}>
                  <Icon className="w-4 h-4" />
                </div>
                <div>
                  <p className="text-xs font-bold text-slate-800">{item.title}</p>
                  <p className="text-[11px] text-slate-400">{item.subtitle}</p>
                </div>
              </div>
              <button onClick={() => navigate('/documentos')} className="text-xs font-semibold text-slate-600 hover:text-slate-900">{item.acao}</button>
            </div>
          );
        })}
        {!items.length && <p className="text-sm text-slate-400">Nenhum item de atenção no momento.</p>}
      </div>
    </div>
  );
}