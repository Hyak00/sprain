(function(root){
    'use strict';const U=root.FluxoPainel,D=root.PortalDados;let geracao=0,controle,cache=null,recebido=0,pendente=null;
    const cores={HISTORICO:'#fb923c',PREVISAO:'#facc15',SIMULACAO:'#38bdf8',TRANSITO_OBSERVADO:'#22c55e',OCORRENCIA_CONFIRMADA:'#ef4444',RELATO_NAO_VALIDADO:'#c084fc',INCERTO:'#cbd5e1'};
    const vazio=()=>({type:'FeatureCollection',features:[]});
    function limpar(){geracao++;controle?.abort();cache=null;pendente=null;recebido=0;map.getSource('mvp-eventos')?.setData(vazio());}
    async function consultar(forcar=false){
        if(!forcar&&cache&&Date.now()-recebido<10000)return cache;
        if(pendente)return pendente;
        const atual=geracao;controle=new AbortController();
        const tarefa=(async()=>{try{const r=await root.PainelSessao.request('/api/v1/painel/eventos',{signal:controle.signal});const d=await r.json();
            if(atual!==geracao)throw Object.assign(new Error(),{silencioso:true});
            if(!Array.isArray(d.items)||!Array.isArray(d.mapa?.features))throw Error('Resposta de eventos inválida.');cache=d;recebido=Date.now();map.getSource('mvp-eventos')?.setData(d.mapa);return d;
        }catch(e){if(atual===geracao){cache=null;map.getSource('mvp-eventos')?.setData(vazio());}throw e;}finally{if(atual===geracao)pendente=null;}})();pendente=tarefa;return tarefa;
    }
    const instalar=()=>{map.addSource('mvp-eventos',{type:'geojson',data:cache?.mapa||vazio()});
        const cor=['match',['get','natureza'],...Object.entries(cores).flat(), '#cbd5e1'];
        for(const [id,tipo,filtro,paint]of [['mvp-eventos-linhas','line',['==',['geometry-type'],'LineString'],{'line-color':cor,'line-width':6,'line-opacity':0.6}],['mvp-eventos-pontos','circle',['==',['geometry-type'],'Point'],{'circle-color':cor,'circle-radius':8,'circle-stroke-width':2,'circle-stroke-color':'#0f172a'}]]){
            map.addLayer({id,type:tipo,source:'mvp-eventos',filter:filtro,paint});map.on('click',id,e=>{const props=e.features?.[0]?.properties;if(!props)return;const p=document.createElement('div');p.style.color='#0f172a';U.el(p,'strong',props.natureza);U.el(p,'p','Fonte: '+props.fonte);U.el(p,'p','Atualização: '+D.data(props.atualizacao));U.el(p,'p','Localização associada ao registro; extensão e efeito na viagem precisam de conferência.');new maplibregl.Popup().setLngLat(e.lngLat).setDOMContent(p).addTo(map);});
        }
    };if(map.loaded())instalar();else map.on('load',instalar);
    const legenda=document.createElement('details');U.el(legenda,'summary','Natureza das informações e ocorrências');for(const[n,c]of Object.entries(cores)){const p=U.el(legenda,'p','● '+n.replaceAll('_',' '));p.style.color=c;}U.el(legenda,'p','Histórico ≠ previsão ≠ observação ≠ confirmação. Relatos pendentes não bloqueiam rotas automaticamente.');document.querySelector('.map-legend').appendChild(legenda);
    async function tela(p,ctx){
        U.el(p,'p','Relato privado da empresa, pendente de validação. Não confirma interdição nem bloqueia automaticamente a malha. Use o feedback do alerta existente para reportar um alerta errado.');
        const form=U.el(p,'form');form.onsubmit=e=>e.preventDefault();const label=U.el(form,'label','Tipo da ocorrência '),categoria=U.el(label,'select');categoria.setAttribute('aria-label','Tipo da ocorrência');for(const x of ['ALAGAMENTO','TRANSITO','PONTE','OUTRO'])U.el(categoria,'option',x).value=x;
        const desc=U.el(form,'label','Descrição do que foi observado '),texto=U.el(desc,'textarea');texto.required=true;texto.minLength=5;texto.maxLength=1000;
        const data=U.campo(form,'ocorrido_em','Data/hora observada (horário do seu navegador)','datetime-local','',{required:''});
        const lat=U.campo(form,'latitude','Latitude do relato','number','',{required:'',min:-90,max:90,step:'any'}),lon=U.campo(form,'longitude','Longitude do relato','number','',{required:'',min:-180,max:180,step:'any'});
        U.botao(form,'Usar origem da operação selecionada',()=>{const c=U.selecionada()?.coordenadas;if(!c)throw Error('Selecione uma operação primeiro.');lat.value=c.origem_lat;lon.value=c.origem_lon;},{valido:ctx.atual});
        const feedback=U.status(p,'Informe somente informações observadas; confiança e confirmação não serão inventadas.');
        U.botao(form,'Registrar ocorrência não detectada',async()=>{if(!form.reportValidity())return;const horario=new Date(data.value);if(!Number.isFinite(horario.getTime())||horario.getTime()>Date.now()+300000)throw Error('Confira a data/hora, sem data futura.');
            await U.enviar('/relatos',{categoria:categoria.value,descricao:texto.value.trim(),ocorrido_em:horario.toISOString(),latitude:Number(lat.value),longitude:Number(lon.value)});if(!ctx.atual())return;
            feedback.textContent='Relato registrado como pendente de validação. Atualizando ocorrências do mapa…';await consultar(true);if(ctx.atual())feedback.textContent='Relato registrado e exibido no mapa, identificado como não validado.';
        },{escrita:true,valido:ctx.atual});
        if(!root.PainelSessao.podeEscrever())form.querySelectorAll('input,select,textarea').forEach(i=>i.disabled=true);
    }
    root.PainelEventos={consultar,limpar};root.PortalOperacional.registrarSecao('relatos','Reportar ocorrência',tela);
})(window);
