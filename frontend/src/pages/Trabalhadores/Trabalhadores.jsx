// Trabalhadores: situação do checklist (irregular primeiro) e o dossiê com a função e as NRs exigidas.
import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import Layout from '../../components/Layout';
import { Cartao, ComDados, Erro, Selo, botao, campo } from '../../components/Estados';
import useApi from '../../hooks/useApi';
import api from '../../services/api';
import { data, mensagemDeErro } from '../../utils/formatar';

const ORIGEM_FUNCAO = { texto: 'lida no documento', ia: 'identificada pela IA', manual: 'corrigida manualmente' };

function Dossie({ id, funcoes, aoMudar }) {
  const d = useApi(() => api.get(`/trabalhadores/${id}/dossie`).then(r => r.data), [id]);
  const [erro, setErro] = useState('');

  async function corrigir(chave) {
    setErro('');
    try { await api.put(`/trabalhadores/${id}/funcao`, { funcao_chave: chave || null }); d.recarregar(); aoMudar(); }
    catch (e) { setErro(mensagemDeErro(e, 'Não foi possível corrigir a função.')); }
  }

  return <ComDados estado={d}>
    {t => <Cartao titulo={`Dossiê — ${t.rotulo}`} subtitulo={`${t.documentos} documento(s) · situação: ${t.situacao}`}>
      <div className="space-y-5">
        <div className="rounded-xl bg-slate-50 p-4 text-sm">
          <p className="text-xs font-bold text-slate-700">Função</p>
          <p className="mt-1 text-slate-800">{t.funcao || 'não identificada'}
            {t.funcao_origem && <span className="text-xs text-slate-500"> · {ORIGEM_FUNCAO[t.funcao_origem] || t.funcao_origem}</span>}</p>
          {t.funcao_evidencia && <p className="mt-1 text-xs text-slate-500">Evidência: “{t.funcao_evidencia}”</p>}
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <label htmlFor="funcao" className="text-xs text-slate-600">Corrigir função:</label>
            <select id="funcao" className={campo} value={t.funcao_chave || ''} onChange={e => corrigir(e.target.value)}>
              <option value="">(sem função com exigência)</option>
              {funcoes.map(f => <option key={f.chave} value={f.chave}>{f.nome} — {f.nrs.join(', ')}</option>)}
            </select>
          </div>
          <p className="mt-2 text-[11px] text-slate-400">Regra de exigência configurável (função → NRs); validar com a área de SST.</p>
          {erro && <div className="mt-2"><Erro mensagem={erro} /></div>}
        </div>

        <div>
          <h3 className="mb-2 text-xs font-bold text-slate-700">Checklist</h3>
          <div className="divide-y divide-slate-100 rounded-xl border border-slate-100">
            {t.checklist.map(i => <div key={i.tipo} className="flex flex-wrap items-center justify-between gap-2 p-3 text-sm">
              <div>
                <p className="font-semibold text-slate-800">{i.tipo_nome}</p>
                <p className="text-xs text-slate-500">{[i.observacao, i.validade && `validade ${data(i.validade)}`].filter(Boolean).join(' · ')}</p>
                {i.motivo_exigencia && <p className="text-xs text-indigo-700">{i.motivo_exigencia}</p>}
              </div>
              <Selo valor={i.status} />
            </div>)}
          </div>
        </div>

        {t.outros_alertas.length > 0 && <div>
          <h3 className="mb-2 text-xs font-bold text-slate-700">Outros alertas</h3>
          {t.outros_alertas.map(a => <p key={a.documento_id} className="text-xs text-amber-800">{a.tipo_nome}: {a.observacao}</p>)}
        </div>}
        {t.duplicados.length > 0 && <div>
          <h3 className="mb-2 text-xs font-bold text-slate-700">Duplicados (vale o mais recente)</h3>
          {t.duplicados.map(x => <p key={x.tipo} className="text-xs text-slate-600">{x.tipo_nome}: {x.substituidos.length} substituído(s)</p>)}
        </div>}
        <div>
          <h3 className="mb-2 text-xs font-bold text-slate-700">Documentos</h3>
          <ul className="space-y-1 text-xs text-slate-600">
            {t.itens.map(doc => <li key={doc.id} className="flex items-center gap-2">
              <a className="font-semibold text-indigo-700 hover:underline" href={`${api.defaults.baseURL}/documentos/${doc.id}/pdf`} target="_blank" rel="noreferrer">{doc.titulo || doc.tipo_nome}</a>
              <span>{doc.tipo_nome}</span>{doc.validade?.status && <Selo valor={doc.validade.status} />}
            </li>)}
          </ul>
        </div>
      </div>
    </Cartao>}
  </ComDados>;
}

export default function Trabalhadores() {
  const [params] = useSearchParams();
  const [situacao, setSituacao] = useState(params.get('situacao') || '');
  const [aberto, setAberto] = useState(null);
  const lista = useApi(() => Promise.all([api.get('/trabalhadores', { params: { situacao: situacao || undefined } }), api.get('/funcoes')])
    .then(([t, f]) => ({ ...t.data, funcoes: f.data })), [situacao]);

  return <Layout titulo="Trabalhadores" subtitulo="Checklist de documentos por pessoa. O CPF nunca é guardado: só a versão mascarada."
                 acoes={<select aria-label="Filtrar por situação" className={campo} value={situacao} onChange={e => setSituacao(e.target.value)}>
                   <option value="">Todas as situações</option><option value="irregular">Irregular</option>
                   <option value="atencao">Atenção</option><option value="regular">Regular</option>
                 </select>}>
    <ComDados estado={lista} vazio={l => l.itens.length === 0} textoVazio="Nenhum trabalhador encontrado. Envie um lote com ASO, CTPS ou ficha de EPI.">
      {l => <div className="grid gap-6 lg:grid-cols-5">
        <div className="lg:col-span-2 space-y-2">
          {l.itens.map(t => <button key={t.id} type="button" onClick={() => setAberto(t.id)}
                                    className={`w-full rounded-xl border p-4 text-left text-sm ${aberto === t.id ? 'border-indigo-300 bg-indigo-50' : 'border-slate-100 bg-white hover:bg-slate-50'}`}>
            <div className="flex items-center justify-between gap-2">
              <span className="font-bold text-slate-800">{t.rotulo}</span><Selo valor={t.situacao} />
            </div>
            <p className="mt-1 text-xs text-slate-500">{t.funcao || 'função não identificada'} · {t.pendencias} pendência(s) · {t.vencidos} vencido(s) · {t.vencendo} vencendo</p>
            {t.faltando.length > 0 && <p className="mt-1 text-xs text-rose-700">Faltando: {t.faltando.map(f => f.replace('CERTIFICADO_NR:', 'Certificado ')).join(', ')}</p>}
          </button>)}
        </div>
        <div className="lg:col-span-3">
          {aberto ? <Dossie id={aberto} funcoes={l.funcoes} aoMudar={lista.recarregar} />
            : <p className="rounded-xl border border-dashed border-slate-200 bg-white p-6 text-sm text-slate-500">Selecione um trabalhador para ver o dossiê.</p>}
          {aberto && <button type="button" className={`${botao} mt-3`} onClick={() => setAberto(null)}>Fechar dossiê</button>}
        </div>
      </div>}
    </ComDados>
  </Layout>;
}
