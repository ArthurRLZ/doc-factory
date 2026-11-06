import Sidebar from '../../components/Sidebar';
import Header from '../../components/Header';
import DocumentsHeader from '../../components/Documents/DocumentsHeader';
import DocumentsMetrics from '../../components/Documents/DocumentsMetrics';
import DocumentsFilters from '../../components/Documents/DocumentsFilter';
import DocumentsTable from '../../components/Documents/DocumentsTable';

export default function Documents() {
  return (
    <div className="min-h-screen bg-slate-50 flex font-sans antialiased">
      {/* Sidebar Fixa */}
      <Sidebar />

      {/* Container Principal */}
      <div className="flex-1 ml-64 flex flex-col">
        <Header />

        <main className="p-8 max-w-7xl w-full mx-auto space-y-6">
          <DocumentsHeader />
          <DocumentsMetrics />

          <div className="space-y-0">
            <div className="flex items-center justify-between px-1 mb-3">
              <h3 className="text-sm font-bold text-slate-800">
                Todos os documentos <span className="text-slate-400 font-normal text-xs ml-1">6 de 163 documentos</span>
              </h3>
            </div>
            <DocumentsFilters />
            <DocumentsTable />
          </div>
        </main>
      </div>
    </div>
  );
}