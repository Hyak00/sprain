/* Fluxos 3.1: controles adicionais, consultas persistentes e premissas editaveis. */
(function(root){
    'use strict';
    const D=root.PortalDados;let atual=null,geracao=0,contador=0;
    const caixa=document.createElement('section');caixa.className='mvp-complemento';document.getElementById('infra-auditoria').before(caixa);
    function el(p,t,s){const e=document.createElement(t);if(s!==undefined)e.textContent=s;p.appendChild(e);return e;}
    function status(p,s){const e=el(p,'p',s);e.setAttribute('role','status');return e;}
    function campo(p,nome,label,tipo='text',valor='',opcoes={}){const l=el(p,'label',label),i=el(l,'input');i.name=nome;i.type=tipo;i.id='mvp-campo-'+(++contador);i.value=valor??'';for(const[k,v]of Object.entries(opcoes))if(v!==undefined)i.setAttribute(k,String(v));return i;}
    const custos=[['custo_por_km','Custo total por km (R$/km)'],['custo_por_km_sem_combustivel','Custo sem combustível (R$/km)'],['consumo_km_l','Consumo (km/L)'],['preco_combustivel_litro','Preço de referência (R$/L)'],['custo_hora_motorista','Motorista (R$/h)'],['custo_operacional_veiculo_hora','Veículo (R$/h)'],['custo_atraso_hora','Atraso contratual (R$/h)'],['prejuizo_potencial_alagamento','Perda potencial informada (R$)']];
    const medidas=[['altura_m','Altura (m)',10],['largura_m','Largura (m)',10],['comprimento_m','Comprimento (m)',100],['peso_total_t','Peso carregado (t)',300],['eixos','Eixos',15]];
    function formularioCustos(p,valores={}){const d=el(p,'details');el(d,'summary','Premissas financeiras');el(d,'p','Em branco: usar valores da frota/referências aplicáveis. Custo total por km tem prioridade; combustível não é somado novamente.');const refs={};for(const[k,label]of custos)refs[k]=campo(d,k,label,'number',valores[k],{min:0,step:'any',max:['consumo_km_l','preco_combustivel_litro'].includes(k)?100:undefined});refs.combustivel_data_coleta=campo(d,'combustivel_data_coleta','Data de coleta do combustível','date',valores.combustivel_data_coleta);return refs;}
    function formularioMedidas(p,valores={}){const d=el(p,'details');el(d,'summary','Medidas do caminhão (opcionais; informe todas ou nenhuma)');const refs={};for(const[k,label,max]of medidas)refs[k]=campo(d,k,label,'number',valores[k],{min:k==='eixos'?2:0.01,max,step:k==='eixos'?1:'any'});return refs;}
    function ler(refs){return Object.fromEntries(Object.entries(refs).filter(([,i])=>i.value!=='').map(([k,i])=>[k,i.type==='number'?Number(i.value):i.value]));}
    function lerMedidas(refs){const v=ler(refs);if(Object.keys(v).length&&Object.keys(v).length!==5)throw Error('Informe as cinco medidas ou deixe todas em branco.');return Object.keys(v).length?v:null;}
    function erro(e){return e?.silencioso?'':e?.name==='ErroPainel'?e.message:e?.message||'Não foi possível concluir a ação.';}
    function botao(p,label,fn,{escrita=false,valido=()=>true}={}){const b=el(p,'button',label);b.type='button';b.disabled=escrita&&!root.PainelSessao.podeEscrever();b.onclick=async()=>{
        if(b.disabled||!valido()||(escrita&&!root.PainelSessao.podeEscrever()))return;
        b.disabled=true;b.setAttribute('aria-busy','true');try{await fn();}catch(e){if(valido()&&erro(e))status(p,erro(e));}finally{if(b.isConnected&&valido()){b.disabled=escrita&&!root.PainelSessao.podeEscrever();b.removeAttribute('aria-busy');}}
    };return b;}
    async function enviar(path,body,method='POST'){const r=await root.PainelSessao.request('/api/v1/painel'+path,{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});return r.json();}
    function limpar(){geracao++;atual=null;caixa.replaceChildren();}
    function exibir(dados,consulta){
        limpar();atual={dados,consulta};const n=geracao,c=dados.contexto_consulta||{};
        const meta=el(caixa,'div');meta.className='mvp-natureza';el(meta,'strong','Natureza: '+(c.natureza||'Não informada'));
        el(meta,'p','Fonte: '+(c.fonte||'Não informada')+' Cálculo: '+D.data(c.calculo_gerado_em)+'. Consulta: '+D.data(consulta?.registrado_em)+'.');
        el(meta,'p','IVI é índice de vulnerabilidade; não é ocorrência confirmada. Valores monetários desta comparação são estimativas com parcelas conhecidas; não comprovam economia realizada.');
        el(meta,'p','Os trechos vermelhos e a lista de trechos críticos representam vulnerabilidade física da malha. A chuva escolhida altera a recomendação; a classificação física continua visível mesmo sem chuva.');
        const d=el(caixa,'details');el(d,'summary','Editar premissas e recalcular esta operação');
        el(d,'p','Os cálculos usam o motor existente no servidor. Este recálculo manual cria um cenário identificado como SIMULAÇÃO. Medidas e restrições continuam sendo consideradas.');
        const f=el(d,'form'),refs=formularioCustos(f,c.premissas_editaveis||{});f.onsubmit=e=>e.preventDefault();
        const chuva=campo(f,'precipitacao_mm','Chuva simulada para este recálculo (mm/h)','number',c.precipitacao_mm,{required:'',min:0,max:250,step:'any'});
        if(!root.PainelSessao.podeEscrever())f.querySelectorAll('input').forEach(i=>i.disabled=true);
        const fb=status(d,root.PainelSessao.podeEscrever()?'Preencha as premissas, confira o cenário e salve para atualizar a comparação.':'Seu perfil permite consultar as premissas, sem alterá-las.');
        botao(d,'Salvar premissas e recalcular',async()=>{
            if(!f.reportValidity())return;fb.textContent='Salvando e recalculando…';
            try{await enviar('/operacoes/'+encodeURIComponent(dados.id_operacao)+'/premissas',{selo_esperado:c.selo_premissas,custos_operacionais:ler(refs),precipitacao_mm:Number(chuva.value)},'PUT');
                if(n!==geracao)return;fb.textContent='Premissas salvas. Atualizando a operação…';await root.selecionarOperacao(dados.id_operacao);
            }catch(e){if(n===geracao)fb.textContent=erro(e);}
        },{escrita:true,valido:()=>n===geracao});
        botao(caixa,'Ver histórico persistente de consultas',()=>root.PortalOperacional.navegar('consultas'));
        botao(caixa,'Reportar ocorrência não detectada',()=>root.PortalOperacional.navegar('relatos'));
        root.PainelEventos?.consultar(false).catch(e=>{if(n===geracao&&!e?.silencioso)status(caixa,'Ocorrências do mapa indisponíveis. Atualize os alertas; isso não significa ausência de risco.');});
    }
    async function historico(p,ctx){
        el(p,'p','Consultas persistidas no servidor por empresa. A fotografia histórica não autoriza uma decisão atual. Acessos individuais registram o identificador do usuário; credenciais compartilhadas identificam somente empresa e papel.');
        let offset=0,leitura=0;const lista=el(p,'div'),detalhe=el(p,'div');
        const carregar=async()=>{leitura++;lista.replaceChildren();detalhe.replaceChildren();status(lista,'Consultando histórico…');
            const d=await ctx.obter('/api/v1/painel/consultas?offset='+offset);if(!ctx.atual())return;lista.replaceChildren();
            if(!d.items.length)status(lista,'Nenhuma consulta registrada para esta empresa. Abra uma operação para registrar a primeira consulta.');
            for(const c of d.items){const a=el(lista,'article');el(a,'p',c.id_operacao+' · '+D.data(c.criado_em)+' · Perfil da credencial: '+c.perfil);
                el(a,'p',c.usuario_id?'Usuário: '+c.usuario_id:'Identidade individual não fornecida (credencial compartilhada).');
                botao(a,'Abrir fotografia '+c.id_operacao,async()=>{const n=++leitura;detalhe.replaceChildren();status(detalhe,'Carregando fotografia histórica…');let r;try{r=await ctx.obter('/api/v1/painel/consultas/'+c.id);}catch(e){if(ctx.atual()&&n===leitura){detalhe.replaceChildren();status(detalhe,erro(e));}return;}if(!ctx.atual()||n!==leitura)return;
                    detalhe.replaceChildren();el(detalhe,'h4','Consulta histórica '+r.id_operacao);el(detalhe,'p','Registrada em '+D.data(r.criado_em)+'. Estes dados são os que foram guardados na consulta, não o cadastro atual.');
                    const s=r.snapshot;el(detalhe,'p',s.justificativa||'Justificativa não informada.');
                    for(const[k,v]of Object.entries(s.metricas||{}))el(detalhe,'p',k+': '+(v??'Não informado'));
                    const bruto=el(detalhe,'details');el(bruto,'summary','Fotografia integral, incluindo fontes, geometria e premissas');el(bruto,'pre',JSON.stringify(s,null,2));
                    botao(detalhe,'Abrir situação atual da operação',async()=>{document.getElementById('portal-operacional').close();await root.selecionarOperacao(r.id_operacao);},{valido:ctx.atual});
                },{valido:ctx.atual});}
            if(offset>0)botao(lista,'Consultas anteriores na lista',()=>{offset=Math.max(0,offset-20);return carregar();},{valido:ctx.atual});
            if(d.proximo_offset!==null)botao(lista,'Mais consultas',()=>{offset=d.proximo_offset;return carregar();},{valido:ctx.atual});
        };await carregar();
    }
    root.FluxoPainel={el,campo,status,botao,enviar,ler,lerMedidas,formularioCustos,formularioMedidas,erro,limpar,exibir,selecionada:()=>atual?.dados||null};
    root.PortalOperacional.registrarSecao('consultas','Histórico de consultas',historico);
})(window);
