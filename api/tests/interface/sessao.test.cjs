const { test } = require('node:test');
const assert = require('node:assert/strict');
const { criarCliente } = require('../../static/painel-sessao.js');
const operador = { api_key: 'chave-teste-A', tenant_id: 'empresa-A', role: 'OPERATOR' };
const leitor = { ...operador, role: 'VIEWER' };
const resposta = (body = '{}', status = 200, type = 'application/json') => new Response(body, { status, headers: { 'Content-Type': type } });
const diferida = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };

test('sem sessao nao consulta a API', async () => {
    let chamadas = 0;
    const c = criarCliente({ fetcher: async () => { chamadas++; return resposta(); } });
    await assert.rejects(c.request('/api/v1/logistica/veiculos'), { status: 401 });
    assert.equal(chamadas, 0);
});
test('leitor nao envia gravacao, mas pode consultar rota por POST', async () => {
    const caminhos = [];
    const c = criarCliente({ fetcher: async p => { caminhos.push(p); return resposta(); } }); c.entrar(leitor);
    await assert.rejects(c.request('/api/v1/logistica/veiculos', { method: 'POST' }), { status: 403 });
    await c.request('/api/v1/infraestrutura/rota-caminhao', { method: 'POST' });
    assert.deepEqual(caminhos, ['/api/v1/infraestrutura/rota-caminhao']);
});
test('chave usada vem da sessao e transporte recusa redirecionamento', async () => {
    let opcoes;
    const c = criarCliente({ fetcher: async (_, o) => { opcoes = o; return resposta(); } }); c.entrar(operador);
    await c.request('/api/v1/logistica/veiculos', { headers: { 'X-API-Key': 'outra-chave' } });
    assert.equal(opcoes.headers.get('X-API-Key'), operador.api_key);
    assert.equal(opcoes.redirect, 'error'); assert.equal(opcoes.cache, 'no-store');
});
test('credencial nao pode ser enviada a endereco externo', async () => {
    const c = criarCliente({ fetcher: async () => { throw Error('Nao deveria consultar'); } }); c.entrar(operador);
    await assert.rejects(c.request('https://example.org/api/v1/teste'), /Endereço/);
    await assert.rejects(c.request('/api/v1/\\example.org'), /Endereço/);
});
test('401 autenticado encerra a sessao e informa novo login', async () => {
    const motivos = [];
    const c = criarCliente({ fetcher: async () => resposta('{}', 401), aoEncerrar: m => motivos.push(m) }); c.entrar(operador);
    await assert.rejects(c.request('/api/v1/logistica/veiculos'), { status: 401, silencioso: true });
    assert.equal(c.perfil(), null); assert.match(motivos.at(-1), /Entre novamente/);
});
test('login incorreto nao inclui chave e nao se apresenta como falha de rede', async () => {
    let headers;
    const c = criarCliente({ fetcher: async (_, o) => { headers = o.headers; return resposta('{}', 401); } });
    await assert.rejects(c.request('/api/v1/logistica/auth/login', { publico: true, method: 'POST', headers: { 'X-API-Key': 'nao-enviar' } }), /senha inválidos/);
    assert.equal(headers.has('X-API-Key'), false);
});
test('resposta atrasada de outra empresa e descartada sem encerrar a conta nova', async () => {
    const gate = diferida();
    const c = criarCliente({ fetcher: () => gate.promise }); c.entrar(operador);
    const pending = c.request('/api/v1/logistica/veiculos');
    c.encerrar(); c.entrar({ ...operador, tenant_id: 'empresa-B', api_key: 'chave-B' });
    gate.resolve(resposta('{}', 401));
    await assert.rejects(pending, { silencioso: true }); assert.equal(c.empresa(), 'empresa-B');
});
test('logout durante leitura do corpo tambem descarta o resultado', async () => {
    const gate = diferida(), iniciado = diferida();
    const c = criarCliente({ fetcher: async () => ({ status: 200, ok: true,
        arrayBuffer() { iniciado.resolve(); return gate.promise; } }) }); c.entrar(operador);
    const pending = c.request('/api/v1/logistica/veiculos'); await iniciado.promise;
    c.encerrar(); gate.resolve(new TextEncoder().encode('{"privado":true}').buffer);
    await assert.rejects(pending, { silencioso: true });
});
test('erro interno nao expoe detalhes devolvidos pelo servidor', async () => {
    const c = criarCliente({ fetcher: async () => resposta('{"detail":"senha-do-banco-nao-pode-aparecer"}', 500) }); c.entrar(operador);
    await assert.rejects(c.request('/api/v1/logistica/veiculos'), e => e.status === 500 && !e.message.includes('senha-do-banco'));
});
test('timeout cancela transporte e fornece mensagem recuperavel', async () => {
    const c = criarCliente({ timeoutMs: 5, fetcher: (_, o) => new Promise((_, reject) => {
        o.signal.addEventListener('abort', () => reject(new DOMException('Abortado', 'AbortError')));
    }) }); c.entrar(operador);
    await assert.rejects(c.request('/api/v1/logistica/veiculos'), /demorou/);
});
test('cancelamento externo nao vira erro de conexao', async () => {
    const controller = new AbortController();
    const c = criarCliente({ fetcher: (_, o) => new Promise((_, reject) => {
        o.signal.addEventListener('abort', () => reject(new DOMException('Abortado', 'AbortError')));
    }) }); c.entrar(operador);
    const pending = c.request('/api/v1/logistica/veiculos', { signal: controller.signal }); controller.abort();
    await assert.rejects(pending, { silencioso: true });
});
test('CSV mantem bytes e formato; resposta vazia 204 e aceita', async () => {
    const c = criarCliente({ fetcher: async p => p.endsWith('/csv') ? resposta('id;nome\n1;São Paulo', 200, 'text/csv') : resposta(null, 204) });
    c.entrar(operador);
    const csv = await c.request('/api/v1/logistica/csv');
    assert.equal(await csv.text(), 'id;nome\n1;São Paulo'); assert.equal(csv.headers.get('Content-Type'), 'text/csv');
    assert.equal((await c.request('/api/v1/logistica/vazio')).status, 204);
});
test('sessao incompleta nao e aceita', () => {
    const c = criarCliente({ fetcher: async () => resposta() });
    assert.throws(() => c.entrar({ role: 'ADMIN', api_key: 'sem-empresa' }), /incompleta/);
});
