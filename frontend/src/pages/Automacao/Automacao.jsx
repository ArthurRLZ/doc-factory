// Meta de automação: limiar em tempo real, curva automação × revisão, sugestão por meta e aprendizados.
import { useEffect, useRef, useState } from 'react';
import Layout from '../../components/Layout';
import { Cartao, ComDados, Erro, Selo, botao, campo } from '../../components/Estados';
import useApi from '../../hooks/useApi';
import api from '../../services/api';
import { avisarFilaMudou, dataHora, mensagemDeErro, num, pct } from '../../utils/formatar';

function Limiar({ atual, aoMudar }) {
  const [valor, setValor] = useState(atual);
  const [erro, setErro] = useState('');
  const timer = useRef(null);
  useEffect(() => () => clearTimeout(timer.current), []);

  function mudar(v) {
    setValor(v);
    clearTimeout(timer.current);
    timer.current = setTimeout(async () => {     // espera o usuário parar de arrastar antes de gravar
      try { await api.put('/automacao/limiar', { limiar: v }); setErro(''); avisarFilaMudou(); aoMudar(); }
      catch (e) { setErro(mensagemDeErro(e, 'Não foi possível mudar o limiar.')); }
    }, 600);
  }

  return <div className="space-y-2">
    <label htmlFor="limiar" className="text-xs font-semibold text-slate-700">
      Confiança mínima para aprovar sem revisão: <strong>{pct(valor * 100)}</strong>
    </label>
    <input id="limiar" type="range" min="0.5" max="0.99" step="0.01" value={valor} onChange={e => mudar(Number(e.target.value))} className="w-full" />
    <p className="text-[11px] text-slate-400">Limiar menor = mais automação; os documentos ainda não revisados por uma pessoa são reavaliados na hora.</p>
    {erro && <Erro mensagem={erro} />}
  </div>;
}

function Sugerir() {
  const [meta, setMeta] = useState(95);
  const [r, setR] = useState(null);
  const [erro, setErro] = useState('');
  async function pedir() {
    setErro('');
    try { setR((await api.get('/automacao/sugerir', { params: { meta } })).data); }
    catch (e) { setErro(mensagemDeErro(e)); }
  }
  return <div className="space-y-2">
    <div className="flex flex-wrap items-center gap-2">
      <label htmlFor="meta" className="text-xs text-slate-700">Meta de acerto (%)</label>
      <input id="meta" className={`${campo} w-20`} type="number" min="50" max="100" value={meta} onChange={e => setMeta(Number(e.target.value))} />
      <button type="button" className={botao} onClick={pedir}>Sugerir limiar para a meta</button>
    </div>
    {r && <p className="text-xs text-slate-700">{r.limiar_sugerido !== null
      ? `Limiar sugerido: ${pct(r.limiar_sugerido * 100)} — ${pct(r.ponto.percentual_automatico)} automático, acerto estimado ${pct(r.ponto.acuracia_estimada)}.`
      : r.observacao}</p>}
    {erro && <Erro mensagem={erro} />}
  </div>;
}

export default function Automacao() {
  const dados = useApi(() => Promise.all([api.get('/automacao'), api.get('/aprendizados')])
    .then(([a, b]) => ({ ...a.data, aprendizados: b.data })), []);
  const [erro, setErro] = useState('');

  async function desativar(id) {
    try { await api.post(`/aprendizados/${id}/desativar`); dados.recarregar(); }
    catch (e) { setErro(mensagemDeErro(e, 'Não foi possível desativar.')); }
  }

  return <Layout titulo="Automação" subtitulo="Quanto vai sozinho e quanto passa por uma pessoa — com o acerto medido nas revisões.">
    {erro && <Erro mensagem={erro} />}
    <ComDados estado={dados}>
      {d => <>
        <div className="grid gap-6 lg:grid-cols-2">
          <Cartao titulo="Limiar de revisão" subtitulo={`Padrão do sistema: ${pct(d.limiar_padrao * 100)} · ${num(d.documentos)} documento(s)`}>
            <Limiar key={d.limiar_atual} atual={d.limiar_atual} aoMudar={dados.recarregar} />
          </Cartao>
          <Cartao titulo="Acerto medido" subtitulo="Pelas revisões humanas já feitas">
            <p className="text-2xl font-extrabold text-slate-900">{pct(d.acuracia_medida.percentual)}</p>
            <p className="text-xs text-slate-500">{num(d.acuracia_medida.corretos)} de {num(d.acuracia_medida.documentos_revisados)} revisados estavam certos</p>
            {d.acuracia_medida.observacao && <p className="mt-1 text-xs text-amber-700">{d.acuracia_medida.observacao}</p>}
            {d.pre_revisao && <p className="mt-3 text-xs text-slate-600">Sugestões da pré-revisão seguidas pelos revisores: <strong>{pct(d.pre_revisao.percentual)}</strong> ({num(d.pre_revisao.seguidas)} de {num(d.pre_revisao.revisoes_com_sugestao)})</p>}
            <div className="mt-4"><Sugerir /></div>
          </Cartao>
        </div>
        <Cartao titulo="Curva automação × revisão" subtitulo="Para cada limiar: quantos documentos passariam sozinhos">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-[10px] uppercase tracking-wider text-slate-400"><tr>
                <th className="py-2">Limiar</th><th>Automáticos</th><th>Para revisão</th><th className="w-1/3">% automático</th><th>Acerto estimado</th>
              </tr></thead>
              <tbody className="divide-y divide-slate-100">
                {d.curva.map(p => <tr key={p.limiar} className={p.atual ? 'bg-indigo-50 font-semibold' : ''}>
                  <td className="py-2">{pct(p.limiar * 100)}{p.atual && ' (atual)'}</td><td>{num(p.automaticos)}</td><td>{num(p.para_revisao)}</td>
                  <td><div className="flex items-center gap-2"><div className="h-2 flex-1 rounded-full bg-slate-100">
                    <div className="h-2 rounded-full bg-indigo-500" style={{ width: `${p.percentual_automatico}%` }} /></div>{pct(p.percentual_automatico)}</div></td>
                  <td>{p.acuracia_estimada === null ? `— (amostra ${p.amostra})` : pct(p.acuracia_estimada)}</td>
                </tr>)}
              </tbody>
            </table>
          </div>
        </Cartao>
        <Cartao titulo="Aprendizados" subtitulo="O que o sistema aprendeu com as correções de tipo feitas pelos revisores">
          {d.aprendizados.length === 0 ? <p className="text-xs text-slate-500">Nenhuma correção de tipo ainda.</p> :
            <div className="divide-y divide-slate-100">
              {d.aprendizados.map(a => <div key={a.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-xs">
                <span><strong>“{a.titulo}”</strong> → {a.tipo_certo} (antes {a.tipo_errado}) · por {a.usuario} · usado {a.usos}x · {dataHora(a.criado_em)}</span>
                {a.ativo ? <button type="button" className={botao} onClick={() => desativar(a.id)}>Desativar</button> : <Selo valor="nao_enviado" texto="Desativado" />}
              </div>)}
            </div>}
        </Cartao>
      </>}
    </ComDados>
  </Layout>;
}
