// Estados obrigatórios de toda tela: carregando, erro (com "tentar de novo") e vazio — e peças visuais comuns.
import { AlertTriangle, Inbox, Loader2 } from 'lucide-react';
import { CORES_SITUACAO, ROTULOS } from '../utils/formatar';

export function Carregando({ texto = 'Carregando...' }) {
  return <div role="status" className="flex items-center gap-2 rounded-xl border border-slate-100 bg-white p-6 text-sm text-slate-500">
    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> {texto}
  </div>;
}

export function Erro({ mensagem, tentarDeNovo }) {
  return <div role="alert" className="flex items-center justify-between gap-4 rounded-xl border border-rose-100 bg-rose-50 p-4 text-sm text-rose-800">
    <span className="flex items-center gap-2"><AlertTriangle className="h-4 w-4" aria-hidden="true" /> {mensagem}</span>
    {tentarDeNovo && <button type="button" onClick={tentarDeNovo} className="rounded-lg border border-rose-200 bg-white px-3 py-1.5 text-xs font-semibold hover:bg-rose-100">Tentar de novo</button>}
  </div>;
}

export function Vazio({ texto = 'Nada por aqui ainda. Envie um lote na tela Documentos.' }) {
  return <div className="flex items-center gap-2 rounded-xl border border-dashed border-slate-200 bg-white p-6 text-sm text-slate-500">
    <Inbox className="h-4 w-4" aria-hidden="true" /> {texto}
  </div>;
}

// Carregando/erro enquanto não há dados; com dados, renderiza `children(dados)` (ou o estado vazio).
export function ComDados({ estado, vazio, textoVazio, children }) {
  const { dados, erro, carregando, recarregar } = estado;
  if (carregando && !dados) return <Carregando />;
  if (erro && !dados) return <Erro mensagem={erro} tentarDeNovo={recarregar} />;
  if (!dados) return null;
  return <>
    {erro && <Erro mensagem={erro} tentarDeNovo={recarregar} />}
    {vazio && vazio(dados) ? <Vazio texto={textoVazio} /> : children(dados)}
  </>;
}

export function Selo({ valor, texto, title }) {
  const cor = CORES_SITUACAO[valor] || 'bg-slate-100 text-slate-700 border-slate-200';
  return <span title={title} className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold ${cor}`}>
    {texto || ROTULOS[valor] || valor}
  </span>;
}

export function Cartao({ titulo, subtitulo, acoes, children, className = '' }) {
  return <section className={`rounded-2xl border border-slate-100 bg-white p-6 shadow-sm ${className}`}>
    {(titulo || acoes) && <div className="mb-4 flex items-start justify-between gap-4">
      <div>{titulo && <h2 className="text-sm font-bold text-slate-800">{titulo}</h2>}
        {subtitulo && <p className="text-xs text-slate-400">{subtitulo}</p>}</div>
      {acoes}
    </div>}
    {children}
  </section>;
}

export const botao = 'rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50';
export const botaoPrimario = 'rounded-lg bg-indigo-950 px-3 py-2 text-xs font-semibold text-white hover:bg-indigo-900 disabled:opacity-50';
export const campo = 'rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-500';
