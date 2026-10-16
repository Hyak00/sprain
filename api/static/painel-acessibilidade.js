/* Teclado, rótulos e camadas sem substituir os controles operacionais. */
(function(){
    'use strict';
    function rotulos(){
        document.querySelectorAll('.ctrl-group').forEach(g=>{
            const titulo=g.querySelector('.ctrl-label');if(!titulo)return;
            g.querySelectorAll('input:not([type="hidden"]),select').forEach(c=>{if(!c.getAttribute('aria-label'))c.setAttribute('aria-label',titulo.textContent.trim());});
        });
        document.querySelectorAll('button').forEach(b=>{if(b.textContent.trim()==='×')b.setAttribute('aria-label',b.closest('#modal-despacho')?'Fechar despacho':'Fechar detalhes da operação');});
        const busca=document.getElementById('input-busca');if(busca)busca.setAttribute('aria-label','Buscar operação ou caminhão');
        document.getElementById('input-motivo-gestor')?.setAttribute('aria-label','Motivo da decisão do gestor');
        document.querySelectorAll('#grid-operacoes tr').forEach(tr=>{if(tr.querySelector('td')&&tr.onclick){tr.tabIndex=0;tr.setAttribute('aria-label','Inspecionar '+tr.textContent.trim());}});
    }
    rotulos();new MutationObserver(rotulos).observe(document.getElementById('sidebar'),{childList:true,subtree:true});
    document.getElementById('grid-operacoes').addEventListener('keydown',e=>{if(e.target.tagName==='TR'&&['Enter',' '].includes(e.key)){e.preventDefault();e.target.click();}});
    const despacho=document.getElementById('modal-despacho');despacho.setAttribute('role','dialog');despacho.setAttribute('aria-modal','true');despacho.setAttribute('aria-label','Despachar nova rota');
    let anterior,aberto=false;
    new MutationObserver(()=>{
        const visivel=despacho.style.display==='flex';
        if(visivel&&!aberto){anterior=document.activeElement;document.querySelectorAll('header,.workspace').forEach(x=>x.inert=true);despacho.querySelector('input:not([type="hidden"])')?.focus();}
        if(!visivel&&aberto){window.PainelSessao.permissoes();if(anterior?.isConnected)anterior.focus();}aberto=visivel;
    }).observe(despacho,{attributes:true,attributeFilter:['style']});
    despacho.addEventListener('keydown',e=>{
        if(e.key==='Escape'){e.preventDefault();fecharModalDespacho();return;}
        if(e.key!=='Tab')return;
        const controles=Array.from(despacho.querySelectorAll('button,input:not([type="hidden"]),select,textarea,summary')).filter(c=>!c.disabled&&c.getClientRects().length);
        if(!controles.length)return;const primeiro=controles[0],ultimo=controles[controles.length-1];
        if(e.shiftKey&&document.activeElement===primeiro){e.preventDefault();ultimo.focus();}else if(!e.shiftKey&&document.activeElement===ultimo){e.preventDefault();primeiro.focus();}
    });
    const detalhes=document.createElement('details');detalhes.className='portal-camadas';const resumo=document.createElement('summary');resumo.textContent='Controlar camadas do mapa';detalhes.appendChild(resumo);document.querySelector('.map-legend').appendChild(detalhes);
    for(const [id,titulo]of [['layer-rota-original','Rota original (tracejada)'],['layer-rota-segura','Alternativa (azul)'],['layer-trechos-criticos','Trechos críticos (vermelho espesso)'],['infra-pontos','Pedágios e limites cadastrados'],['infra-limites','Estruturas e restrições'],['dados-viagem','Postos e histórico'],['mvp-eventos-linhas','Ocorrências nos trechos'],['mvp-eventos-pontos','Relatos georreferenciados']]){
        const label=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.checked=true;label.append(input,document.createTextNode(titulo));detalhes.appendChild(label);
        input.onchange=()=>{if(map.getLayer(id))map.setLayoutProperty(id,'visibility',input.checked?'visible':'none');};
    }
    const pesquisar={orig:0,dest:0},pendentes={orig:null,dest:null};
    ['orig','dest'].forEach(tipo=>{
        document.getElementById('status-geo-'+tipo).textContent='Selecione uma sugestão para confirmar a coordenada.';
        document.getElementById('desp-'+tipo+'-nome').addEventListener('input',()=>{
            document.getElementById('desp-'+tipo+'-lat').value='0';document.getElementById('desp-'+tipo+'-lon').value='0';
            document.getElementById('status-geo-'+tipo).textContent='Endereço alterado; confirme uma sugestão da malha.';
        });
    });
    // Mesmo endpoint e seleção; respostas antigas não podem substituir a busca atual.
    window.buscarViaAutocomplete=async function(tipo,termo){
        const n=++pesquisar[tipo],ep=window.SESSION_EPOCH,drop=document.getElementById('ac-'+tipo);pendentes[tipo]?.abort();drop.replaceChildren();
        if(!termo.trim()){drop.style.display='none';return;}
        pendentes[tipo]=new AbortController();
        const r=await window.PainelSessao.request('/api/v1/logistica/vias/buscar?q='+encodeURIComponent(termo),{signal:pendentes[tipo].signal}),vias=await r.json();
        if(n!==pesquisar[tipo]||ep!==window.SESSION_EPOCH||document.getElementById('desp-'+tipo+'-nome').value!==termo)return;
        drop.replaceChildren();
        if(!Array.isArray(vias)||!vias.length){drop.style.display='none';document.getElementById('status-geo-'+tipo).textContent='Nenhuma sugestão retornada para este texto.';return;}
        vias.forEach(v=>{
            const b=document.createElement('button');b.type='button';b.className='ac-item';b.style.width='100%';b.style.textAlign='left';
            b.textContent=v.nome_via+' · IVI '+v.ivi_medio+' ('+v.classe_risco+')';
            b.onclick=()=>{selecionarViaAutocomplete(tipo,v.nome_via,v.lat,v.lon);document.getElementById('desp-'+tipo+'-nome').focus();};drop.appendChild(b);
        });drop.style.display='block';
    };
    window.PainelAcessibilidade={limpar:()=>{for(const tipo of ['orig','dest']){pesquisar[tipo]++;pendentes[tipo]?.abort();document.getElementById('ac-'+tipo).replaceChildren();}}};
})();
