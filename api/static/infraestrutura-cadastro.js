/* Manutencao opcional por ADMIN, dentro da aba Minha Frota existente. */
window.CadastroInfra = (()=>{
    'use strict';
    let pontos=[],id=null,geracao=0,escolhendo=false;
    const painel=document.createElement('details');painel.className='infra-complemento';painel.hidden=true;
    painel.id='infra-cadastro';
    document.querySelector('#frota-panel .panel-card').appendChild(painel);
    function el(tag,parent,text){const e=document.createElement(tag);if(text)e.textContent=text;parent.appendChild(e);return e;}
    el('summary',painel,'Administrar pedágios e pontes (ADMIN)');
    el('p',painel,'Registre apenas dados conferidos, com fonte e validade. Referências OSM não confirmam tarifas ou passagem. Depois de corrigir, simule novamente as operações.');
    const lista=el('select',painel);lista.className='ctrl-input';
    lista.id='infra-cadastro-lista';
    const carregar=el('button',painel,'Carregar referências');carregar.type='button';carregar.className='btn-top';
    const form=el('form',painel);form.className='infra-grid';
    const campos={};
    function campo(k,nome,tipo='text'){
        const l=el('label',form,nome),i=el('input',l);i.type=tipo;i.className='ctrl-input';campos[k]=i;return i;
    }
    const label=el('label',form,'Tipo'),tipo=el('select',label);tipo.className='ctrl-input';
    [['PEDAGIO','Pedágio'],['PONTE','Ponte / passagem restrita']].forEach(([v,n])=>{el('option',tipo,n).value=v;});
    campo('nome','Nome').required=true;
    ['longitude','latitude'].forEach(k=>{campo(k,k==='latitude'?'Latitude':'Longitude','number').step='any';campos[k].required=true;});
    campo('id_trecho','ID do trecho associado','number').required=true;
    const escolher=el('button',painel,'Escolher localização no mapa');escolher.type='button';escolher.className='btn-top';
    const proximos=el('button',painel,'Localizar trechos próximos');proximos.type='button';proximos.className='btn-top';
    const candidatos=el('select',painel);candidatos.className='ctrl-input';
    [['tarifa_por_eixo','Tarifa por eixo (R$)'],['altura_max_m','Altura máxima (m)'],['largura_max_m','Largura máxima (m)'],
        ['comprimento_max_m','Comprimento máximo (m)'],['peso_max_t','Peso máximo (t)']].forEach(([k,n])=>{
        const i=campo(k,n,'number');i.step='any';i.min=k==='tarifa_por_eixo'?0:0.01;
    });
    campo('tarifas_por_eixos','Tabela por eixos (JSON opcional, exemplo: {"2":"23.30","5":"58.30"})');
    campo('fonte','Fonte confirmada (documento ou link)').required=true;
    campo('grupo_cobranca','Grupo da mesma praca (opcional, evita contar cabines duas vezes)');
    ['verificado_em','valido_ate'].forEach(k=>campo(k,k==='verificado_em'?'Consulta realizada em':'Revisar até','datetime-local').required=true);
    const salvar=el('button',form,'Salvar cadastro confirmado');salvar.type='submit';salvar.className='btn-top';
    const historico=el('button',painel,'Ver histórico');historico.type='button';historico.className='btn-top';
    const desativar=el('button',painel,'Desativar referência');desativar.type='button';desativar.className='btn-top';
    const status=el('p',painel);status.setAttribute('role','status');
    function preparar(f){
        id=f?.properties.id??null; const p=f?.properties||{};
        tipo.value=p.tipo||'PEDAGIO';
        Object.entries(campos).forEach(([k,i])=>{
            let v=p[k]??'';
            if(k==='longitude'||k==='latitude')v=f?.geometry.coordinates[k==='longitude'?0:1]??'';
            if(i.type==='datetime-local'){
                const d=v?new Date(v):new Date(Date.now()+(k==='valido_ate'?7*86400000:0));
                v=new Date(d-d.getTimezoneOffset()*60000).toISOString().slice(0,16);
            }
            if(k==='fonte'&&p.origem_dados==='REFERENCIA_OSM')v='';
            if(k==='tarifas_por_eixos' && v && typeof v==='object')v=JSON.stringify(v);
            i.value=v;
        });
        historico.disabled=desativar.disabled=id===null;
        status.textContent=p.origem_dados==='REFERENCIA_OSM'?'Para confirmar esta referência, informe a fonte consultada e a validade.':'';
    }
    async function request(path,method='GET',body){
        const g=geracao,r=await window.PainelSessao.request('/api/v1/'+path,{method,headers:{'X-API-Key':window.API_KEY,'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});
        const data=await r.json();if(g!==geracao)throw new Error('A sessão mudou.');
        if(!r.ok)throw new Error(typeof data.detail==='string'?data.detail:'Confira os campos, a associação e sua permissão.');return data;
    }
    async function carregarPontos(){
        const data=await request('infraestrutura/pontos?limite=500');pontos=data.features;lista.replaceChildren();
        el('option',lista,'Novo ponto').value='';
        pontos.forEach(f=>el('option',lista,f.properties.tipo+' · '+f.properties.nome+' #'+f.properties.id).value=f.properties.id);
        preparar(null);if(data.proximo_depois_id)status.textContent='Primeiras 500 referências; outras páginas disponíveis pela API.';
    }
    async function executar(fn){try{await fn();}catch(e){if(!e.silencioso)status.textContent=e.message;}}
    carregar.onclick=()=>executar(carregarPontos);
    lista.onchange=()=>preparar(pontos.find(f=>String(f.properties.id)===lista.value));
    proximos.onclick=()=>executar(async()=>{
        const lon=Number(campos.longitude.value),lat=Number(campos.latitude.value);
        if(!campos.longitude.value||!campos.latitude.value)throw new Error('Informe latitude e longitude ou escolha no mapa.');
        const data=await request('infraestrutura/malha/trechos-proximos?somente_regional=false&longitude='+lon+'&latitude='+lat);
        candidatos.replaceChildren();el('option',candidatos,'Escolha a pista correta').value='';
        data.candidatos.forEach(c=>el('option',candidatos,'#'+c.id_trecho+' · '+(c.name||'Sem nome')+' · '+Math.round(c.distancia_m)+' m').value=c.id_trecho);
        status.textContent=data.aviso;
    });
    candidatos.onchange=()=>campos.id_trecho.value=candidatos.value;
    escolher.onclick=()=>{escolhendo=true;status.textContent='Clique no mapa no local da estrutura. Confira a pista associada.';};
    map.on('click',e=>{if(!escolhendo||painel.hidden)return;escolhendo=false;campos.longitude.value=e.lngLat.lng;campos.latitude.value=e.lngLat.lat;});
    form.onsubmit=e=>{e.preventDefault();executar(async()=>{
        const payload={tipo:tipo.value,origem_dados:'CADASTRO_MANUAL'};
        Object.entries(campos).forEach(([k,i])=>{
            if(i.type==='datetime-local')payload[k]=new Date(i.value).toISOString();
            else if(i.type==='number')payload[k]=i.value===''?null:Number(i.value);
            else payload[k]=i.value.trim();
        });
        payload.tarifas_por_eixos=payload.tarifas_por_eixos?JSON.parse(payload.tarifas_por_eixos):null;
        if(!payload.grupo_cobranca)payload.grupo_cobranca=null;
        if(tipo.value==='PEDAGIO')['altura_max_m','largura_max_m','comprimento_max_m','peso_max_t'].forEach(k=>payload[k]=null);
        else {payload.tarifa_por_eixo=null;payload.tarifas_por_eixos=null;}
        await request('infraestrutura/pontos'+(id===null?'':'/'+id),id===null?'POST':'PUT',payload);
        await carregarPontos();status.textContent='Cadastro salvo. Recalcule as operações para considerar a atualização.';
    });};
    historico.onclick=()=>executar(async()=>{const data=await request('infraestrutura/pontos/'+id+'/historico');status.textContent=JSON.stringify(data,null,2);});
    desativar.onclick=()=>executar(async()=>{await request('infraestrutura/pontos/'+id,'DELETE');await carregarPontos();status.textContent='Referência desativada; histórico preservado. Recalcule as operações.';});
    return {sessao:role=>{geracao++;escolhendo=false;painel.hidden=role!=='ADMIN';painel.open=false;pontos=[];lista.replaceChildren();preparar(null);}};
})();
