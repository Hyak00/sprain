/* Sessao e transporte do painel. Sem persistir credenciais ou alterar permissoes da API. */
(function (root) {
    'use strict';
    class ErroPainel extends Error {
        constructor(message, status = 0, silencioso = false) {
            super(message); this.name = 'ErroPainel'; this.status = status; this.silencioso = silencioso;
        }
    }
    function criarCliente({ fetcher, aoEncerrar = () => {}, timeoutMs = 90000 } = {}) {
        let usuario = null, geracao = 0, validade;
        const pendentes = new Set();
        const consultasPost = new Set(['/api/v1/painel/acompanhamento','/api/v1/infraestrutura/rota-caminhao', '/api/v1/infraestrutura/avaliar-mapa',
            '/api/v1/dados-publicos/consultar-rota', '/api/v1/transito/comparar', '/api/v1/painel/consultas','/api/v1/acesso/logout','/api/v1/demonstracao/reproduzir']);
        function encerrar(motivo = '') {
            clearTimeout(validade);geracao++; usuario = null;
            pendentes.forEach(c => c.abort()); pendentes.clear(); aoEncerrar(motivo);
        }
        function entrar(dados) {
            if (!dados?.api_key || !dados.tenant_id || !['ADMIN', 'OPERATOR', 'VIEWER'].includes(dados.role)) {
                throw new ErroPainel('O servidor devolveu uma sessão incompleta. Entre novamente.');
            }
            encerrar(); usuario = { ...dados };
            if(dados.expira_em){const ms=Date.parse(dados.expira_em)-Date.now();if(!Number.isFinite(ms)||ms<=0){encerrar();throw new ErroPainel('A sessão recebida expirou. Entre novamente.',401);}validade=setTimeout(()=>encerrar('Sua sessão expirou. Entre novamente.'),Math.min(ms,2147483647));validade?.unref?.();}
        }
        async function sair(){
            let falhou=false;
            try{if(usuario?.tipo_acesso==='INDIVIDUAL')await request('/api/v1/acesso/logout',{method:'POST',timeout:5000});}
            catch(e){falhou=e.status!==401;}
            finally{encerrar(falhou?'Acesso local encerrado. Não foi possível confirmar a revogação no servidor; a sessão expira no prazo informado.':'');}
        }
        function podeEscrever() { return usuario?.role === 'ADMIN' || usuario?.role === 'OPERATOR'; }
        async function request(path, options = {}) {
            if (typeof path !== 'string' || !path.startsWith('/api/v1/') || /[\\\r\n]/.test(path)) {
                throw new ErroPainel('Endereço de consulta inválido.');
            }
            const { publico = false, timeout = timeoutMs, ...init } = options;
            if (!publico && !usuario) throw new ErroPainel('Entre na sua conta para continuar.', 401);
            const method = (init.method || 'GET').toUpperCase();
            if (!publico && path.split('?')[0] === '/api/v1/logistica/exportar-contingencia/csv' && !podeEscrever()) {
                throw new ErroPainel('A exportação de contingência exige perfil ADMIN ou OPERATOR. Os históricos continuam disponíveis na central.', 403);
            }
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
                    const mensagens = { 400: 'Confira os dados. O código de recuperação pode estar inválido, expirado ou já utilizado.', 401: 'E-mail ou senha inválidos.', 403: 'Seu perfil não permite esta ação.',
                        404: 'Informação não encontrada ou fora da sua empresa.',
                        409: 'A ação está em conflito com os dados atuais. Recarregue a lista ou operação antes de confirmar.',
                        413: 'A exportação excede o limite. Solicite uma extração administrativa assistida.',
                        422: 'Confira os campos e as unidades informadas.',
                        429: res.headers.has('Retry-After') ? 'Limite de consultas por minuto atingido. Aguarde antes de tentar novamente.' : 'Limite do plano atingido. Peça ao administrador para conferir o plano e o consumo da empresa.',
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
        return { entrar, encerrar, sair, request, podeEscrever,
            identidade: () => usuario ? {usuario_id:usuario.usuario_id,role:usuario.role,tipo_acesso:usuario.tipo_acesso,tenant_id:usuario.tenant_id} : null,
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
        const modalAberto=document.getElementById('modal-despacho')?.style.display==='flex';
        document.querySelectorAll('header, .workspace, #ux-navegacao, .ux-cabecalho-pagina, .ux-visao-geral').forEach(el => { el.inert = !autenticado||modalAberto; });
        document.getElementById('login-overlay').inert = autenticado;
        document.querySelectorAll('[data-escrita]').forEach(el => {
            const bloqueado = !cliente.podeEscrever();
            el.disabled = bloqueado||el.getAttribute('aria-busy')==='true'; el.setAttribute('aria-disabled', String(el.disabled));
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
