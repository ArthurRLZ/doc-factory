// Regras de separação escritas em português: entender (sem gravar), salvar, ativar/desativar, remover.
import { useState } from 'react';
import Layout from '../../components/Layout';
import { Cartao, ComDados, Erro, Selo, botao, botaoPrimario, campo } from '../../components/Estados';
import useApi from '../../hooks/useApi';
import api from '../../services/api';
import { dataHora, mensagemDeErro } from '../../utils/formatar';

const EXEMPLOS = ['mantenha o contrato inteiro junto', 'cada guia do FGTS é um documento separado', 'página em branco não separa documentos'];
const POR = { ia: 'entendida pela IA', palavras_chave: 'entendida por palavras-chave' };

export default function Regras() {
  const lista = useApi(() => api.get('/regras-separacao').then(r => r.data), []);
  const [texto, setTexto] = useState('');
  const [entendido, setEntendido] = useState(null);
  const [erro, setErro] = useState('');

  async function entender() {
    setErro(''); setEntendido(null);
    try { setEntendido((await api.post('/regras-separacao/interpretar', { texto })).data); }
    catch (e) {
      const ex = e.response?.data?.exemplos;
      setErro(mensagemDeErro(e, 'Não entendi a regra.') + (ex ? ` Exemplos: ${ex.join('; ')}.` : ''));
    }
  }

  async function executar(fn) {
    setErro('');
    try { await fn(); lista.recarregar(); } catch (e) { setErro(mensagemDeErro(e)); }
  }

  return <Layout titulo="Regras de separação" subtitulo="Ensine o sistema a separar os documentos escrevendo em português. Vale para os próximos lotes.">
    <Cartao titulo="Nova regra">
      <div className="space-y-3">
        <label htmlFor="regra" className="text-xs font-semibold text-slate-700">Escreva uma regra em português</label>
        <input id="regra" className={`${campo} w-full`} value={texto} onChange={e => { setTexto(e.target.value); setEntendido(null); }}
               placeholder="ex.: mantenha o contrato inteiro junto" />
        <div className="flex flex-wrap gap-2 text-xs">
          {EXEMPLOS.map(ex => <button key={ex} type="button" className="rounded-full bg-slate-100 px-3 py-1 text-slate-600 hover:bg-slate-200"
                                      onClick={() => { setTexto(ex); setEntendido(null); }}>{ex}</button>)}
        </div>
        <div className="flex gap-2">
          <button type="button" className={botao} disabled={texto.trim().length < 3} onClick={entender}>Entender</button>
          <button type="button" className={botaoPrimario} disabled={!entendido}
                  onClick={() => executar(async () => { await api.post('/regras-separacao', { texto }); setTexto(''); setEntendido(null); })}>Salvar</button>
        </div>
        {entendido && <div className="rounded-xl bg-indigo-50 p-3 text-sm text-indigo-900">
          Entendi assim: <strong>{entendido.regras.map(r => r.descricao).join('; ')}</strong>
          <span className="text-xs text-indigo-600"> ({POR[entendido.interpretada_por]})</span>
        </div>}
        {erro && <Erro mensagem={erro} />}
      </div>
    </Cartao>
    <Cartao titulo="Regras cadastradas" subtitulo="Cada lote guarda as regras ativas no envio; para aplicar em lote antigo, reprocesse com “atualizar regras”.">
      <ComDados estado={lista} vazio={l => l.length === 0} textoVazio="Nenhuma regra cadastrada: a separação segue o comportamento padrão.">
        {l => <div className="divide-y divide-slate-100">
          {l.map(r => <div key={r.id} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm">
            <div>
              <p className="font-semibold text-slate-800">“{r.texto}”</p>
              <p className="text-xs text-slate-500">{r.regras.map(x => x.descricao).join('; ')} · {POR[r.interpretada_por]} · {r.criada_por} · {dataHora(r.criado_em)}</p>
            </div>
            <div className="flex items-center gap-2">
              <Selo valor={r.ativa ? 'aprovado' : 'nao_enviado'} texto={r.ativa ? 'Ativa' : 'Inativa'} />
              <button type="button" className={botao} onClick={() => executar(() => api.post(`/regras-separacao/${r.id}/${r.ativa ? 'desativar' : 'ativar'}`))}>
                {r.ativa ? 'Desativar' : 'Ativar'}</button>
              <button type="button" className={botao} onClick={() => executar(() => api.delete(`/regras-separacao/${r.id}`))}>Remover</button>
            </div>
          </div>)}
        </div>}
      </ComDados>
    </Cartao>
  </Layout>;
}
