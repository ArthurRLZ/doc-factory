import { Cpu } from 'lucide-react';
import Layout from '../../components/Layout';
import StatCard from '../../components/StatCard';
import ChartSection from '../../components/ChartSection';
import AttentionSection from '../../components/AttentionSection';
import RecentDocuments from '../../components/RecentDocuments';
import SectorDistribution from '../../components/SectorDistribution';
import { Cartao, ComDados } from '../../components/Estados';
import { useAuth } from '../../context/useAuth';
import useApi from '../../hooks/useApi';
import api from '../../services/api';
import { num, pct } from '../../utils/formatar';

function saudacao() {
  const h = new Date().getHours();
  return h < 12 ? 'Bom dia' : h < 18 ? 'Boa tarde' : 'Boa noite';
}

function UsoDeIA({ ia }) {
  return <Cartao titulo="Uso de IA" subtitulo="Quantas páginas precisaram do modelo (o resto foi decidido por regras)">
    <div className="flex items-center gap-4">
      <div className="rounded-xl bg-indigo-50 p-3 text-indigo-600"><Cpu className="h-6 w-6" aria-hidden="true" /></div>
      <div>
        <p className="text-sm font-bold text-slate-800">
          {ia.paginas_total ? `Só ${pct(ia.percentual_paginas_com_ia)} das páginas precisaram de IA` : 'Nenhuma página processada ainda'}
        </p>
        <p className="text-xs text-slate-500">
          {num(ia.paginas_com_ia)} de {num(ia.paginas_total)} páginas · {num(ia.chamadas_total)} chamada(s) ao modelo
        </p>
      </div>
    </div>
  </Cartao>;
}

export default function Home() {
  const { user } = useAuth();
  const painel = useApi(() => api.get('/painel').then(r => r.data), [], { intervalo: 30000 });
  const hoje = new Date().toLocaleDateString('pt-BR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });

  return <Layout>
    <div className="flex items-center justify-between">
      <div>
        <p className="text-xs text-slate-400 font-medium mb-1">Início</p>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">{saudacao()}{user?.login ? `, ${user.login}` : ''}</h1>
        <p className="text-xs text-slate-500 mt-1">Aqui está o que precisa da sua atenção hoje.</p>
      </div>
      <p className="text-xs font-medium text-slate-400 first-letter:uppercase">{hoje}</p>
    </div>

    <ComDados estado={painel} vazio={p => p.cartoes.documentos_ativos.valor === 0}
              textoVazio="Nenhum documento ainda. Envie um lote na tela Documentos para ver o painel.">
      {p => <>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard title="Documentos ativos" value={num(p.cartoes.documentos_ativos.valor)}
                    subtext={`+${num(p.cartoes.documentos_ativos.este_mes)} este mês`} color="indigo" />
          <StatCard title="Vencem esta semana" value={num(p.cartoes.vencem_semana.valor)}
                    subtext={`${num(p.cartoes.vencem_semana.vencem_hoje)} vencem hoje · ${num(p.cartoes.vencem_semana.vencidos)} vencidos`} color="red" />
          <StatCard title="Aguardando revisão" value={num(p.cartoes.aguardando_revisao.valor)}
                    subtext={`${num(p.cartoes.aguardando_revisao.alta_prioridade)} com alta prioridade`} color="amber" />
          <StatCard title="Analisados sem revisão" value={pct(p.cartoes.analisados_sem_revisao.percentual)}
                    subtext={`${num(p.cartoes.analisados_sem_revisao.total)} documentos aprovados automaticamente`} color="emerald" />
        </div>
        <UsoDeIA ia={p.ia} />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2"><ChartSection volume={p.volume_7_dias} /></div>
          <div><AttentionSection itens={p.atencao} /></div>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2"><RecentDocuments documentos={p.recentes} /></div>
          <div><SectorDistribution setores={p.por_setor} /></div>
        </div>
      </>}
    </ComDados>
  </Layout>;
}
