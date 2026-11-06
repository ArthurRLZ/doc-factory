// Fornecedores: cria o link privado do portal (mostrado uma única vez), lista convites, revoga e vê os envios.
import { useState } from 'react';
import { Copy } from 'lucide-react';
import Layout from '../../components/Layout';
import { Cartao, ComDados, Erro, Selo, botao, botaoPrimario, campo } from '../../components/Estados';
import useApi from '../../hooks/useApi';
import api from '../../services/api';
import { data, mensagemDeErro } from '../../utils/formatar';

function NovoConvite({ tipos, aoCriar }) {
  const [nome, setNome] = useState('');
  const [exigidos, setExigidos] = useState(['CND_FEDERAL', 'CRF_FGTS', 'CNDT', 'CONTRATO']);
  const [dias, setDias] = useState(14);
  const [criado, setCriado] = useState(null);
  const [copiado, setCopiado] = useState(false);
  const [erro, setErro] = useState('');

  async function criar(e) {
    e.preventDefault(); setErro(''); setCopiado(false);
    try {
      const r = await api.post('/portal/convites', { fornecedor_nome: nome, exigidos, expira_dias: Number(dias) });
      // o link do servidor aponta para PORTAL_URL_BASE; aqui usamos o endereço desta tela, que é o mesmo front
      setCriado({ ...r.data, link: `${window.location.origin}/portal/${r.data.token}` });
      setNome(''); aoCriar();
    } catch (er) { setErro(mensagemDeErro(er, 'Não foi possível criar o convite.')); }
  }

  const alternar = (codigo) => setExigidos(x => x.includes(codigo) ? x.filter(c => c !== codigo) : [...x, codigo]);

  return <div className="space-y-4">
    <form onSubmit={criar} className="space-y-3">
      <div className="flex flex-wrap items-end gap-2">
        <label className="text-xs text-slate-600">Fornecedor<input className={`${campo} block w-72`} value={nome} onChange={e => setNome(e.target.value)} required minLength={2} placeholder="Construtora Exemplo LTDA" /></label>
        <label className="text-xs text-slate-600">Validade do link (dias)<input className={`${campo} block w-24`} type="number" min="1" max="365" value={dias} onChange={e => setDias(e.target.value)} /></label>
        <button className={botaoPrimario} type="submit" disabled={exigidos.length === 0}>Gerar link</button>
      </div>
      <fieldset>
        <legend className="mb-2 text-xs font-semibold text-slate-700">Documentos exigidos</legend>
        <div className="flex flex-wrap gap-2">
          {tipos.map(t => <label key={t.codigo} className={`cursor-pointer rounded-full border px-3 py-1 text-xs ${exigidos.includes(t.codigo) ? 'border-indigo-300 bg-indigo-50 text-indigo-800' : 'border-slate-200 text-slate-600'}`}>
            <input type="checkbox" className="sr-only" checked={exigidos.includes(t.codigo)} onChange={() => alternar(t.codigo)} />{t.nome}
          </label>)}
        </div>
      </fieldset>
      {erro && <Erro mensagem={erro} />}
    </form>
    {criado && <div role="status" className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm">
      <p className="font-bold text-amber-900">Copie o link agora: ele não será mostrado de novo.</p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <code className="break-all rounded bg-white px-2 py-1 text-xs text-slate-800">{criado.link}</code>
        <button type="button" className={botao} aria-label="Copiar link" onClick={async () => { await navigator.clipboard.writeText(criado.link); setCopiado(true); }}>
          <Copy className="inline h-3.5 w-3.5" aria-hidden="true" /> {copiado ? 'Copiado' : 'Copiar'}</button>
      </div>
      <p className="mt-1 text-xs text-amber-800">Expira em {data(criado.expira_em)}.</p>
    </div>}
  </div>;
}

function Envios({ id }) {
  const envios = useApi(() => api.get(`/portal/convites/${id}/envios`).then(r => r.data), [id]);
  return <ComDados estado={envios} vazio={l => l.length === 0} textoVazio="O fornecedor ainda não enviou nada.">
    {l => <div className="mt-3 space-y-3">{l.map(e => <div key={e.lote_id} className="rounded-xl bg-slate-50 p-3 text-xs">
      <p className="font-bold text-slate-700">{e.nome} · {e.status}</p>
      {e.documentos.map(d => <p key={d.id} className="mt-1 flex flex-wrap items-center gap-2 text-slate-600">
        {d.tipo_nome} <Selo valor={d.veredito} /> {d.risco !== 'confiavel' && <Selo valor={d.risco} />} {d.motivo || d.aviso || ''}
      </p>)}
    </div>)}</div>}
  </ComDados>;
}

export default function Fornecedores() {
  const dados = useApi(() => Promise.all([api.get('/portal/convites'), api.get('/tipos')])
    .then(([c, t]) => ({ convites: c.data, tipos: t.data })), []);
  const [aberto, setAberto] = useState(null);
  const [erro, setErro] = useState('');

  async function revogar(id) {
    try { await api.post(`/portal/convites/${id}/revogar`); dados.recarregar(); }
    catch (e) { setErro(mensagemDeErro(e)); }
  }

  return <Layout titulo="Fornecedores" subtitulo="Link privado: o fornecedor envia os documentos e vê na hora o que foi aprovado ou reprovado.">
    {erro && <Erro mensagem={erro} />}
    <ComDados estado={dados}>
      {d => <>
        <Cartao titulo="Novo convite"><NovoConvite tipos={d.tipos} aoCriar={dados.recarregar} /></Cartao>
        <Cartao titulo="Convites">
          {d.convites.length === 0 ? <p className="text-xs text-slate-500">Nenhum convite criado.</p> :
            <div className="divide-y divide-slate-100">
              {d.convites.map(c => <div key={c.id} className="py-3 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-semibold text-slate-800">{c.fornecedor_nome}</p>
                    <p className="text-xs text-slate-500">Expira em {data(c.expira_em)} · {c.usos}/{c.usos_max} envios · {c.situacao_resumo.aprovados} aprovado(s), {c.situacao_resumo.pendentes} pendente(s), {c.situacao_resumo.faltando} faltando</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Selo valor={c.ativo ? 'aprovado' : 'nao_enviado'} texto={c.ativo ? 'Ativo' : 'Revogado'} />
                    <button type="button" className={botao} onClick={() => setAberto(aberto === c.id ? null : c.id)}>{aberto === c.id ? 'Ocultar envios' : 'Ver envios'}</button>
                    {c.ativo && <button type="button" className={botao} onClick={() => revogar(c.id)}>Revogar</button>}
                  </div>
                </div>
                {aberto === c.id && <Envios id={c.id} />}
              </div>)}
            </div>}
        </Cartao>
      </>}
    </ComDados>
  </Layout>;
}
