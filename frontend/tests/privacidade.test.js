import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  categoriasSensiveis,
  linhasIdentificadores,
  mensagemDeErro,
  nivelDoRelatorio,
  NIVEIS,
  nomeArquivoRelatorio,
} from '../src/services/privacidade.js';

// Resposta REAL de GET /lotes/{id}/privacidade (lote de terceiros do projeto, passou por OCR e anonimização).
// Se o backend mudar o formato, este teste quebra aqui e não na tela.
const real = JSON.parse(readFileSync(new URL('./fixtures/relatorio-privacidade.json', import.meta.url), 'utf8'));

test('nível de risco: conhecido, e desconhecido cai no médio (nunca esconde nem exagera)', () => {
  assert.equal(nivelDoRelatorio(real), NIVEIS.alto);
  assert.equal(nivelDoRelatorio({ nivel_risco: 'baixo' }).rotulo, 'Risco baixo');
  assert.equal(nivelDoRelatorio({ nivel_risco: 'novo-nivel' }), NIVEIS.medio);
  assert.equal(nivelDoRelatorio(undefined), NIVEIS.medio);
});

test('identificadores: só os que apareceram, do mais frequente ao menos', () => {
  const linhas = linhasIdentificadores(real);
  assert.ok(linhas.length > 0 && linhas.every((l) => l.ocorrencias > 0));
  assert.deepEqual(linhas.map((l) => l.ocorrencias), [...linhas.map((l) => l.ocorrencias)].sort((a, b) => b - a));
  const cpf = linhas.find((l) => l.codigo === 'CPF');
  assert.equal(cpf.ocorrencias, 11);
  assert.equal(cpf.pessoas, 2);                               // só o CPF traz "pessoas distintas"
  assert.equal(linhas.find((l) => l.codigo !== 'CPF').pessoas, null);
  assert.deepEqual(linhasIdentificadores({}), []);
});

test('categorias sensíveis: inclui as sem achado, para mostrar "nada detectado"', () => {
  const cats = categoriasSensiveis(real);
  assert.deepEqual(cats.map((c) => c.codigo), ['SAUDE', 'BIOMETRIA', 'SINDICAL']);
  const saude = cats.find((c) => c.codigo === 'SAUDE');
  assert.equal(saude.documentos, 2);
  assert.deepEqual(saude.porTipo, [['ASO', 2]]);
  assert.equal(cats.find((c) => c.codigo === 'BIOMETRIA').documentos, 0);
});

test('nome do arquivo do relatório: sem acento, sem extensão, sem caracteres perigosos', () => {
  assert.equal(nomeArquivoRelatorio(real), 'privacidade-terceiros-marco.json');
  assert.equal(nomeArquivoRelatorio({ lote: '../../etc/passwd.pdf' }), 'privacidade-etc-passwd.json');
  assert.equal(nomeArquivoRelatorio({ lote: '???.pdf' }), 'privacidade-lote.json');
  assert.equal(nomeArquivoRelatorio({}), 'privacidade-lote.json');
});

test('mensagem de erro: usa a do backend; sem ela, a padrão', () => {
  assert.equal(mensagemDeErro({ response: { data: { erro: { mensagem: 'Lote ainda não concluído' } } } }, 'padrão'), 'Lote ainda não concluído');
  assert.equal(mensagemDeErro({ response: { data: {} } }, 'padrão'), 'padrão');
  assert.equal(mensagemDeErro(new Error('rede'), 'padrão'), 'padrão');
});

test('o relatório real não carrega dado pessoal (CPF, e-mail, telefone)', () => {
  const texto = JSON.stringify(real);
  assert.doesNotMatch(texto, /\d{3}\.\d{3}\.\d{3}-\d{2}|\b\d{11}\b|@/);
});
