import { useState } from 'react';
import Layout from '../../components/Layout';
import ReportsHeader from '../../components/Reports/ReportsHeader';
import ReportsMetrics from '../../components/Reports/ReportsMetrics';
import VolumeChart from '../../components/Reports/VolumeChart';
import PriorityDonutChart from '../../components/Reports/PriorityDonutChart';
import SectorVolume from '../../components/Reports/SectorVolume';
import StatusPrazos from '../../components/Reports/StatusPrazos';
import { ComDados } from '../../components/Estados';
import useApi from '../../hooks/useApi';
import api from '../../services/api';

export default function Reports() {
  const [dias, setDias] = useState(30);
  const rel = useApi(() => api.get('/relatorios', { params: { dias } }).then(r => r.data), [dias]);

  return <Layout>
    <ReportsHeader dias={dias} onDias={setDias} dados={rel.dados} />
    <ComDados estado={rel} vazio={r => r.metricas.documentos_processados.valor === 0}
              textoVazio="Nenhum documento processado neste período. Envie um lote na tela Documentos.">
      {r => <>
        <ReportsMetrics metricas={r.metricas} />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2"><VolumeChart pontos={r.volume_diario} /></div>
          <div><PriorityDonutChart prioridades={r.por_prioridade} /></div>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2"><SectorVolume setores={r.por_setor} /></div>
          <div><StatusPrazos status={r.status_prazos} /></div>
        </div>
      </>}
    </ComDados>
  </Layout>;
}
