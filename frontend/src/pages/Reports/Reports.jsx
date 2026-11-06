import { useEffect, useState } from 'react';
import Sidebar from '../../components/Sidebar';
import Header from '../../components/Header';
import ReportsHeader from '../../components/Reports/ReportsHeader';
import ReportsMetrics from '../../components/Reports/ReportsMetrics';
import VolumeChart from '../../components/Reports/VolumeChart';
import PriorityDonutChart from '../../components/Reports/PriorityDonutChart';
import SectorVolume from '../../components/Reports/SectorVolume';
import StatusPrazos from '../../components/Reports/StatusPrazos';
import api from '../../services/api';

function mensagemErro(error) {
  return error.response?.data?.detail
    || error.response?.data?.erro?.mensagem
    || 'Não foi possível carregar os relatórios.';
}

function exportar(data) {
  const linhas = [
    ['Relatório', 'Início', 'Fim'],
    ['Documentos', data.periodo.inicio, data.periodo.fim],
    [],
    ['Métrica', 'Valor'],
    ['Documentos processados', data.metricas.documentos_processados.valor],
    ['Tempo médio de análise (s)', data.metricas.tempo_medio_analise_segundos ?? 'Sem dados'],
    ['Concluídos sem revisão (%)', data.metricas.concluidos_sem_revisao.percentual],
    ['Enviados para revisão', data.metricas.enviados_para_revisao.valor],
    [],
    ['Prioridade', 'Total', 'Percentual (%)'],
    ...data.por_prioridade.map((item) => [item.prioridade, item.total, item.percentual]),
    [],
    ['Setor', 'Total', 'Percentual (%)'],
    ...data.por_setor.map((item) => [item.setor, item.total, item.percentual]),
    [],
    ['Prazo', 'Total', 'Percentual (%)'],
    ...data.status_prazos.map((item) => [item.rotulo, item.total, item.percentual]),
  ];
  const csv = `\uFEFF${linhas.map((linha) => linha.map((valor) => (
    `"${String(valor ?? '').replaceAll('"', '""')}"`
  )).join(';')).join('\r\n')}`;
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = `relatorio-${data.periodo.inicio}-${data.periodo.fim}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

export default function Reports() {
  const [dias, setDias] = useState(30);
  const [relatorio, setRelatorio] = useState(null);
  const [diasCarregados, setDiasCarregados] = useState(null);
  const [erro, setErro] = useState('');

  useEffect(() => {
    let ativo = true;
    api.get('/relatorios', { params: { dias } })
      .then(({ data }) => {
        if (ativo) {
          setRelatorio(data);
          setDiasCarregados(dias);
          setErro('');
        }
      })
      .catch((error) => {
        if (ativo) setErro(mensagemErro(error));
      });

    return () => { ativo = false; };
  }, [dias]);
  const carregando = diasCarregados !== dias && !erro;

  return (
    <div className="min-h-screen bg-slate-50 flex font-sans antialiased">
      <Sidebar />

      <div className="flex-1 ml-64 flex flex-col">
        <Header />

        <main className="p-8 max-w-7xl w-full mx-auto space-y-6">
          <ReportsHeader
            days={dias}
            onDaysChange={(value) => setDias(Number(value))}
            onExport={() => relatorio && diasCarregados === dias && exportar(relatorio)}
            canExport={Boolean(relatorio && diasCarregados === dias)}
          />

          {erro && <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{erro}</div>}
          {carregando && !relatorio && <p className="text-sm text-slate-500">Carregando relatórios...</p>}

          {relatorio && diasCarregados === dias && (
            <>
              <ReportsMetrics data={relatorio} />

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2">
                  <VolumeChart volume={relatorio.volume_diario} />
                </div>
                <div>
                  <PriorityDonutChart priorities={relatorio.por_prioridade} />
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2">
                  <SectorVolume sectors={relatorio.por_setor} />
                </div>
                <div>
                  <StatusPrazos statuses={relatorio.status_prazos} />
                </div>
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
