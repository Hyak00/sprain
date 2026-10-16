/* Sessao e transporte do painel. Sem persistir credenciais ou alterar permissoes da API. */
(function (root) {
    'use strict';
    class ErroPainel extends Error {
        constructor(message, status = 0, silencioso = false) {
            super(message); this.name = 'ErroPainel'; this.status = status; this.silencioso = silencioso;
        }
    }
    function criarCliente({ fetcher, aoEncerrar = () => {}, timeoutMs = 90000 } = {}) {
        let usuario = null, geracao = 0;
        const pendentes = new Set();
        const consultasPost = new Set(['/api/v1/infraestrutura/rota-caminhao', '/api/v1/infraestrutura/avaliar-mapa',
            '/api/v1/dados-publicos/consultar-rota', '/api/v1/transito/comparar']);
        function encerrar(motivo = '') {
            geracao++; usuario = null;
            pendentes.forEach(c => c.abort()); pendentes.clear(); aoEncerrar(motivo);
        }
        function entrar(dados) {
            if (!dados?.api_key || !dados.tenant_id || !['ADMIN', 'OPERATOR', 'VIEWER'].includes(dados.role)) {
                throw new ErroPainel('O servidor devolveu uma sessão incompleta. Entre novamente.');
            }
            encerrar(); usuario = { ...dados };
        }
        function podeEscrever() { return usuario?.role === 'ADMIN' || usuario?.role === 'OPERATOR'; }
        async function request(path, options = {}) {
            if (typeof path !== 'string' || !path.startsWith('/api/v1/') || /[\\\r\n]/.test(path)) {
                throw new ErroPainel('Endereço de consulta inválido.');
            }
            const { publico = false, timeout = timeoutMs, ...init } = options;
            if (!publico && !usuario) throw new ErroPainel('Entre na sua conta para continuar.', 401);
            const method = (init.method || 'GET').toUpperCase();
            if (!publico && !['GET', 'HEAD', 'OPTIONS'].includes(method) &&
                !(method === 'POST' && consultasPost.has(path.split('?')[0])) && !podeEscrever()) {
                throw new ErroPainel('Seu perfil permite apenas consultas.', 403);
            }
            const atual = geracao, controller = new AbortController();
            const sinalExterno = init.signal;
            const cancelar = () => controller.abort();
            if (sinalExterno?.aborted) cancelar();
            else sinalExterno?.addEventListener('abort', cancelar, { once: true });
            pendentes.add(controller);
            let expirou = false;
            const timer = setTimeout(() => { expirou = true; cancelar(); }, timeout);
            try {
                const headers = new Headers(init.headers);
                if (publico) headers.delete('X-API-Key');
                else headers.set('X-API-Key', usuario.api_key);
                const res = await fetcher(path, { ...init, headers, signal: controller.signal,
                    credentials: 'same-origin', redirect: 'error', cache: 'no-store' });
                // Consumir o corpo ainda sob o controle da sessao evita aplicar JSON/CSV
                // da conta anterior quando o logout ocorre depois dos cabecalhos.
                const buffer = await res.arrayBuffer();
                if (atual !== geracao || controller.signal.aborted) throw new ErroPainel('Consulta cancelada.', 0, true);
                if (buffer.byteLength > 20 * 1024 * 1024) throw new ErroPainel('Resultado muito grande. Reduza o período ou os filtros.');
                if (res.status === 401 && !publico) {
                    encerrar('Sua sessão foi encerrada ou perdeu a validade. Entre novamente.');
                    throw new ErroPainel('Entre novamente para continuar.', 401, true);
                }
                if (!res.ok) {
                    const mensagens = { 401: 'E-mail ou senha inválidos.', 403: 'Seu perfil não permite esta ação.',
                        404: 'Informação não encontrada ou fora da sua empresa.',
                        409: 'Os dados mudaram. Atualize a operação antes de confirmar.',
                        422: 'Confira os campos e as unidades informadas.',
                        429: 'Limite de consultas atingido. Aguarde antes de tentar novamente.',
                        503: publico ? 'Acesso corporativo ainda não configurado neste ambiente.' : 'Serviço temporariamente indisponível. Tente novamente.' };
                    throw new ErroPainel(mensagens[res.status] || 'Não foi possível concluir a consulta. Tente novamente.', res.status);
                }
                return new Response([204, 205].includes(res.status) ? null : buffer,
                    { status: res.status, statusText: res.statusText, headers: res.headers });
            } catch (error) {
                if (error instanceof ErroPainel) throw error;
                if (atual !== geracao || sinalExterno?.aborted) throw new ErroPainel('Consulta cancelada.', 0, true);
                throw new ErroPainel(expirou ? 'A consulta demorou além do esperado. Tente novamente.' :
                    'Não foi possível acessar o servidor. Verifique a conexão e tente novamente.');
            } finally {
                clearTimeout(timer); pendentes.delete(controller);
                sinalExterno?.removeEventListener('abort', cancelar);
            }
        }
        return { entrar, encerrar, request, podeEscrever,
            perfil: () => usuario?.role || null, empresa: () => usuario?.tenant_id || null };
    }
    if (typeof module !== 'undefined' && module.exports) { module.exports = { criarCliente, ErroPainel }; return; }

    const cliente = criarCliente({ fetcher: (...args) => root.fetch(...args), aoEncerrar: motivo => {
        if (typeof root.limparPainelSessao === 'function') root.limparPainelSessao();
        if (motivo) document.getElementById('login-erro').textContent = motivo;
    } });
    const ocupados = new Set();
    function aviso(mensagem = '', erro = false) {
        const box = document.getElementById('painel-status');
        if (!box) return;
        box.textContent = mensagem; box.hidden = !mensagem; box.dataset.erro = String(erro);
    }
    function permissoes() {
        const autenticado = cliente.perfil() !== null;
        document.querySelectorAll('header, .workspace').forEach(el => { el.inert = !autenticado; });
        document.getElementById('login-overlay').inert = autenticado;
        document.querySelectorAll('[data-escrita]').forEach(el => {
            const bloqueado = !cliente.podeEscrever();
            el.disabled = bloqueado; el.setAttribute('aria-disabled', String(bloqueado));
            el.title = bloqueado ? 'Seu perfil permite apenas consultas.' : '';
        });
        document.querySelectorAll('[data-admin]').forEach(el => { el.hidden = cliente.perfil() !== 'ADMIN'; });
        const simular = document.querySelector('[data-acao="executarSimulacao"]');
        if (simular) simular.textContent = cliente.perfil() === 'VIEWER' ? 'Atualizar alertas' : 'Simular';
        const total = document.getElementById('kpi-total');
        if (total?.nextElementSibling) total.nextElementSibling.textContent = cliente.perfil() === 'VIEWER' ? 'ALERTAS CARREGADOS' : 'MONITORADAS';
    }
    function tratar(error) {
        if (!error?.silencioso) aviso(error instanceof ErroPainel ? error.message : 'Não foi possível atualizar a tela. Tente novamente.', true);
    }
    function instalar() {
        const acoes = ['realizarLogin', 'carregarFrota', 'cadastrarNovoCaminhao', 'criarOperacaoRoteada',
            'carregarCorredorRegional', 'executarSimulacao', 'selecionarOperacao', 'abrirExplicacaoDecisao',
            'carregarHistoricoDecisoes', 'registrarDecisao', 'exportarCsv', 'buscarViaAutocomplete'];
        const gravacoes = new Set(['cadastrarNovoCaminhao', 'criarOperacaoRoteada', 'registrarDecisao']);
        acoes.forEach(nome => {
            const original = root[nome];
            root[nome] = async function (...args) {
                if (gravacoes.has(nome) && !cliente.podeEscrever()) { tratar(new ErroPainel('Seu perfil permite apenas consultas.', 403)); return; }
                const exclusivo = gravacoes.has(nome) || nome === 'realizarLogin' || nome === 'executarSimulacao';
                if (exclusivo && ocupados.has(nome)) return;
                if (exclusivo) ocupados.add(nome);
                if (exclusivo) aviso();
                const botoes = document.querySelectorAll('[data-acao="' + nome + '"]');
                if (exclusivo) botoes.forEach(botao => { botao.disabled = true; botao.setAttribute('aria-busy', 'true'); });
                try { await original(...args); }
                catch (error) {
                    if (!error?.silencioso && typeof root.falhaPainel === 'function') root.falhaPainel(nome);
                    tratar(error);
                }
                finally {
                    ocupados.delete(nome);
                    botoes.forEach(botao => { botao.disabled = false; botao.removeAttribute('aria-busy'); });
                    permissoes();
                }
            };
        });
        document.getElementById('login-senha').addEventListener('keydown', e => {
            if (e.key === 'Enter') { e.preventDefault(); root.realizarLogin(); }
        });
        permissoes();
    }
    root.PainelSessao = { ...cliente, aviso, permissoes, instalar, tratar };
})(typeof window !== 'undefined' ? window : globalThis);
