import { FileText, Clock, CheckSquare, Send } from 'lucide-react';
import { num, pct } from '../../utils/formatar';

function tempo(segundos) {
  if (segundos === null || segundos === undefined) return '—';
  const m = Math.floor(segundos / 60);
  const s = Math.round(segundos % 60);
  return m ? `${m}m ${s}s` : `${s}s`;
}

function variacao(v, sufixo = '% vs. período anterior') {
  if (v === null || v === undefined) return 'sem período anterior para comparar';
  return `${v >= 0 ? '↑' : '↓'} ${Math.abs(v).toLocaleString('pt-BR')}${sufixo}`;
}

// Métricas do período (GET /relatorios → metricas).
export default function ReportsMetrics({ metricas: m }) {
  const itens = [
    { title: 'Documentos processados', value: num(m.documentos_processados.valor),
      subtext: variacao(m.documentos_processados.variacao), icon: FileText, iconBg: 'bg-indigo-50 text-indigo-600' },
    { title: 'Tempo médio de análise', value: tempo(m.tempo_medio_analise_segundos),
      subtext: 'por documento, do envio do lote à conclusão', icon: Clock, iconBg: 'bg-purple-50 text-purple-600' },
    { title: 'Concluídos sem revisão', value: pct(m.concluidos_sem_revisao.percentual),
      subtext: variacao(m.concluidos_sem_revisao.variacao_pontos, ' ponto(s) vs. período anterior'),
      icon: CheckSquare, iconBg: 'bg-emerald-50 text-emerald-600' },
    { title: 'Enviados para revisão', value: num(m.enviados_para_revisao.valor),
      subtext: 'decididos ou a decidir por uma pessoa', icon: Send, iconBg: 'bg-amber-50 text-amber-600' },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {itens.map((item) => {
        const Icon = item.icon;
        return (
          <div key={item.title} className="bg-white p-5 rounded-2xl border border-slate-100 shadow-sm">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-medium text-slate-400 mb-1">{item.title}</p>
                <h3 className="text-2xl font-extrabold text-slate-900">{item.value}</h3>
              </div>
              <div className={`p-2.5 rounded-xl ${item.iconBg}`}><Icon className="w-5 h-5" aria-hidden="true" /></div>
            </div>
            <p className="text-[11px] text-slate-500 font-medium mt-3">{item.subtext}</p>
          </div>
        );
      })}
    </div>
  );
}
