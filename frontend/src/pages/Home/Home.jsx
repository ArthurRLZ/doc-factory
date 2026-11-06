import Sidebar from '../../components/Sidebar';
import Header from '../../components/Header';
import StatCard from '../../components/StatCard';
import ChartSection from '../../components/ChartSection';
import AttentionSection from '../../components/AttentionSection';
import RecentDocuments from '../../components/RecentDocuments';
import SectorDistribution from '../../components/SectorDistribution';

export default function Home() {
  return (
    <div className="min-h-screen bg-slate-50 flex font-sans antialiased">
      {/* Sidebar Fixa */}
      <Sidebar />

      {/* Container Principal */}
      <div className="flex-1 ml-64 flex flex-col">
        <Header />

        <main className="p-8 max-w-7xl w-full mx-auto space-y-6">
          {/* Welcome Header */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-slate-400 font-medium mb-1">Início</p>
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Bom dia, Marina</h1>
              <p className="text-xs text-slate-500 mt-1">Aqui está o que precisa da sua atenção hoje.</p>
            </div>
            <p className="text-xs font-medium text-slate-400">Quinta-feira, 6 de novembro de 2026</p>
          </div>

          {/* Metric Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard title="Documentos ativos" value="163" subtext="+18 este mês" color="indigo" />
            <StatCard title="Vencem esta semana" value="12" subtext="3 vencem hoje" color="red" />
            <StatCard title="Aguardando revisão" value="5" subtext="2 com alta prioridade" color="amber" />
            <StatCard title="Analisados com sucesso" value="94,8%" subtext="+2,1% este mês" color="emerald" />
          </div>

          {/* Middle Section: Chart + Attention */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2">
              <ChartSection />
            </div>
            <div>
              <AttentionSection />
            </div>
          </div>

          {/* Bottom Section: Recent Docs + Sector Dist */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2">
              <RecentDocuments />
            </div>
            <div>
              <SectorDistribution />
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}