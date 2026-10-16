/* Complemento de leitura do inspector. Não recalcula nem altera o motor de rotas. */
(function (root) {
    'use strict';
    const informado = v => typeof v === 'string' && v.trim() ? v : 'Não informado';
    const numero = v => typeof v === 'number' && Number.isFinite(v) ? v : null;
    const moeda = v => numero(v) === null ? 'Não informado' : v.toLocaleString('pt-BR', {style:'currency', currency:'BRL'});
    function instante(v) {
        if (typeof v !== 'string' || !v.trim() || !/T.*(?:Z|[+-]\d{2}:\d{2})$/.test(v)) return null;
        const n = Date.parse(v); return Number.isFinite(n) ? n : null;
    }
    const data = v => instante(v) === null ? 'Não informado' : new Date(v).toLocaleString('pt-BR', {timeZone:'America/Sao_Paulo'}) + ' (Brasília)';
    function trechos(geo) {
        return new Set((Array.isArray(geo?.features) ? geo.features : []).map(f => f?.properties?.id_trecho)
            .filter(id => typeof id === 'number' || typeof id === 'string').map(String));
    }
    function evento(e, operacao, agora = Date.now()) {
        const ids = Array.isArray(e.trechos_afetados) ? e.trechos_afetados.filter(id => typeof id === 'number' || typeof id === 'string').map(String) : [];
        const original = trechos(operacao?.geometrias?.rota_original_geojson);
        const alternativa = trechos(operacao?.geometrias?.rota_alternativa_geojson);
        const locais = [];
        if (ids.some(id => original.has(id))) locais.push('rota original');
        if (ids.some(id => alternativa.has(id))) locais.push('rota alternativa');
        const validade = instante(e.expiracao_em), atualizacao = instante(e.ultima_atualizacao);
        const confianca = numero(e.confianca);
        return {
            id: informado(e.id_evento), categoria: informado(e.categoria), fonte: informado(e.fonte),
            status: informado(e.status_evento), desconhecido: informado(e.o_que_nao_sabemos),
            confianca: confianca !== null && confianca >= 0 && confianca <= 1 ? (confianca * 100).toFixed(0) + '%' : 'Não informado',
            local: locais.length ? 'Trechos associados à ' + locais.join(' e à ') : e.escopo==='PRIVADO' ? 'Relato privado por coordenada; associação à rota não validada' : 'Sem associação identificada às rotas exibidas; contexto público',
            trechos: ids.length ? ids.join(', ') : 'Não informados',
            temporal: validade === null ? 'Validade não informada; conferir antes de usar' : validade <= agora ? 'EXPIRADO — atualizar a consulta' : atualizacao === null ? 'Atualização não informada; conferir antes de usar' : atualizacao > agora ? 'Data de atualização futura; conferir na fonte' : 'Dentro da validade informada pela API',
            expirado: validade !== null && validade <= agora,
            deteccao: data(e.primeira_deteccao), atualizacao: data(e.ultima_atualizacao), expiracao: data(e.expiracao_em)
        };
    }
    function comparacao(op) {
        const infra = op?.infraestrutura || {}, f = infra.financeiro || {};
        const alternativa = op?.validacao_rota?.rota_alternativa_disponivel === true &&
            Array.isArray(op?.geometrias?.rota_alternativa_geojson?.features) &&
            op.geometrias.rota_alternativa_geojson.features.some(v => ['LineString','MultiLineString'].includes(v?.geometry?.type) && v.geometry.coordinates?.length > 0);
        const rows = [
            ['Original: custo estimado com parcelas conhecidas', f.custo_original_conhecido_brl],
            ['Alternativa: custo estimado com parcelas conhecidas', alternativa ? f.custo_alternativa_conhecido_brl : null],
            ['Diferença de custo (alternativa − original)', alternativa ? f.custo_desvio_brl : null],
            ['Diferença de pedágios conhecidos', alternativa ? f.delta_pedagios_conhecidos_brl : null],
            ['Diferença estimada de combustível', alternativa ? f.delta_combustivel_estimado_brl : null],
            ['Economia operacional estimada', alternativa ? f.economia_operacional_conhecida_brl : null],
            ['Prejuízo potencial evitado', alternativa ? f.prejuizo_potencial_evitado_brl : null],
            ['Economia líquida potencial', alternativa ? f.economia_liquida_potencial_brl : null],
            ['Original: custo médio estimado (R$/km)', f.custo_medio_original_conhecido_por_km_brl],
            ['Alternativa: custo médio estimado (R$/km)', alternativa ? f.custo_medio_alternativa_conhecido_por_km_brl : null]
        ];
        return {alternativa, rows, pendentes: numero(f.tarifas_pendentes_comparacao),
            aviso: informado(f.aviso), fotografia: informado(infra.aviso),
            premissas: f.premissas || {}, dimensoes: infra.dimensoes || {}, combustivel: f.combustivel || {}};
    }
    if (typeof module !== 'undefined' && module.exports) { module.exports = {evento, comparacao, moeda, instante}; return; }

    const box = document.createElement('section'); box.className = 'ac-painel';
    box.setAttribute('aria-label', 'Alertas e comparação detalhada');
    document.getElementById('infra-auditoria').after(box);
    let operacao, geracao = 0, controle, timer, eventos = [], consultaEm;
    function texto(parent, tag, value) { const el = document.createElement(tag); el.textContent = value; parent.appendChild(el); return el; }
    function linha(parent, nome, valor) { const p = texto(parent, 'p', ''); texto(p, 'strong', nome + ': '); texto(p, 'span', valor); }
    function limpar() {
        geracao++; controle?.abort(); clearInterval(timer); eventos = []; operacao = null; consultaEm = null; box.replaceChildren();
    }
    function exibir(op) {
        limpar(); operacao = op;
        const c = comparacao(op), custos = texto(box, 'details', '');
        if (!c.alternativa) {
            document.getElementById('box-alt-km').textContent='Indisponível';
            document.getElementById('box-alt-min').textContent='Sem caminho alternativo retornado';
            ['modal-custo','modal-prejuizo'].forEach(id=>{document.getElementById(id).textContent='Não comparável';});
        }
        texto(custos, 'summary', 'Comparação detalhada de custos');
        texto(custos, 'p', c.alternativa ? 'Alternativa disponível no resultado consultado. Valores estimados; não comprovam economia realizada.' : 'Sem alternativa disponível com geometria. Não há comparação válida de desvio neste resultado.');
        const tabela = texto(custos, 'table', '');
        texto(tabela, 'caption', 'Valores da fotografia de cálculo retornada pela API');
        const head = texto(tabela, 'thead', ''), hr = texto(head, 'tr', '');
        ['Parcela', 'Valor'].forEach(t => { const th=texto(hr,'th',t); th.scope='col'; });
        const body = texto(tabela, 'tbody', '');
        c.rows.forEach(([nome,v]) => { const tr=texto(body,'tr',''); texto(tr,'th',nome).scope='row'; texto(tr,'td',moeda(v)); });
        linha(custos, 'Tarifas pendentes nas duas rotas', c.pendentes === null ? 'Não informado' : String(c.pendentes));
        texto(custos, 'p', 'Cobertura parcial. Valores negativos na diferença indicam alternativa mais barata. Dados ausentes não equivalem a custo zero.');
        texto(custos, 'p', 'Espera: sem estimativa comparável neste contrato. Economia comprovada: não disponível; depende de custos e viagens observados.');
        texto(custos, 'p', c.aviso); texto(custos, 'p', c.fotografia);
        const parametros = texto(custos, 'details', ''); texto(parametros, 'summary', 'Medidas atuais e premissas do cálculo');
        const unidades = {
            altura_m:'Altura (m)', largura_m:'Largura (m)', comprimento_m:'Comprimento (m)', peso_total_t:'Peso total (t)', eixos:'Eixos',
            consumo_km_l:'Consumo (km/L)', preco_combustivel_litro:'Combustível (R$/L)', custo_por_km:'Custo base (R$/km)',
            custo_por_km_sem_combustivel:'Custo sem combustível (R$/km)',
            custo_hora_motorista:'Motorista (R$/h)', custo_operacional_veiculo_hora:'Veículo (R$/h)', custo_atraso_hora:'Atraso (R$/h)',
            prejuizo_potencial_alagamento:'Perda potencial informada (R$)'
        };
        Object.entries(unidades).forEach(([chave,label]) => {
            const v = Object.hasOwn(c.dimensoes,chave) ? c.dimensoes[chave] : c.premissas[chave];
            linha(parametros,label,numero(v) === null ? 'Não informado' : String(v));
        });
        linha(parametros,'Custo por km aplicado pela API',moeda(c.combustivel.custo_por_km_aplicado));
        linha(parametros,'Método de combustível',informado(c.combustivel.modo));
        linha(parametros,'Fonte do consumo',informado(c.combustivel.fonte_consumo));
        linha(parametros,'Fonte do preço',informado(c.combustivel.fonte_preco));
        linha(parametros,'Data da coleta do preço',informado(c.combustivel.data_coleta));
        texto(parametros,'p',informado(c.combustivel.aviso));
        texto(parametros,'p','Medidas efetivas atuais retornadas pela API; não há fotografia datada das medidas nesta resposta. As premissas financeiras pertencem ao cálculo retornado. Use os formulários existentes de caminhão e despacho para informar medidas e recalcular.');
        const alertas = texto(box,'details',''); texto(alertas,'summary','Alertas: fonte, validade e relação com a rota');
        texto(alertas,'p','Até 50 eventos públicos e 50 relatos privados da empresa. A associação por trechos não confirma impacto atual nem cobertura completa.');
        const botao = texto(alertas,'button','Consultar / atualizar alertas'); botao.type='button'; botao.className='btn-top';
        const status = texto(alertas,'p','Abra esta seção para consultar.'); status.setAttribute('role','status');
        const lista = texto(alertas,'div','');
        function renderizar() {
            lista.replaceChildren();
            if (!eventos.length) { texto(lista,'p','Nenhum evento retornado nesta consulta. Isso não comprova ausência de risco.'); return; }
            for (const e of eventos) {
                const v=evento(e,op), item=texto(lista,'article','');
                texto(item,'h4',v.categoria + ' · ' + v.status);
                linha(item,'Natureza',e.natureza||'Não informada');linha(item,'Escopo',e.escopo||'Não informado');
                linha(item,'Identificador',v.id); linha(item,'Fonte',v.fonte);
                linha(item,'Localização',v.local); linha(item,'IDs dos trechos',v.trechos);
                linha(item,'Local informado',e.local||'Não informado');
                if(e.descricao)linha(item,'Descrição relatada',e.descricao);
                linha(item,'Primeira detecção',v.deteccao); linha(item,'Atualização',v.atualizacao); linha(item,'Expira em',v.expiracao);
                const temporal=texto(item,'p',v.temporal);
                temporal.dataset.expiracao=e.expiracao_em || '';
                linha(item,'Confiança informada pela API',v.confianca);
                texto(item,'p','O status e a confiança são declarações da API; não equivalem a verificação independente. Chuva simulada, previsão e registro histórico não se tornam observação confirmada por aparecerem no painel.');
                linha(item,'O que não sabemos',v.desconhecido);
                linha(item,'Consequência possível',e.consequencia_possivel||'Não informada');
                texto(item,'p',e.criterio_consequencia||'Possibilidade relatada; não confirma impacto na viagem.');
                if (window.PainelSessao.podeEscrever() && e.escopo!=='PRIVADO' && typeof e.id_evento === 'string' && e.id_evento.trim() && !v.expirado) feedback(item,e);
            }
        }
        async function consultar() {
            controle?.abort(); const atual=++geracao; controle=new AbortController();
            clearInterval(timer); eventos=[]; lista.replaceChildren(); consultaEm=null;
            botao.disabled=true; botao.setAttribute('aria-busy','true'); status.textContent='Consultando alertas…';
            try {
                const resposta=await window.PainelEventos.consultar(true);
                const dados=resposta.items;
                if(atual!==geracao)return;
                if(!Array.isArray(dados) || dados.some(e=>!e || typeof e!=='object' || Array.isArray(e)))throw new Error('Resposta inválida');
                eventos=dados; consultaEm=new Date().toISOString();
                status.textContent='Consulta recebida em '+data(consultaEm)+'. Até 50 ocorrências públicas e 50 relatos recentes; não é histórico completo. Atualize para buscar mudanças na fonte.';
                renderizar(); timer=setInterval(()=>{
                    if(atual!==geracao)return;
                    lista.querySelectorAll('[data-expiracao]').forEach(el=>{
                        const fim=instante(el.dataset.expiracao);
                        if(fim!==null && fim<=Date.now()){
                            el.textContent='EXPIRADO — atualizar a consulta';
                            el.closest('article').querySelectorAll('form button').forEach(b=>{b.disabled=true;});
                        }
                    });
                },60000);
            } catch(error) {
                if(atual!==geracao || error?.silencioso)return;
                status.textContent='Alertas indisponíveis. Não é possível concluir que a rota está livre. Tente atualizar.';
            } finally {if(atual===geracao){botao.disabled=false;botao.removeAttribute('aria-busy');}}
        }
        botao.onclick=consultar;
        alertas.addEventListener('toggle',()=>{if(alertas.open && !consultaEm && !botao.disabled)consultar();});
    }
    function feedback(parent,e) {
        const atual=geracao, form=texto(parent,'form','');
        const label=texto(form,'label','Avaliação deste alerta '), select=document.createElement('select'); label.appendChild(select);
        [['confirmar','Corresponde ao observado'],['falso','Não corresponde ao observado (falso alerta)']].forEach(([v,t])=>{const o=texto(select,'option',t);o.value=v;});
        const motivoLabel=texto(form,'label','Motivo (obrigatório, até 500 caracteres) '), motivo=document.createElement('textarea');
        motivo.required=true;motivo.maxLength=500;motivoLabel.appendChild(motivo);
        const enviar=texto(form,'button','Registrar feedback');enviar.type='submit';enviar.className='btn-top';
        const status=texto(form,'p','O feedback fica registrado para sua empresa; não altera o evento público.');status.setAttribute('role','status');
        form.onsubmit=async ev=>{
            ev.preventDefault(); if(enviar.disabled || !window.PainelSessao.podeEscrever() || atual!==geracao)return;
            if(evento(e,operacao).expirado){status.textContent='Evento expirado. Atualize os alertas antes de registrar feedback.';enviar.disabled=true;return;}
            if(!motivo.value.trim()){status.textContent='Informe o motivo.';motivo.focus();return;}
            enviar.disabled=true;
            try {
                const res=await window.PainelSessao.request('/api/v1/alertas/feedback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id_evento:e.id_evento,falso_alerta:select.value==='falso',evento_nao_detectado:false,motivo_reporte:motivo.value.trim()})});
                const info=await res.json(); if(atual!==geracao)return;
                if(info.sucesso!==true)throw new Error('Não confirmado');
                status.textContent='Feedback registrado para sua empresa. O evento público foi preservado.';motivo.value='';
            } catch(error) {if(atual===geracao && !error?.silencioso)status.textContent='Não foi possível registrar o feedback. Confira o evento e tente novamente.';}
            finally {if(atual===geracao)enviar.disabled=false;}
        };
    }
    root.AlertasComparacao={exibir,limpar};
})(typeof window !== 'undefined' ? window : globalThis);
