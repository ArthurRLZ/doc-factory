// Situação dos prazos (GET /relatorios → status_prazos).
import { CheckCircle2, Clock, AlertTriangle } from 'lucide-react';
import { num, pct } from '../../utils/formatar';

const ESTILO = {
  vigente: { icon: CheckCircle2, iconBg: 'bg-emerald-50 text-emerald-600', texto: 'text-emerald-700' },
  vencendo: { icon: Clock, iconBg: 'bg-amber-50 text-amber-600', texto: 'text-amber-700' },
  vencido: { icon: AlertTriangle, iconBg: 'bg-rose-50 text-rose-600', texto: 'text-rose-700' },
};

export default function StatusPrazos({ status = [] }) {
  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex flex-col justify-between">
      <div>
        <h4 className="font-bold text-slate-800 text-sm">Situação dos prazos</h4>
        <p className="text-xs text-slate-400 mb-4">Documentos com validade no período</p>
      </div>
      <div className="space-y-3">
        {status.map((item) => {
          const e = ESTILO[item.status] || ESTILO.vigente;
          const Icon = e.icon;
          return (
            <div key={item.status} className="flex items-center justify-between p-3.5 rounded-xl border border-slate-50 bg-slate-50/50">
              <div className="flex items-center gap-3">
                <div className={`p-2.5 rounded-lg ${e.iconBg}`}><Icon className="w-4 h-4" aria-hidden="true" /></div>
                <div>
                  <p className="text-sm font-extrabold text-slate-800">{num(item.total)}</p>
                  <p className="text-[11px] text-slate-400 font-medium">{item.rotulo}</p>
                </div>
              </div>
              <span className={`text-xs font-bold ${e.texto}`}>{pct(item.percentual)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
