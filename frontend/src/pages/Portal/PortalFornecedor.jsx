// Portal do fornecedor (PÚBLICO, sem login): o token na URL é a autenticação. Sem menu e sem dado interno.
import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { UploadCloud } from 'lucide-react';
import { Carregando, Erro, Selo } from '../../components/Estados';
import api from '../../services/api';
import { dataHora, mensagemDeErro } from '../../utils/formatar';

export default function PortalFornecedor() {
  const { token } = useParams();
  const [portal, setPortal] = useState(null);
  const [erro, setErro] = useState('');
  const [invalido, setInvalido] = useState(false);
  const [envio, setEnvio] = useState(null);           // {envio_id, status, progresso, documentos, mensagem}
  const [arrastando, setArrastando] = useState(false);
  const timer = useRef(null);

  const carregar = useCallback(async () => {
    try { setPortal((await api.get(`/portal/${token}`)).data); }
    catch (e) { if (e.response?.status === 404) setInvalido(true); else setErro(mensagemDeErro(e)); }
  }, [token]);

  useEffect(() => { const t = setTimeout(carregar, 0); return () => clearTimeout(t); }, [carregar]);
  useEffect(() => () => clearInterval(timer.current), []);

  function acompanhar(envioId) {
    clearInterval(timer.current);
    timer.current = setInterval(async () => {
      try {
        const r = (await api.get(`/portal/${token}/envios/${envioId}`)).data;
        setEnvio(r);
        if (r.status !== 'processando') {
          clearInterval(timer.current);
          setPortal(p => p && { ...p, situacao: r.situacao });
        }
      } catch (e) { clearInterval(timer.current); setErro(mensagemDeErro(e)); }
    }, 2000);
  }

  async function enviar(arquivo) {
    if (!arquivo) return;
    setErro(''); setEnvio({ status: 'enviando', progresso: 0, documentos: [] });
    const dados = new FormData();
    dados.append('arquivo', arquivo);
    try {
      const r = (await api.post(`/portal/${token}/enviar`, dados)).data;
      setEnvio({ envio_id: r.envio_id, status: 'processando', progresso: 0, documentos: [] });
      acompanhar(r.envio_id);
      carregar();
    } catch (e) {
      setEnvio(null);
      if (e.response?.status === 404) setInvalido(true);
      else setErro(e.response?.status === 413 ? 'Arquivo grande demais.' : mensagemDeErro(e, 'Não foi possível enviar o arquivo.'));
    }
  }

  if (invalido) return <Moldura><Erro mensagem="Link inválido ou expirado. Peça um novo link a quem contratou o serviço." /></Moldura>;
  if (!portal) return <Moldura>{erro ? <Erro mensagem={erro} tentarDeNovo={carregar} /> : <Carregando />}</Moldura>;

  return <Moldura fornecedor={portal.fornecedor}>
    <p className="text-sm text-slate-600">Envie os documentos abaixo em PDF ou foto. Você vê o resultado de cada um em instantes e pode reenviar o que for reprovado.</p>
    {erro && <Erro mensagem={erro} />}
    <div className="grid gap-3 sm:grid-cols-2">
      {portal.situacao.map(s => <div key={s.tipo} className="rounded-xl border border-slate-100 bg-white p-4 shadow-sm">
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm font-bold text-slate-800">{s.tipo_nome}</p>
          <Selo valor={s.situacao} />
        </div>
        {s.motivo && <p className="mt-2 text-xs text-rose-700">{s.motivo}</p>}
        {s.aviso && <p className="mt-2 text-xs text-amber-700">{s.aviso}</p>}
        {s.enviado_em && <p className="mt-2 text-[11px] text-slate-400">Enviado em {dataHora(s.enviado_em)}</p>}
      </div>)}
    </div>

    <label onDragOver={e => { e.preventDefault(); setArrastando(true); }} onDragLeave={() => setArrastando(false)}
           onDrop={e => { e.preventDefault(); setArrastando(false); enviar(e.dataTransfer.files?.[0]); }}
           className={`flex cursor-pointer flex-col items-center gap-2 rounded-2xl border-2 border-dashed p-8 text-center text-sm ${arrastando ? 'border-indigo-400 bg-indigo-50' : 'border-slate-300 bg-white'}`}>
      <UploadCloud className="h-8 w-8 text-slate-400" aria-hidden="true" />
      <span className="font-semibold text-slate-700">Arraste o arquivo aqui ou clique para escolher</span>
      <span className="text-xs text-slate-400">PDF, PNG, JPG ou TIFF · {portal.envios_restantes} envio(s) restante(s) neste link</span>
      <input type="file" className="sr-only" accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff" disabled={envio?.status === 'processando' || envio?.status === 'enviando'}
             onChange={e => { enviar(e.target.files?.[0]); e.target.value = ''; }} />
    </label>

    {envio && <div className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm" role="status" aria-live="polite">
      {envio.status === 'concluido' ? <p className="text-sm font-bold text-slate-800">Resultado deste envio</p>
        : envio.status === 'erro' ? <Erro mensagem={envio.mensagem || 'Não foi possível ler este arquivo. Tente reenviar.'} />
        : <>
          <p className="text-sm text-slate-700">{envio.status === 'enviando' ? 'Enviando...' : 'Analisando os documentos...'}</p>
          <progress className="mt-2 w-full" max="1" value={envio.progresso || 0} aria-label="Progresso da análise" />
        </>}
      {envio.documentos?.length > 0 && <ul className="mt-3 space-y-2 text-sm">
        {envio.documentos.map(d => <li key={d.ordem} className="flex flex-wrap items-center gap-2">
          <span className="text-slate-700">{d.ordem}. {d.tipo_nome}</span><Selo valor={d.veredito} />
          {(d.motivo || d.aviso) && <span className="text-xs text-slate-500">{d.motivo || d.aviso}</span>}
        </li>)}
      </ul>}
    </div>}
  </Moldura>;
}

function Moldura({ fornecedor, children }) {
  return <div className="min-h-screen bg-slate-50 font-sans antialiased">
    <header className="border-b border-slate-100 bg-white px-6 py-4">
      <p className="text-xs font-semibold uppercase tracking-wider text-indigo-600">Portal do Fornecedor</p>
      {fornecedor && <h1 className="text-lg font-bold text-slate-900">{fornecedor}</h1>}
    </header>
    <main className="mx-auto max-w-3xl space-y-5 p-6">{children}</main>
  </div>;
}
