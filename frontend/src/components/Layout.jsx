// Moldura das telas internas: menu lateral + cabeçalho + conteúdo.
import Sidebar from './Sidebar';
import Header from './Header';

export default function Layout({ titulo, subtitulo, acoes, children }) {
  return <div className="min-h-screen bg-slate-50 flex font-sans antialiased">
    <Sidebar />
    <div className="flex-1 ml-64 flex flex-col min-w-0">
      <Header />
      <main className="p-8 max-w-7xl w-full mx-auto space-y-6">
        {titulo && <div className="flex flex-wrap items-center justify-between gap-4">
          <div><h1 className="text-2xl font-bold tracking-tight text-slate-900">{titulo}</h1>
            {subtitulo && <p className="mt-1 text-xs text-slate-500">{subtitulo}</p>}</div>
          {acoes}
        </div>}
        {children}
      </main>
    </div>
  </div>;
}
