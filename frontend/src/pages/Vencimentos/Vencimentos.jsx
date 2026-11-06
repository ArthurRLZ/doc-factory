// Vencimentos: agrupados em vencidos, vencem em até 7 dias e em até 30 dias, com filtro por tipo.
import { useMemo, useState } from 'react';
import Layout from '../../components/Layout';
import { Cartao, ComDados, Selo, campo } from '../../components/Estados';
import useApi from '../../hooks/useApi';
import api from '../../services/api';
import { data, prazo } from '../../utils/formatar';

const GRUPOS = [
  { chave: 'vencidos', titulo: 'Vencidos', filtro: d => d < 0 },
  { chave: 'sete', titulo: 'Vencem em até 7 dias', filtro: d => d >= 0 && d <= 7 },
  { chave: 'trinta', titulo: 'Vencem em até 30 dias', filtro: d => d > 7 && d <= 30 },
];

export default function Vencimentos() {
  const [tipo, setTipo] = useState('');
  const venc = useApi(() => api.get('/vencimentos', { params: { ate_dias: 30 } }).then(r => r.data), []);
  const tipos = useMemo(() => [...new Map((venc.dados || []).map(d => [d.tipo, d.tipo_nome])).entries()], [venc.dados]);

  return <Layout titulo="Vencimentos" subtitulo="Documentos vencidos ou que vencem nos próximos 30 dias."
                 acoes={<select aria-label="Filtrar por tipo" className={campo} value={tipo} onChange={e => setTipo(e.target.value)}>
                   <option value="">Todos os tipos</option>
                   {tipos.map(([codigo, nome]) => <option key={codigo} value={codigo}>{nome}</option>)}
                 </select>}>
    <ComDados estado={venc} vazio={l => l.length === 0} textoVazio="Nenhum documento vencido ou vencendo nos próximos 30 dias.">
      {lista => {
        const filtrada = lista.filter(d => !tipo || d.tipo === tipo);
        return <div className="space-y-6">
          {GRUPOS.map(g => {
            const itens = filtrada.filter(d => d.validade?.dias_restantes !== null && g.filtro(d.validade.dias_restantes));
            return <Cartao key={g.chave} titulo={`${g.titulo} (${itens.length})`}>
              {itens.length === 0 ? <p className="text-xs text-slate-500">Nenhum.</p> :
                <div className="divide-y divide-slate-100">
                  {itens.map(d => <div key={d.id} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm">
                    <div>
                      <p className="font-semibold text-slate-800">{d.titulo || d.tipo_nome}</p>
                      <p className="text-xs text-slate-500">{d.tipo_nome}{d.trabalhador ? ` · ${d.trabalhador.rotulo}` : ' · empresa'} · validade {data(d.validade.data)}
                        {d.validade.evidencia && <span title={`Evidência: ${d.validade.evidencia}`} className="ml-1 cursor-help underline decoration-dotted">(prova)</span>}</p>
                    </div>
                    <div className="flex items-center gap-2"><span className="text-xs text-slate-600">{prazo(d.validade.dias_restantes)}</span><Selo valor={d.validade.status} /></div>
                  </div>)}
                </div>}
            </Cartao>;
          })}
        </div>;
      }}
    </ComDados>
  </Layout>;
}
