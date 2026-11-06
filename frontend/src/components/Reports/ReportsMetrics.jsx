import { FileText, Clock, CheckSquare, Send } from 'lucide-react';

const numero = new Intl.NumberFormat('pt-BR');

function formatarNumero(valor) {
  return Number.isFinite(valor) ? numero.format(valor) : '—';
}

function variacao(valor, unidade = '%') {
  if (valor === null || valor === undefined) return 'Sem comparação com o período anterior';
  return `${valor > 0 ? '↑ ' : valor < 0 ? '↓ ' : ''}${numero.format(Math.abs(valor))}${unidade} vs. período anterior`;
}

function tempo(segundos) {
  if (segundos === null || segundos === undefined) return 'Sem dados';
  const minutos = Math.floor(segundos / 60);
  const resto = Math.round(segundos % 60);
  return minutos ? `${minutos}m ${resto}s` : `${resto}s`;
}

export default function ReportsMetrics({ data }) {
  const metricas = data?.metricas || {};
  const metrics = [
    {
      title: 'Documentos processados',
      value: formatarNumero(metricas.documentos_processados?.valor),
      subtext: variacao(metricas.documentos_processados?.variacao),
      icon: FileText,
      iconBg: 'bg-indigo-50 text-indigo-600',
    },
    {
      title: 'Tempo médio de análise',
      value: tempo(metricas.tempo_medio_analise_segundos),
      subtext: 'Média dos lotes concluídos',
      icon: Clock,
      iconBg: 'bg-purple-50 text-purple-600',
    },
    {
      title: 'Concluídos sem revisão',
      value: Number.isFinite(metricas.concluidos_sem_revisao?.percentual)
        ? `${numero.format(metricas.concluidos_sem_revisao.percentual)}%`
        : '—',
      subtext: variacao(metricas.concluidos_sem_revisao?.variacao_pontos, ' p.p.'),
      icon: CheckSquare,
      iconBg: 'bg-emerald-50 text-emerald-600',
    },
    {
      title: 'Enviados para revisão',
      value: formatarNumero(metricas.enviados_para_revisao?.valor),
      subtext: 'No período selecionado',
      icon: Send,
      iconBg: 'bg-amber-50 text-amber-600',
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {metrics.map((item) => {
        const Icon = item.icon;
        return (
          <div key={item.title} className="bg-white p-5 rounded-2xl border border-slate-100 shadow-sm">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-medium text-slate-400 mb-1">{item.title}</p>
                <h3 className="text-2xl font-extrabold text-slate-900">{item.value}</h3>
              </div>
              <div className={`p-2.5 rounded-xl ${item.iconBg}`}>
                <Icon className="w-5 h-5" />
              </div>
            </div>
            <p className="text-[11px] text-slate-500 font-medium mt-3">{item.subtext}</p>
          </div>
        );
      })}
    </div>
  );
}
