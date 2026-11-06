// Formatação e textos comuns das telas (tudo em português).

export function mensagemDeErro(e, padrao = 'Não foi possível acessar o servidor.') {
  const d = e?.response?.data;
  if (typeof d?.detail === 'string') return d.detail;
  if (typeof d?.erro?.mensagem === 'string') return d.erro.mensagem;
  if (typeof d?.detail?.mensagem === 'string') return d.detail.mensagem;
  if (Array.isArray(d?.detail) && d.detail[0]?.msg) return d.detail[0].msg.replace(/^Value error, /, '');
  if (e?.response?.status === 401) return 'Sua sessão expirou. Entre novamente.';
  if (e?.response?.status === 403) return 'Seu perfil não tem permissão para esta ação.';
  return padrao;
}

export const pct = (v) => (v === null || v === undefined ? '—' : `${Number(v).toLocaleString('pt-BR', { maximumFractionDigits: 1 })}%`);
export const num = (v) => (v === null || v === undefined ? '—' : Number(v).toLocaleString('pt-BR'));

export function data(iso) {
  if (!iso) return '—';
  const [a, m, d] = String(iso).slice(0, 10).split('-');
  return d ? `${d}/${m}/${a}` : iso;
}

export function dataHora(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
}

export function prazo(dias) {
  if (dias === null || dias === undefined) return 'sem validade';
  if (dias < 0) return `venceu há ${Math.abs(dias)} dia(s)`;
  if (dias === 0) return 'vence hoje';
  return `vence em ${dias} dia(s)`;
}

// rotas que o /painel devolve (contrato da API) → rotas desta interface
export function rotaDaTela(rota) {
  if (!rota) return '/';
  if (rota.startsWith('/revisao/fila')) return '/fila-revisao';
  return rota;
}

export const CORES_SITUACAO = {
  aprovado: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  ok: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  vigente: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  regular: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  confiavel: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  auto_aprovado: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  revisado: 'bg-indigo-50 text-indigo-700 border-indigo-200',
  reprovado: 'bg-rose-50 text-rose-700 border-rose-200',
  vencido: 'bg-rose-50 text-rose-700 border-rose-200',
  faltando: 'bg-rose-50 text-rose-700 border-rose-200',
  irregular: 'bg-rose-50 text-rose-700 border-rose-200',
  alto_risco: 'bg-rose-50 text-rose-700 border-rose-200',
  em_analise: 'bg-amber-50 text-amber-800 border-amber-200',
  vencendo: 'bg-amber-50 text-amber-800 border-amber-200',
  atencao: 'bg-amber-50 text-amber-800 border-amber-200',
  pendente: 'bg-amber-50 text-amber-800 border-amber-200',
  nao_enviado: 'bg-slate-100 text-slate-700 border-slate-200',
};

export const ROTULOS = {
  aprovado: 'Aprovado', reprovado: 'Reprovado', em_analise: 'Em análise', nao_enviado: 'Não enviado',
  ok: 'OK', vigente: 'Vigente', vencendo: 'Vencendo', vencido: 'Vencido', faltando: 'Faltando',
  regular: 'Regular', irregular: 'Irregular', atencao: 'Atenção', alto_risco: 'Alto risco', confiavel: 'Confiável',
  pendente: 'Pendente', auto_aprovado: 'Aprovado automaticamente', revisado: 'Revisado', sem_validade: 'Sem validade',
  indeterminado: 'Validade não identificada',
};

// avisa o menu lateral que a fila de revisão mudou (atualiza o contador na hora)
export function avisarFilaMudou() {
  window.dispatchEvent(new Event('fila-revisao-mudou'));
}
