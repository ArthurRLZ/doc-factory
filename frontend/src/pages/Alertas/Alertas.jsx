// Alertas de vencimento: estado, contatos (e-mail/WhatsApp), prévia, execução simulada e histórico.
import { useState } from 'react';
import Layout from '../../components/Layout';
import { Cartao, ComDados, Erro, Selo, botao, botaoPrimario, campo } from '../../components/Estados';
import useApi from '../../hooks/useApi';
import api from '../../services/api';
import { dataHora, mensagemDeErro } from '../../utils/formatar';

function NovoContato({ aoCriar }) {
  const [form, setForm] = useState({ nome: '', canal: 'whatsapp', destino: '' });
  const [erro, setErro] = useState('');
  async function salvar(e) {
    e.preventDefault(); setErro('');
    try { await api.post('/alertas/contatos', form); setForm({ ...form, nome: '', destino: '' }); aoCriar(); }
    catch (er) { setErro(mensagemDeErro(er, 'Não foi possível salvar o contato.')); }
  }
  return <form onSubmit={salvar} className="flex flex-wrap items-end gap-2">
    <label className="text-xs text-slate-600">Nome<input className={`${campo} block`} value={form.nome} onChange={e => setForm({ ...form, nome: e.target.value })} required /></label>
    <label className="text-xs text-slate-600">Canal<select className={`${campo} block`} value={form.canal} onChange={e => setForm({ ...form, canal: e.target.value })}>
      <option value="whatsapp">WhatsApp</option><option value="email">E-mail</option></select></label>
    <label className="text-xs text-slate-600">{form.canal === 'email' ? 'E-mail' : 'Telefone (só dígitos, com DDI)'}
      <input className={`${campo} block`} placeholder={form.canal === 'email' ? 'gestor@empresa.com' : '5581999999999'}
             value={form.destino} onChange={e => setForm({ ...form, destino: e.target.value })} required /></label>
    <button className={botaoPrimario} type="submit">Adicionar contato</button>
    {erro && <div className="w-full"><Erro mensagem={erro} /></div>}
  </form>;
}

export default function Alertas() {
  const dados = useApi(() => Promise.all([api.get('/alertas/config'), api.get('/alertas/contatos'), api.get('/alertas/historico')])
    .then(([c, k, h]) => ({ config: c.data, contatos: k.data, historico: h.data })), []);
  const [previa, setPrevia] = useState(null);
  const [resultado, setResultado] = useState('');
  const [erro, setErro] = useState('');

  async function acao(fn, sucesso) {
    setErro(''); setResultado('');
    try { const r = await fn(); if (sucesso) setResultado(sucesso(r.data)); dados.recarregar(); }
    catch (e) { setErro(mensagemDeErro(e)); }
  }

  return <Layout titulo="Alertas de vencimento" subtitulo="O sistema avisa sozinho quem cuida dos contratos, antes de o documento vencer.">
    {erro && <Erro mensagem={erro} />}
    {resultado && <div role="status" className="rounded-xl bg-emerald-50 p-4 text-sm text-emerald-800">{resultado}</div>}
    <ComDados estado={dados}>
      {d => <>
        <Cartao titulo="Estado" subtitulo="Configurado no servidor (.env); senhas e chaves nunca aparecem aqui">
          <div className="flex flex-wrap gap-3 text-xs text-slate-700">
            <Selo valor={d.config.modo === 'real' ? 'aprovado' : 'em_analise'} texto={d.config.modo === 'real' ? 'Modo real (envia de verdade)' : 'Modo simulado (não envia nada)'} />
            <Selo valor={d.config.ativo ? 'aprovado' : 'nao_enviado'} texto={d.config.ativo ? `Envio automático diário às ${d.config.hora_execucao}h` : 'Envio automático desligado'} />
            <span>Faixas: {d.config.faixas.join(', ')} dia(s) antes + vencidos</span>
            <span>E-mail: {d.config.canais_configurados.email ? 'configurado' : 'não configurado'}</span>
            <span>WhatsApp: {d.config.canais_configurados.whatsapp ? 'configurado' : 'não configurado'}</span>
          </div>
        </Cartao>

        <Cartao titulo="Contatos" subtitulo="Pessoas da empresa que recebem o resumo (nunca o trabalhador)">
          <div className="space-y-4">
            <NovoContato aoCriar={dados.recarregar} />
            {d.contatos.length === 0 ? <p className="text-xs text-slate-500">Nenhum contato cadastrado.</p> :
              <div className="divide-y divide-slate-100">
                {d.contatos.map(c => <div key={c.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                  <span><strong>{c.nome}</strong> · {c.canal === 'email' ? 'E-mail' : 'WhatsApp'} · {c.destino}</span>
                  <span className="flex gap-2">
                    <button type="button" className={botao} onClick={() => acao(() => api.post(`/alertas/contatos/${c.id}/testar`),
                      r => r.simulado ? 'Teste registrado (modo simulado: nada foi enviado).' : 'Mensagem de teste enviada.')}>Enviar teste</button>
                    <button type="button" className={botao} aria-label={`Remover ${c.nome}`} onClick={() => acao(() => api.delete(`/alertas/contatos/${c.id}`))}>Remover</button>
                  </span>
                </div>)}
              </div>}
          </div>
        </Cartao>

        <Cartao titulo="Envio" acoes={<div className="flex gap-2">
          <button type="button" className={botao} onClick={() => acao(() => api.get('/alertas/pendentes').then(r => { setPrevia(r.data); return r; }))}>Ver o que seria enviado agora</button>
          <button type="button" className={botaoPrimario} onClick={() => acao(() => api.post('/alertas/executar', null, { params: { simular: true } }),
            r => `Simulação: ${r.mensagens} mensagem(ns) para ${r.contatos} contato(s), ${r.itens} documento(s). Rodar de novo não repete.`)}>Executar agora (simulado)</button>
        </div>}>
          {previa === null ? <p className="text-xs text-slate-500">Clique em “Ver o que seria enviado agora” para a prévia (não envia nem grava nada).</p>
            : previa.length === 0 ? <p className="text-xs text-slate-500">Nada novo para avisar (ou nenhum contato ativo).</p>
            : previa.map(p => <div key={p.contato_id} className="mb-3 rounded-xl bg-slate-50 p-4">
              <p className="text-xs font-bold text-slate-700">Para {p.contato} ({p.canal}) · {p.itens.length} documento(s)</p>
              <pre className="mt-2 whitespace-pre-wrap text-xs text-slate-700">{p.texto}</pre>
            </div>)}
        </Cartao>

        <Cartao titulo="Histórico" subtitulo="Últimos avisos registrados">
          {d.historico.length === 0 ? <p className="text-xs text-slate-500">Nenhum aviso ainda.</p> :
            <table className="w-full text-left text-xs"><thead className="text-[10px] uppercase tracking-wider text-slate-400">
              <tr><th className="py-2">Quando</th><th>Documento</th><th>Faixa</th><th>Contato</th><th>Status</th></tr></thead>
              <tbody className="divide-y divide-slate-100">{d.historico.map(h => <tr key={h.id}>
                <td className="py-2">{dataHora(h.enviado_em)}</td><td>{h.tipo_nome}</td><td>{h.faixa === 'vencido' ? 'vencido' : `${h.faixa} dia(s)`}</td>
                <td>{h.contato} ({h.canal})</td>
                <td><Selo valor={h.status === 'falhou' ? 'reprovado' : 'aprovado'} texto={h.status} title={h.erro || undefined} /></td>
              </tr>)}</tbody></table>}
        </Cartao>
      </>}
    </ComDados>
  </Layout>;
}
