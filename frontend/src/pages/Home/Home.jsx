import { useEffect, useState } from 'react';
import Sidebar from '../../components/Sidebar';
import Header from '../../components/Header';
import StatCard from '../../components/StatCard';
import ChartSection from '../../components/ChartSection';
import AttentionSection from '../../components/AttentionSection';
import RecentDocuments from '../../components/RecentDocuments';
import SectorDistribution from '../../components/SectorDistribution';
import { useAuth } from '../../context/useAuth';
import api from '../../services/api';

const numero = new Intl.NumberFormat('pt-BR');

function formatarNumero(valor) {
  return Number.isFinite(valor) ? numero.format(valor) : '—';
}

function formatarPercentual(valor) {
  return Number.isFinite(valor) ? `${numero.format(valor)}%` : '—';
}

function mensagemErro(error) {
  return error.response?.data?.detail
    || error.response?.data?.erro?.mensagem
    || 'Não foi possível carregar os dados do painel.';
}

export default function Home() {
  const { user } = useAuth();
  const [painel, setPainel] = useState(null);
  const [erro, setErro] = useState('');
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    let ativo = true;
    api.get('/painel')
      .then(({ data }) => {
        if (ativo) {
          setPainel(data);
          setErro('');
        }
      })
      .catch((error) => {
        if (ativo) setErro(mensagemErro(error));
      })
      .finally(() => {
        if (ativo) setCarregando(false);
      });

    return () => { ativo = false; };
  }, []);

  const cartoes = painel?.cartoes;
  const dia = painel?.hoje
    ? new Date(`${painel.hoje}T12:00:00`).toLocaleDateString('pt-BR', {
      weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
    })
    : '';

  return (
    <div className="min-h-screen bg-slate-50 flex font-sans antialiased">
      <Sidebar reviewCount={painel ? painel.fila_revisao : null} />

      <div className="flex-1 ml-64 flex flex-col">
        <Header />

        <main className="p-8 max-w-7xl w-full mx-auto space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-slate-400 font-medium mb-1">Início</p>
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
                Bom dia, {user?.login || 'usuário'}
              </h1>
              <p className="text-xs text-slate-500 mt-1">Aqui está o que precisa da sua atenção hoje.</p>
            </div>
            {dia && <p className="text-xs font-medium text-slate-400">{dia}</p>}
          </div>

          {erro && (
            <div role="alert" className="flex items-center justify-between gap-4 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
              <span>{erro}</span>
              <button className="font-semibold underline" onClick={() => window.location.reload()} type="button">Tentar novamente</button>
            </div>
          )}

          {carregando && !painel && <p className="text-sm text-slate-500">Carregando dados do painel...</p>}

          {cartoes && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard
                  title="Documentos ativos"
                  value={formatarNumero(cartoes.documentos_ativos?.valor)}
                  subtext={`${formatarNumero(cartoes.documentos_ativos?.este_mes)} neste mês`}
                  color="indigo"
                />
                <StatCard
                  title="Vencem esta semana"
                  value={formatarNumero(cartoes.vencem_semana?.valor)}
                  subtext={`${formatarNumero(cartoes.vencem_semana?.vencem_hoje)} vencem hoje · ${formatarNumero(cartoes.vencem_semana?.vencidos)} vencidos`}
                  color="red"
                />
                <StatCard
                  title="Aguardando revisão"
                  value={formatarNumero(cartoes.aguardando_revisao?.valor)}
                  subtext={`${formatarNumero(cartoes.aguardando_revisao?.alta_prioridade)} com alta prioridade`}
                  color="amber"
                />
                <StatCard
                  title="Analisados sem revisão"
                  value={formatarPercentual(cartoes.analisados_sem_revisao?.percentual)}
                  subtext={`${formatarNumero(cartoes.analisados_sem_revisao?.total)} aprovados automaticamente`}
                  color="emerald"
                />
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2">
                  <ChartSection volume={painel.volume_7_dias} />
                </div>
                <div>
                  <AttentionSection items={painel.atencao} />
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2">
                  <RecentDocuments documents={painel.recentes} />
                </div>
                <div>
                  <SectorDistribution sectors={painel.por_setor} />
                </div>
              </div>
            </>
          )}

        </main>
      </div>
    </div>
  );
}
