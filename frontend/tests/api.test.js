import test from 'node:test';
import assert from 'node:assert/strict';
import api from '../src/services/api.js';

test('mantém arquivos como FormData e envia dados comuns como JSON', async () => {
  globalThis.sessionStorage = { getItem: () => 'token-de-teste' };
  const chamadas = [];
  const adapter = async (config) => {
    chamadas.push(config);
    return { data: {}, status: 200, statusText: 'OK', headers: {}, config };
  };
  const arquivo = new FormData();
  arquivo.append('arquivo', new Blob(['teste']), 'teste.txt');
  await api.post('/lotes', arquivo, { adapter });
  await api.post('/auth/registrar', { login: 'teste' }, { adapter });
  const credenciais = new URLSearchParams({ username: 'teste', password: 'senha' });
  await api.post('/auth/login', credenciais, {
    adapter,
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  assert.ok(chamadas[0].data instanceof FormData);
  assert.notEqual(chamadas[0].headers.get('Content-Type'), 'application/json');
  assert.equal(chamadas[1].data, '{"login":"teste"}');
  assert.equal(chamadas[1].headers.get('Content-Type'), 'application/json');
  assert.equal(chamadas[2].headers.get('Content-Type'), 'application/x-www-form-urlencoded');
  assert.equal(chamadas[0].headers.get('Authorization'), 'Bearer token-de-teste');
  delete globalThis.sessionStorage;
});
