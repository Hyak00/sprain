/* O modo vem do servidor/banco, nunca de um parâmetro de URL ou papel da conta. */
(function(root){
    'use strict';
    const D=root.PortalDados;let estadoAtual=null,geracao=0,observador,exibindo=false;
    const el=(p,t,s)=>{const e=document.createElement(t);if(s!==undefined)e.textContent=s;p.appendChild(e);return e;};
    const faixa=el(document.body,'div');faixa.id='demo-faixa';faixa.hidden=true;faixa.setAttribute('role','status');
    const legenda=el(document.querySelector('.map-legend'),'p','Exercício sintético: linha roxa original e linha laranja alternativa. Não são vias reais do evento.');legenda.hidden=true;
    function atualizarFaixa(texto){faixa.textContent=texto;faixa.hidden=false;document.body.classList.add('demo-identificada');
        const ajustar=()=>document.body.style.setProperty('--demo-faixa-altura',faixa.getBoundingClientRect().height+'px');ajustar();
        if(root.ResizeObserver&&!observador){observador=new root.ResizeObserver(ajustar);observador.observe(faixa);}
    }
    async function carregarEstado(){
        try{const r=await root.PainelSessao.request('/api/v1/demonstracao/estado',{publico:true,timeout:5000});estadoAtual=await r.json();
            if(estadoAtual.demo_isolada){atualizarFaixa(estadoAtual.aviso);const aviso=document.querySelector('.portal-aviso');if(aviso){aviso.hidden=false;aviso.textContent=estadoAtual.aviso;}}
            else{faixa.hidden=true;document.body.classList.remove('demo-identificada');document.body.style.removeProperty('--demo-faixa-altura');}
        }catch(e){atualizarFaixa('Não foi possível verificar o ambiente. Demonstração desabilitada; confira o servidor antes de apresentar dados como reais.');}
    }
    const vazio=()=>({type:'FeatureCollection',features:[]});
    function limparMapa(){geracao++;exibindo=false;for(const id of ['demo34-original','demo34-alternativa'])map.getSource(id)?.setData(vazio());legenda.hidden=true;}
    function mostrarMapa(d){
        exibindo=true;
        const n=geracao,tenant=root.PainelSessao.empresa();
        const instalar=()=>{
            if(n!==geracao||tenant!==root.PainelSessao.empresa())return;
            const geometrias=[['demo34-original',d.rota_original?.geojson,'#c084fc'],['demo34-alternativa',d.rota_alternativa?.geojson,'#fb923c']];
            const coords=[];
            for(const[id,geo,cor]of geometrias){if(!map.getSource(id)){map.addSource(id,{type:'geojson',data:vazio()});map.addLayer({id,type:'line',source:id,paint:{'line-color':cor,'line-width':5,'line-dasharray':[2,2]}});}
                map.getSource(id).setData(geo||vazio());for(const f of geo?.features||[])if(f.geometry?.type==='LineString')coords.push(...f.geometry.coordinates);}
            legenda.hidden=false;
            if(coords.length){const lons=coords.map(c=>c[0]),lats=coords.map(c=>c[1]);map.fitBounds([[Math.min(...lons),Math.min(...lats)],[Math.max(...lons),Math.max(...lats)]],{padding:60,duration:0});}
        };if(map.loaded())instalar();else map.once('load',instalar);
    }
    async function render(p,ctx){
        const avisar=s=>{const e=el(p,'p',s);e.setAttribute('role','status');return e;};
        if(!estadoAtual)await carregarEstado();if(!ctx.atual())return;
        if(!estadoAtual?.demo_isolada){avisar('Exercício bloqueado neste ambiente. Inicie a composição dedicada com python scripts/iniciar_demo_caminhoes.py e abra http://127.0.0.1:18000/static/b2b.html. A base operacional não será preparada por esta tela.');return;}
        el(p,'strong','DEMONSTRAÇÃO ISOLADA — referência histórica e exercício sintético');
        const r=await ctx.obter('/api/v1/demonstracao/referencia');if(!ctx.atual())return;
        el(p,'h4',r.titulo);el(p,'p',r.resumo);el(p,'p',r.rodovia+' · km publicado '+r.km_publicado+' · '+r.municipio+' · sentido '+r.sentido);
        const a=el(p,'a','Consultar fonte oficial: '+r.fonte_nome);a.href=r.fonte_url;a.target='_blank';a.rel='noopener noreferrer';
        el(p,'p','Origem da referência: pesquisa pública; o evento originalmente pretendido pela equipe não foi identificado. Consulta à fonte: '+r.consultado_em+'. Última atualização publicada: '+r.atualizacao_fonte_publicada+' (horário literal).');
        ctx.tabela(p,['Horário publicado (literal)','Fato histórico'],r.marcos.map(m=>[m.horario_publicado,m.fato]));
        const lista=el(p,'ul');r.incognitas.forEach(s=>el(lista,'li',s));
        el(p,'h4','Exercício sobre malha sintética');el(p,'p','Compare o mesmo caminhão de exemplo com e sem um bloqueio ilustrativo. As medidas, custos, nós e geometria são didáticos; não são a localização comprovada do km 205. A chuva matemática é zero para isolar o efeito do bloqueio.');
        const status=avisar('Prepare o exemplo uma vez com o script ou com um ADMIN de demo_corp. Depois, todos os papéis dessa empresa podem reproduzi-lo.');
        const resultado=el(p,'div');let consulta=0,ocupado=false;const controles=[];
        function botao(label,fn,permitido=()=>true){const b=el(p,'button',label);b.type='button';b.disabled=!permitido();b.onclick=async()=>{
            if(ocupado||b.disabled||!ctx.atual()||!permitido())return;ocupado=true;controles.forEach(c=>c.b.disabled=true);b.setAttribute('aria-busy','true');
            try{await fn();}catch(e){if(ctx.atual()&&!e?.silencioso)status.textContent=e?.name==='ErroPainel'?e.message:'Não foi possível concluir. Confira se os dados foram preparados e tente novamente.';}
            finally{ocupado=false;if(ctx.atual()){controles.forEach(c=>c.b.disabled=!c.permitido());b.removeAttribute('aria-busy');}}
        };controles.push({b,permitido});return b;}
        const tenantDemo=()=>root.PainelSessao.empresa()==='demo_corp';
        botao('Preparar dados sintéticos',async()=>{
            status.textContent='Preparando somente o banco reservado…';const res=await root.PainelSessao.request('/api/v1/demonstracao/preparar',{method:'POST'});const d=await res.json();
            if(ctx.atual())status.textContent='Exemplo preparado: '+d.id_operacao+'. Repetir a preparação não duplica nem sobrescreve cadastros.';
        },()=>tenantDemo()&&root.PainelSessao.perfil()==='ADMIN');
        for(const [etapa,label]of [['SEM_BLOQUEIO','1. Simular sem bloqueio'],['BLOQUEIO','2. Simular bloqueio ilustrativo'],['LIBERACAO','3. Simular liberação']]){
            botao(label,async()=>{const n=++consulta;status.textContent='Calculando o exercício no motor existente…';resultado.replaceChildren();
                const res=await root.PainelSessao.request('/api/v1/demonstracao/reproduzir',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({etapa})});const d=await res.json();
                if(!ctx.atual()||n!==consulta)return;status.textContent=d.aviso;
                const f=d.financeiro||{},m=d.comparativo_rotas;
                ctx.tabela(resultado,['Medida do exercício','Original sintética','Alternativa calculada'],[
                    ['Distância (km)',m.rota_original_km,m.rota_alternativa_km],['Tempo nominal (min)',m.tempo_original_min,m.tempo_alternativo_min],
                    ['Custo estimado conhecido (R$)',D.moeda(f.custo_original_conhecido_brl),D.moeda(f.custo_alternativa_conhecido_brl)]]);
                el(resultado,'p','Diferença estimada de custo: '+D.moeda(f.custo_desvio_brl)+'. Economia comprovada: indisponível. As medidas e custos são exemplos, não observações do evento.');
                if(!d.rota_original||!d.rota_alternativa)el(resultado,'p','Sem rota disponível na malha atual do exercício; nenhuma distância substituta foi atribuída.');
                const ver=el(resultado,'button','Ver exercício sintético no mapa');ver.type='button';ver.onclick=()=>{if(!ctx.atual())return;limparMapa();mostrarMapa(d);document.getElementById('portal-operacional').close();};
            },tenantDemo);
        }
        botao('Limpar exercício do mapa',()=>{limparMapa();status.textContent='Camadas do exercício removidas. Nenhum alerta ou cadastro foi apagado.';});
        if(!tenantDemo())avisar('Entre na empresa de demonstração demo_corp para usar este exercício. Nenhum dado de outra empresa será alterado.');
    }
    root.PainelDemonstracao={render,limparMapa,marcaMapa:()=>geracao,emExibicao:()=>exibindo,estado:()=>estadoAtual};
    carregarEstado();
})(window);
