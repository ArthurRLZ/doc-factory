// "Ver acerto": compara o lote com o gabarito (GET /lotes/{id}/avaliacao). Erros silenciosos em destaque.
import { Cartao, ComDados } from '../Estados';
import useApi from '../../hooks/useApi';
import api from '../../services/api';
import { pct } from '../../utils/formatar';

export default function PainelAcerto({ loteId }) {
  const av = useApi(() => api.get(`/lotes/${loteId}/avaliacao`).then(r => r.data), [loteId]);
  return <ComDados estado={av}>
    {({ metricas: m, aviso }) => <Cartao titulo="Acerto contra o gabarito"
                                         subtitulo={`${m.totais.gabarito} documento(s) no gabarito · ${m.totais.previstos} encontrados pelo sistema`}>
      <div className="grid gap-3 text-sm sm:grid-cols-4">
        {[['Cortes (F1)', m.corte_f1], ['Documentos exatos', m.documentos_exatos_pct], ['Tipo certo', m.tipo_acerto_pct],
          ['Aprovados sem revisão', m.automatizados_pct]].map(([rotulo, v]) => <div key={rotulo} className="rounded-xl bg-slate-50 p-3">
          <p className="text-xs text-slate-500">{rotulo}</p><p className="text-xl font-extrabold text-slate-900">{pct(v)}</p></div>)}
      </div>
      <div className={`mt-4 rounded-xl p-4 text-sm ${m.erros_silenciosos.length ? 'bg-rose-50 text-rose-800' : 'bg-emerald-50 text-emerald-800'}`}>
        <strong>{m.erros_silenciosos.length} erro(s) silencioso(s)</strong> — documento(s) aprovado(s) automaticamente que estão errados
        {m.erros_silenciosos.map(e => <p key={e.id} className="mt-1 text-xs">{e.tipo_previsto} · páginas {e.paginas.map(n => n + 1).join(', ')}</p>)}
      </div>
      {m.detalhes.length > 0 && <ul className="mt-3 list-disc pl-5 text-xs text-slate-600">{m.detalhes.map(d => <li key={d}>{d}</li>)}</ul>}
      {aviso && <p className="mt-3 text-xs text-amber-700">{aviso}</p>}
    </Cartao>}
  </ComDados>;
}
