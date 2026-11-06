import Sidebar from '../../components/Sidebar';
import Header from '../../components/Header';
import ReportsHeader from '../../components/Reports/ReportsHeader';
import ReportsMetrics from '../../components/Reports/ReportsMetrics';
import VolumeChart from '../../components/Reports/VolumeChart';
import PriorityDonutChart from '../../components/Reports/PriorityDonutChart';
import SectorVolume from '../../components/Reports/SectorVolume';
import StatusPrazos from '../../components/Reports/StatusPrazos';

export default function Reports() {
  return (
    <div className="min-h-screen bg-slate-50 flex font-sans antialiased">
      {/* Sidebar Fixa */}
      <Sidebar />

      {/* Content Area */}
      <div className="flex-1 ml-64 flex flex-col">
        <Header />

        <main className="p-8 max-w-7xl w-full mx-auto space-y-6">
          <ReportsHeader />
          <ReportsMetrics />

          {/* Gráficos Principais */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2">
              <VolumeChart />
            </div>
            <div>
              <PriorityDonutChart />
            </div>
          </div>

          {/* Detalhes de Setores e Prazos */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2">
              <SectorVolume />
            </div>
            <div>
              <StatusPrazos />
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}