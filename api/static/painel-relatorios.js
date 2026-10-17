/* Relatórios de leitura: fotografias históricas, formatos locais e proveniência. */
(function(root){
    'use strict';
    const D=root.PortalDados,PDF=root.PortalPDF;
    const el=(p,t,s)=>{const e=document.createElement(t);if(s!==undefined)e.textContent=s;p.appendChild(e);return e;};
    const aviso=(p,s)=>{const e=el(p,'p',s);e.setAttribute('role','status');return e;};
    const labels={economia_comprovada:'Economia comprovada',custo_observado:'Custo observado',custo_estimado:'Custo estimado da rota original',impacto_potencial:'Impacto potencial'};
    const natureza=v=>({NAO_DISPONIVEL:'Não disponível',ESTIMATIVA_PARCIAL:'Estimativa de planejamento; cobertura parcial',POTENCIAL_NAO_COMPROVADO:'Potencial; não comprovado'})[v]||'Não informada';
    function linhasPiloto(d){
        const linhas=['SPRain | Relatório do piloto','Uso interno - dados privados da empresa','Empresa: '+d.empresa,
            'Ambiente: '+(d.ambiente||'Não informado')+' - simulações não comprovam viagens reais.',
            'Emissão: '+D.data(d.emitido_em),'Período (Brasília): '+(d.periodo.inicio?d.periodo.inicio+' até '+d.periodo.fim:'Todo o cadastro disponível'),
            'Critério: '+d.periodo.criterio,'Operações: '+d.amostra.operacoes+' | Recomendações: '+d.amostra.recomendacoes,
            'Consultas no período: '+d.amostra.consultas+' | Decisões no período: '+d.amostra.decisoes,
            'Último cálculo incluído: '+D.dataRelatorio(d.amostra.ultimo_calculo),''];
        for(const [k,label]of Object.entries(labels)){
            const v=d.indicadores[k];linhas.push(label+': '+D.moeda(v.valor_brl),'Natureza: '+natureza(v.natureza));
            if(v.operacoes_com_valor!==undefined)linhas.push('Cobertura: '+v.operacoes_com_valor+' operação(ões) com valor; '+v.operacoes_sem_valor+' sem valor.');
            if(v.motivo)linhas.push('Ausência: '+v.motivo);if(v.fonte)linhas.push('Fonte: '+v.fonte);linhas.push('');
        }
        linhas.push('Limitações:',...d.limitacoes.map(s=>'- '+s),'Fontes:',...d.fontes.map(s=>'- '+s));return linhas;
    }
    function linhasIndividual(d){
        const r=d.decisao,linhas=['SPRain | Relatório da decisão #'+r.id_decisao,'Uso interno - dados privados da empresa',
            'Empresa: '+d.empresa,'Emissão do arquivo: '+D.data(d.emitido_em),'Operação: '+r.id_operacao,
            'Ambiente: '+(d.ambiente||'Não informado')+' - simulações não comprovam viagens reais.',
            'Decisão: '+r.decisao,'Registro da decisão: '+D.data(r.registrado_em),'Motivo: '+r.motivo_gestor,
            'Usuário: '+(r.usuario_id||'Identidade individual não registrada'),'Papel: '+(r.perfil_registro||'Não registrado'),
            'Consulta vinculada: '+(r.consulta_id||'Não informada'),'Fonte da fotografia: '+(d.fonte_snapshot||'Não disponível'),
            ...d.limitacoes.map(s=>'Limitação: '+s),''];
        if(d.snapshot)linhas.push(...D.linhasDecisao(d.snapshot,[r],d.empresa,d.emitido_em));
        else linhas.push('Sem fotografia histórica: distâncias, tempos, custos, restrições e fontes da época são desconhecidos.',
            'A consulta atual não substitui os dados usados na decisão.',
            'Economia comprovada: não disponível.','Custo observado: não disponível.','Custo estimado da época: não disponível.');
        return linhas;
    }
    function html(linhas){
        const esc=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
        return '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'"><title>SPRain | Relatório interno</title><style>body{max-width:900px;margin:24px auto;padding:16px;font:16px/1.5 sans-serif;color:#142139}h1{border-bottom:3px solid #0284c7;padding-bottom:12px}pre{font:inherit;white-space:pre-wrap;overflow-wrap:anywhere}@media print{body{margin:0}}</style></head><body><h1>SPRain | Relatório interno</h1><pre>'+linhas.map(esc).join('\n')+'</pre></body></html>';
    }
    async function render(p,ctx){
        const usuario=ctx.usuario(),empresa=usuario.tenant_id;let ciclo=0,leitura=0,leituraDecisao=0;
        const atual=()=>ctx.atual()&&ctx.usuario()?.tenant_id===empresa;
        function botao(parent,label,fn){const b=el(parent,'button',label);b.type='button';b.onclick=async()=>{
            if(b.disabled||!atual())return;b.disabled=true;b.setAttribute('aria-busy','true');
            try{await fn();}catch(e){if(atual()&&!e?.silencioso)aviso(parent,e?.name==='ErroPainel'?e.message:'Não foi possível gerar o relatório. Atualize a consulta e tente novamente.');}
            finally{if(atual()&&b.isConnected){b.disabled=false;b.removeAttribute('aria-busy');}}
        };return b;}
        function arquivos(parent,base,linhas,dados,nomes){
            botao(parent,nomes.pdf,()=>ctx.download(base+'.pdf',PDF.gerar(linhas),'application/pdf'));
            botao(parent,nomes.json||'Baixar dados do relatório (JSON)',()=>ctx.download(base+'.json',JSON.stringify(dados,null,2),'application/json'));
            botao(parent,nomes.html,()=>ctx.download(base+'.html',html(linhas),'text/html;charset=utf-8'));
        }
        el(p,'p','Relatórios privados para compartilhamento interno. PDFs e HTML não enviam dados a terceiros. Guarde os arquivos com acesso restrito. Valores estimados ou potenciais não comprovam economia realizada.');
        const filtros=el(p,'form');filtros.onsubmit=e=>e.preventDefault();
        const campo=(label,nome)=>{const l=el(filtros,'label',label),i=el(l,'input');i.type='date';i.name=nome;return i;};
        const inicio=campo('Início do período (Brasília)','relatorio_inicio'),fim=campo('Fim do período, inclusive (Brasília)','relatorio_fim');
        el(filtros,'p','Deixe as duas datas vazias para todo o cadastro. Informe ambas para até 366 dias. O piloto filtra operações pela criação; históricos usam o horário de cada registro.');
        const escopo=aviso(p,'Período aplicado: todo o cadastro.'),piloto=el(p,'article'),historicos=el(p,'section'),consulta=el(p,'section'),decisoes=el(p,'section');
        let params='';
        const url=(path,extras='')=>'/api/v1/painel/relatorios/'+path+((params||extras)?'?'+[params,extras].filter(Boolean).join('&'):'');
        async function csv(path,nome){
            const c=ciclo,r=await root.PainelSessao.request(url(path)),texto=await r.text();
            if(atual()&&c===ciclo)ctx.download(nome,texto,'text/csv;charset=utf-8');
        }
        async function atualizar(){
            if(!filtros.reportValidity())return;
            if(Boolean(inicio.value)!==Boolean(fim.value)||inicio.value&&fim.value<inicio.value){aviso(filtros,'Informe as duas datas em ordem ou deixe ambas vazias.');return;}
            const n=++ciclo;params=inicio.value?'inicio='+encodeURIComponent(inicio.value)+'&fim='+encodeURIComponent(fim.value):'';
            escopo.textContent='Período aplicado: '+(inicio.value?inicio.value+' até '+fim.value+' (Brasília).':'todo o cadastro.');
            piloto.replaceChildren();historicos.replaceChildren();decisoes.replaceChildren();
            el(piloto,'h4','Relatório do piloto');const st=aviso(piloto,'Consultando indicadores e cobertura…');
            el(historicos,'h4','Históricos completos no período');
            el(historicos,'p','CSV UTF-8 com separador ponto e vírgula, fontes, datas, autoria registrada e premissas. Até 10 mil registros ou 8 MB por arquivo; acima disso, refine o período. Campos desconhecidos ficam vazios.');
            botao(historicos,'Exportar histórico de consultas (CSV)',()=>csv('consultas.csv','sprain-consultas.csv'));
            botao(historicos,'Exportar histórico de decisões (CSV)',()=>csv('decisoes.csv','sprain-decisoes.csv'));
            try{
                const d=await ctx.obter(url('piloto'));if(!atual()||n!==ciclo)return;
                const linhas=linhasPiloto(d);
                ctx.tabela(piloto,['Indicador','Valor','Natureza / cobertura'],Object.entries(labels).map(([k,l])=>{const i=d.indicadores[k];return[l,D.moeda(i.valor_brl),natureza(i.natureza)+(i.operacoes_com_valor!==undefined?' · '+i.operacoes_com_valor+' com valor / '+i.operacoes_sem_valor+' sem valor':'')];}));
                const det=el(piloto,'details');el(det,'summary','Amostra, critérios, limitações e fontes');el(det,'pre',linhas.join('\n'));
                arquivos(piloto,'sprain-piloto',linhas,d,{pdf:'Baixar PDF do piloto',json:'Baixar dados do resumo (JSON)',html:'Baixar HTML do piloto'});
                st.remove();
            }catch(e){if(atual()&&n===ciclo)st.textContent='Indicadores indisponíveis. Tente Atualizar período e relatórios; não há base para declarar economia.';}
            if(atual()&&n===ciclo)await listarDecisoes(n,0);
        }
        botao(filtros,'Atualizar período e relatórios',atualizar);
        async function listarDecisoes(n,offset){
            decisoes.replaceChildren();el(decisoes,'h4','Relatório de uma decisão individual');const st=aviso(decisoes,'Carregando decisões registradas…');
            try{
                const d=await ctx.obter(url('decisoes','offset='+offset));if(!atual()||n!==ciclo)return;st.remove();
                if(!d.items.length)aviso(decisoes,'Nenhuma decisão registrada no período.');
                const detalhe=el(decisoes,'div');
                for(const r of d.items){const a=el(decisoes,'article');el(a,'p','#'+r.id_decisao+' · '+r.id_operacao+' · '+r.decisao+' · '+D.data(r.registrado_em));
                    botao(a,'Abrir relatório da decisão #'+r.id_decisao,async()=>{
                        const l=++leituraDecisao;detalhe.replaceChildren();const st=aviso(detalhe,'Carregando a fotografia histórica…');
                        try{const dados=await ctx.obter('/api/v1/painel/relatorios/decisoes/'+r.id_decisao);if(!atual()||n!==ciclo||l!==leituraDecisao)return;
                            detalhe.replaceChildren();el(detalhe,'h5','Decisão #'+r.id_decisao+' · fotografia histórica');const linhas=linhasIndividual(dados);
                            const pre=el(detalhe,'details');pre.open=true;el(pre,'summary','Conteúdo do relatório');el(pre,'pre',linhas.join('\n'));
                            arquivos(detalhe,'sprain-decisao-'+r.id_decisao,linhas,dados,{pdf:'Baixar PDF da decisão #'+r.id_decisao,json:'Baixar JSON da decisão #'+r.id_decisao,html:'Baixar HTML da decisão #'+r.id_decisao});
                        }catch(e){if(atual()&&n===ciclo&&l===leituraDecisao){detalhe.replaceChildren();aviso(detalhe,'Não foi possível carregar a decisão. Tente abri-la novamente.');}}
                    });
                }
                if(offset>0)botao(decisoes,'Decisões anteriores',()=>listarDecisoes(n,Math.max(0,offset-20)));
                if(d.proximo_offset!==null)botao(decisoes,'Próximas decisões',()=>listarDecisoes(n,d.proximo_offset));
            }catch(e){if(atual()&&n===ciclo)st.textContent='Histórico indisponível. Atualize o período para tentar novamente.';}
        }
        el(consulta,'h4','Consulta atual e decisões da operação');const st=aviso(consulta,'Carregando operações…');
        try{
            const ops=await ctx.obter('/api/v1/logistica/operacoes');if(!atual())return;st.remove();
            if(!Array.isArray(ops))throw Error('Operações indisponíveis');
            if(!ops.length)aviso(consulta,'Nenhuma operação cadastrada para esta empresa.');
            else{
                const label=el(consulta,'label','Operação '),select=el(label,'select');select.id='portal-operacao';
                for(const o of ops){const opt=el(select,'option',o.id_operacao+' · '+(o.origem_nome||'Origem')+' → '+(o.destino_nome||'Destino'));opt.value=o.id_operacao;}
                const area=el(consulta,'div');
                botao(consulta,'Carregar consulta e decisões',async()=>{
                    const l=++leitura,id=select.value;area.replaceChildren();const st=aviso(area,'Carregando consulta atual e lista de decisões…');
                    try{
                        const resultados=await Promise.allSettled([ctx.obter('/api/v1/painel/consultas',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id_operacao:id})}),ctx.obter('/api/v1/logistica/operacoes/'+encodeURIComponent(id)+'/decisoes')]);
                        if(!atual()||l!==leitura)return;
                        if(resultados[0].status!=='fulfilled')throw Error('Consulta indisponível');
                        const d=resultados[0].value,h=resultados[1].status==='fulfilled'?resultados[1].value:null;
                        if(d.explicacao?.id_operacao!==id)throw Error('Operação divergente');
                        area.replaceChildren();const recebido=new Date().toISOString();
                        el(area,'p','Consulta '+(d.consulta?.id||'sem identificador')+' · recebida em '+D.data(recebido)+'. Os dados financeiros abaixo pertencem a esta consulta atual. Para condições de uma decisão antiga, abra seu relatório individual.');
                        el(area,'p',d.explicacao.justificativa||'Justificativa não informada.');
                        const linhas=D.linhasDecisao(d.explicacao,h,empresa,recebido);
                        arquivos(area,ctx.nome(id),linhas,{empresa,consulta_recebida_em:recebido,...d,decisoes:h},
                            {pdf:'Baixar PDF da consulta e decisões',json:'Baixar consulta integral (JSON)',html:'Baixar relatório compartilhável (HTML)'});
                        botao(area,'Baixar consulta (CSV)',async()=>{if(!d.consulta?.id)throw Error('Consulta sem identificador');const r=await root.PainelSessao.request('/api/v1/painel/relatorios/consultas.csv?id_consulta='+encodeURIComponent(d.consulta.id));const texto=await r.text();if(atual()&&l===leitura)ctx.download(ctx.nome(id)+'-consulta.csv',texto,'text/csv;charset=utf-8');});
                        if(Array.isArray(h)){
                            ctx.tabela(area,['Decisão','Motivo','Registro','Usuário'],h.map(r=>[r.decisao,r.motivo_gestor,D.data(r.registrado_em),r.usuario_id||'Não registrado']));if(!h.length)aviso(area,'Nenhuma decisão retornada.');
                            botao(area,'Baixar decisões (CSV)',async()=>{const r=await root.PainelSessao.request('/api/v1/painel/relatorios/decisoes.csv?id_operacao='+encodeURIComponent(id));const texto=await r.text();if(atual()&&l===leitura)ctx.download(ctx.nome(id)+'-decisoes.csv',texto,'text/csv;charset=utf-8');});
                        }else aviso(area,'Lista de decisões indisponível; a ausência está indicada no relatório.');
                    }catch(e){if(atual()&&l===leitura){area.replaceChildren();aviso(area,'Consulta indisponível. Tente carregar novamente.');}}
                });
                select.onchange=()=>{leitura++;area.replaceChildren();};
            }
        }catch(e){if(atual())st.textContent='Lista de operações indisponível. Reabra Relatórios e exportações para tentar novamente.';}
        if(atual())await atualizar();
    }
    root.RelatoriosPainel={render,linhasPiloto,linhasIndividual,html};
    if(typeof module!=='undefined'&&module.exports)module.exports=root.RelatoriosPainel;
})(typeof window!=='undefined'?window:globalThis);
