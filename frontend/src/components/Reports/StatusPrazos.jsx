import { CheckCircle2, Clock, AlertTriangle } from 'lucide-react';

const aparencia = {
  vigente: { icon: CheckCircle2, iconBg: 'bg-emerald-50 text-emerald-600', badge: 'text-emerald-700' },
  vencendo: { icon: Clock, iconBg: 'bg-amber-50 text-amber-600', badge: 'text-amber-700' },
  vencido: { icon: AlertTriangle, iconBg: 'bg-rose-50 text-rose-600', badge: 'text-rose-700' },
};
const numero = new Intl.NumberFormat('pt-BR');

export default function StatusPrazos({ statuses = [] }) {
  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex flex-col justify-between">
      <div>
        <h4 className="font-bold text-slate-800 text-sm">Situação dos prazos</h4>
        <p className="text-xs text-slate-400 mb-4">Resumo dos documentos no período</p>
      </div>

      <div className="space-y-3">
        {statuses.map((status) => {
          const style = aparencia[status.status] || aparencia.vigente;
          const Icon = style.icon;
          return (
            <div key={status.status} className="flex items-center justify-between p-3.5 rounded-xl border border-slate-50 bg-slate-50/50 hover:bg-slate-50 transition-colors">
              <div className="flex items-center gap-3">
                <div className={`p-2.5 rounded-lg ${style.iconBg}`}><Icon className="w-4 h-4" /></div>
                <div>
                  <p className="text-sm font-extrabold text-slate-800">{numero.format(status.total)}</p>
                  <p className="text-[11px] text-slate-400 font-medium">{status.rotulo}</p>
                </div>
              </div>
              <span className={`text-xs font-bold ${style.badge}`}>{numero.format(status.percentual)}%</span>
            </div>
          );
        })}
        {!statuses.length && <p className="text-sm text-slate-400">Sem documentos com prazo identificado.</p>}
      </div>
    </div>
  );
}
