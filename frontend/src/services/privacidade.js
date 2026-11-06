// src/services/privacidade.js
// Relatório de risco de privacidade de um lote (GET /lotes/{id}/privacidade).
// Funções puras à parte da chamada de API, para testar sem navegador.
import api from './api.js';

export function buscarRelatorioPrivacidade(loteId) {
  return api.get(`/lotes/${encodeURIComponent(loteId)}/privacidade`).then((r) => r.data);
}

// O texto sempre acompanha a cor: quem não distingue cores (ou imprime em preto e branco) lê o mesmo alerta.
export const NIVEIS = {
  alto: { rotulo: 'Risco alto', classe: 'bg-rose-50 text-rose-700 border-rose-200' },
  medio: { rotulo: 'Risco médio', classe: 'bg-amber-50 text-amber-700 border-amber-200' },
  baixo: { rotulo: 'Risco baixo', classe: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
};

// Nível desconhecido (backend mais novo que o front) cai no médio: nunca esconde nem exagera.
export function nivelDoRelatorio(relatorio) {
  return NIVEIS[relatorio?.nivel_risco] ?? NIVEIS.medio;
}

// Só os identificadores que apareceram no lote, do mais frequente ao menos.
export function linhasIdentificadores(relatorio) {
  return Object.entries(relatorio?.identificadores ?? {})
    .map(([codigo, d]) => ({
      codigo,
      nome: d.nome ?? codigo,
      ocorrencias: d.ocorrencias ?? 0,
      documentos: d.documentos ?? 0,
      pessoas: d.pessoas_distintas ?? null,
    }))
    .filter((l) => l.ocorrencias > 0)
    .sort((a, b) => b.ocorrencias - a.ocorrencias || a.nome.localeCompare(b.nome, 'pt-BR'));
}

// Categorias sensíveis na ordem do backend, com ou sem ocorrência (para mostrar "nada detectado").
export function categoriasSensiveis(relatorio) {
  return Object.entries(relatorio?.dados_sensiveis ?? {}).map(([codigo, d]) => ({
    codigo,
    nome: d.nome ?? codigo,
    documentos: d.documentos ?? 0,
    porTipo: Object.entries(d.por_tipo ?? {}),
    termos: d.termos_mais_frequentes ?? [],
  }));
}

export function nomeArquivoRelatorio(relatorio) {
  const base = String(relatorio?.lote ?? 'lote')
    .replace(/\.[^.]+$/, '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return `privacidade-${base || 'lote'}.json`;
}

export function mensagemDeErro(e, padrao) {
  return e?.response?.data?.erro?.mensagem || padrao;
}
