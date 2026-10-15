/* Complemento da torre existente: nao substitui abas, filtros, mapa ou auditoria. */
window.InfraCaminhoes = (() => {
    'use strict';
    const medidas = [['altura_m','Altura (m)',10],['largura_m','Largura (m)',10],
        ['comprimento_m','Comprimento (m)',100],['peso_total_t','Peso com carga (t)',300],['eixos','Eixos',15]];
    const custos = [['custo_por_km','Custo por km (R$)'],['custo_hora_motorista','Motorista / hora (R$)'],
        ['custo_operacional_veiculo_hora','Veículo / hora (R$)'],['prejuizo_potencial_alagamento','Perda potencial por alagamento (R$)']];
    custos.push(['consumo_km_l','Consumo com carga (km/L)'],['preco_combustivel_litro','Preco de referencia do diesel (R$/L)'],['custo_por_km_sem_combustivel','Custo por km SEM combustivel (R$)']);
    custos.push(['custo_atraso_hora','Custo contratual por hora de atraso (R$)']);
    const money = n => n == null ? 'A confirmar' : Number(n).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
    let epoch=0;
    let pontos={type:'FeatureCollection',features:[]};
    let limitesMapa={type:'FeatureCollection',features:[]};
    function limitesTexto(valor) {
        let dados=valor;
        if(typeof dados==='string') {try{dados=JSON.parse(dados);}catch{return 'Limites a conferir';}}
        const nomes={altura_max_m:'Altura máxima (m)',largura_max_m:'Largura máxima (m)',comprimento_max_m:'Comprimento máximo (m)',peso_max_t:'Peso máximo (t)'};
        return Object.entries(dados||{}).map(([k,v])=>(nomes[k]||'Limite')+': '+v).join(' · ');
    }
    function texto(el,tag,value) { const child=document.createElement(tag); child.textContent=value; el.appendChild(child); return child; }
    function formulario(id,titulo,parent) {
        const box=document.createElement('details'); box.id=id; box.className='infra-complemento';
        texto(box,'summary',titulo);
        texto(box,'p','Preencha medidas reais, incluindo a carga. Campos vazios mantêm o cadastro existente. Sem limites confirmados, a passagem exige conferência.');
        const grid=document.createElement('div'); grid.className='infra-grid'; box.appendChild(grid);
        [...medidas,...custos].forEach(([campo,nome,max])=>{
            const label=texto(grid,'label',nome); const input=document.createElement('input');
            input.id=id+'-'+campo; input.type='number'; input.className='ctrl-input mono';
            input.min=medidas.some(m=>m[0]===campo)?(campo==='eixos'?2:0.01):0;
            input.step=campo==='eixos'?1:'any'; if(max) input.max=max;
            label.appendChild(input);
        });
        texto(box,'p','Custos próprios substituem as premissas gerais para este caminhão/viagem. Perda potencial é uma premissa, não uma perda real nem economia garantida.');
        const data=texto(box,'label','Data de coleta do preco (quando pesquisado)');const input=document.createElement('input');input.type='date';input.id=id+'-combustivel_data_coleta';input.className='ctrl-input';data.appendChild(input);
        texto(box,'p','Custos opcionais: em branco, o sistema estima consumo e custo do diesel com a referencia ANP de SP. Informe o consumo real para melhorar a estimativa. O custo total por km informado tem prioridade; nao soma combustivel novamente.');
        parent.appendChild(box); return box;
    }
    function ler(id) {
        const values = lista => Object.fromEntries(lista.map(([k])=>[k,document.getElementById(id+'-'+k).value])
            .filter(([,v])=>v!=='').map(([k,v])=>[k,Number(v)]));
        const dims=values(medidas), cs=values(custos);
        const data=document.getElementById(id+'-combustivel_data_coleta').value;
        if(data)cs.combustivel_data_coleta=data;
        if(Object.keys(dims).length && Object.keys(dims).length!==5) throw new Error('Informe as cinco medidas do caminhão, ou deixe todas vazias para usar o cadastro.');
        for(const [k,v] of Object.entries({...dims,...cs}).filter(([k])=>k!=='combustivel_data_coleta')) {
            const input=document.getElementById(id+'-'+k);
            if(!Number.isFinite(v)||!input.checkValidity()) throw new Error('Confira o valor de '+input.parentElement.firstChild.textContent+'.');
        }
        return {...(Object.keys(dims).length?{dimensoes:dims}:{}),...(Object.keys(cs).length?{custos_operacionais:cs}:{})};
    }
    function preencher(id,v={}) {
        document.getElementById(id+'-combustivel_data_coleta').value=v.custos_operacionais?.combustivel_data_coleta||'';
        [...medidas,...custos].forEach(([k])=>document.getElementById(id+'-'+k).value=
            v.dimensoes?.[k]??v.custos_operacionais?.[k]??'');
    }
    function carregarVeiculo(v) {
        ['id','placa','modelo'].forEach(k=>document.getElementById('veic-'+k).value=v[k==='id'?'id_veiculo':k]);
        document.getElementById('veic-tipo').value=v.tipo_veiculo;
        preencher('infra-veic',v); document.getElementById('infra-veic').open=true;
    }
    function frota(lista) {
            const cards=document.querySelectorAll('#lista-frota-cards > div');
        lista.forEach((v,i)=>{
            if(!cards[i]) return;
            const btn=texto(cards[i],'button','Medidas e custos'); btn.className='btn-top';
            btn.onclick=()=>carregarVeiculo(v);
        });
        const atual=lista.find(v=>v.id_veiculo===document.getElementById('desp-veiculo').value);
        preencher('infra-desp',atual);
        const sel=document.getElementById('infra-corredor-veiculo');
        const anterior=sel.value; sel.replaceChildren();
        const opt=texto(sel,'option','Escolha um caminhão cadastrado'); opt.value='';
        lista.forEach(v=>{const o=texto(sel,'option',v.placa+' · '+v.modelo);o.value=v.id_veiculo;});
        sel.value=anterior;
    }
    function limpar() {
        window.DadosViagem?.limpar();
        epoch++; pontos={type:'FeatureCollection',features:[]};
        window.SESSION_EPOCH=epoch;
        limitesMapa={type:'FeatureCollection',features:[]};
        if(map.getSource('infra-pontos')) map.getSource('infra-pontos').setData(pontos);
        if(map.getSource('infra-limites')) map.getSource('infra-limites').setData(pontos);
        document.getElementById('infra-auditoria').replaceChildren();
        ['infra-veic','infra-desp','infra-corredor'].forEach(id=>preencher(id));
    }
    function mapa(info) {
        const orig=info?.original?.pontos_mapa?.features||[];
        const alt=info?.alternativa?.pontos_mapa?.features||[];
        const porId=new Map();
        [...orig,...alt].forEach(f=>porId.set(f.properties.id,f));
        pontos={type:'FeatureCollection',features:[...porId.values()]};
        if(map.getSource('infra-pontos')) map.getSource('infra-pontos').setData(pontos);
        const limites=new Map();
        [...(info?.original?.limites_mapa?.features||[]),...(info?.alternativa?.limites_mapa?.features||[])].forEach(f=>limites.set(f.properties.id_trecho,f));
        limitesMapa={type:'FeatureCollection',features:[...limites.values()]};
        map.getSource('infra-limites')?.setData(limitesMapa);
    }
    function mostrar(parent,info) {
        parent.replaceChildren(); if(!info) return;
        texto(parent,parent.tagName==='DETAILS'?'summary':'strong','Pedágios, caminhão e restrições');
        const dims=info.dimensoes;
        if(info.custo_planejado_conhecido_brl!=null)texto(parent,'p','Custo conhecido do planejamento salvo: '+money(info.custo_planejado_conhecido_brl)+'. Tarifas pendentes podem alterar esse valor.');
        texto(parent,'p',dims?`${dims.altura_m} m de altura · ${dims.largura_m} m de largura · ${dims.comprimento_m} m de comprimento · ${dims.peso_total_t} t com carga · ${dims.eixos} eixos`:
            'Medidas do caminhão não informadas. Não há liberação automática de pontes.');
        [['Original',info.original],['Alternativa',info.alternativa]].forEach(([nome,rota])=>{
            if(!rota) return;
            const p=rota.pedagios;
            texto(parent,'p',`${nome}: ${p.quantidade_cadastrada_na_rota} referência(s) de pedágio · subtotal ${p.quantidade_cadastrada_na_rota && p.tarifas_pendentes===p.quantidade_cadastrada_na_rota?'a confirmar':money(p.subtotal_conhecido_reais)} · ${p.tarifas_pendentes} tarifa(s) pendente(s). Cobertura parcial.`);
            if(rota.estruturas_referencia?.length)texto(parent,'p',`${nome}: ${rota.estruturas_referencia.length} ponte(s), viaduto(s) ou tunel(is) identificados na propria via; ${rota.estruturas_sem_limites_completos} sem os quatro limites publicados. Conferir capacidade antes de autorizar a viagem.`);
            if(rota.trechos_incompativeis?.length) texto(parent,'p',`${rota.trechos_incompativeis.length} trecho(s) incompatível(is), indisponível(is) ou sem medidas suficientes.`);
            const limites=rota.limites_mapa?.features||[];
            const grupos=new Map();
            limites.forEach(f=>{const p=f.properties,k=(p.fonte_malha||'')+JSON.stringify(p.limites_importados);
                const grupo=grupos.get(k)||{p,total:0};grupo.total++;grupos.set(k,grupo);});
            [...grupos.values()].slice(0,20).forEach(({p,total})=>texto(parent,'p',`${limitesTexto(p.limites_importados)} · ${total} segmento(s) · fonte: ${p.fonte_malha||'A confirmar'}.`));
            if(grupos.size>20) texto(parent,'p','Primeiros 20 grupos listados; todos os limites disponíveis no mapa e na API.');
        });
        const f=info.financeiro;
        if(f) {
            if(f.combustivel){const c=f.combustivel;texto(parent,'p',c.aviso+' Custo variavel por km: '+money(c.custo_por_km_aplicado));if(c.consumo_km_l)texto(parent,'p',`${c.consumo_estimado?'Consumo estimado por referencia estatistica':'Consumo informado'}: ${c.consumo_km_l} km/L · diesel ${money(c.preco_litro)}/L · coleta ${c.data_coleta||'premissa informada'}. Os custos horarios do motorista e veiculo sao calculados separadamente.`);}
            texto(parent,'p','Diferença de pedágios conhecidos: '+money(f.delta_pedagios_conhecidos_brl));
            texto(parent,'p','Economia líquida potencial, após custo do desvio: '+money(f.economia_liquida_potencial_brl));
            if(f.trechos_risco_residual_alternativa) texto(parent,'p',`${f.trechos_risco_residual_alternativa} trecho(s) continuam com risco climático no modelo da alternativa. Não foi atribuída perda por alagamento evitada a esse desvio.`);
            texto(parent,'p',f.aviso);
        } else texto(parent,'p','Sem comparação financeira disponível para esta recomendação.');
        texto(parent,'p','Dados ausentes ou vencidos exigem conferência. O mapa não autoriza a passagem.');
        mapa(info);
    }
    async function corredor(lista) {
        window.DadosViagem?.limpar();
        const atual=epoch;
        const atualizacao=corredorAtualizacao;
        const container=document.getElementById('corredor-detalhes');
        const avisoBase=document.createElement('div');avisoBase.className='panel-card';
        avisoBase.textContent='Demonstração fixa anterior: segmentos e valores de exemplo. A avaliação abaixo usa as medidas e as referências da malha real.';
        container.prepend(avisoBase);
        const veiculo=lista.find(v=>v.id_veiculo===document.getElementById('infra-corredor-veiculo').value);
        let extra;
        try {extra=ler('infra-corredor');} catch(e) {texto(avisoBase,'p',e.message);return;}
        const dims=extra.dimensoes||veiculo?.dimensoes;
        if(!dims) {
            const aviso=document.createElement('div'); aviso.className='panel-card';
            aviso.textContent='Os valores acima pertencem à demonstração fixa anterior. Escolha um caminhão e informe suas medidas para avaliar pedágios e restrições na malha real.';
            container.appendChild(aviso); mapa(null);return;
        }
        const cat=document.getElementById('sel-veiculo-corredor').value;
        const eixos=cat==='CARRETA_5_EIXOS'?5:cat==='TRUCK_3_EIXOS'?3:2;
        if(dims.eixos!==eixos) {
            texto(avisoBase,'p','A categoria selecionada não corresponde aos eixos informados. Ajuste a categoria ou o caminhão.');return;
        }
        const res=await fetch('/api/v1/infraestrutura/rota-caminhao',{
            method:'POST',headers:{'Content-Type':'application/json','X-API-Key':window.API_KEY},
            body:JSON.stringify({origem_lon:-48.1867913,origem_lat:-21.8126273,
                destino_lon:-46.7561156,destino_lat:-23.444725,veiculo:dims,perfil:'FASTEST',
                custos_operacionais:{...(veiculo?.custos_operacionais||{}),...(extra.custos_operacionais||{})}})});
        const data=await res.json(); if(atual!==epoch || atualizacao!==corredorAtualizacao || document.getElementById('corredor-panel').style.display==='none') return;
        if(!res.ok) {texto(avisoBase,'p',typeof data.detail==='string'?data.detail:'Não foi possível avaliar a rota para essas medidas.');mapa(null);return;}
        const card=document.createElement('div'); card.className='panel-card';container.appendChild(card);
        texto(card,'strong','Corredor de referência avaliado para este caminhão');
        texto(card,'p',`${data.rota.distancia_km} km · ${data.rota.tempo_min} min estimados. Pontos de referência rodoviários; confirme os endereços reais no despacho.`);
        texto(card,'p','Custo de viagem com premissas e tarifas conhecidas: '+money(data.custos?.custo_original_conhecido_brl)+'. Estimativa parcial; tarifas pendentes não estão incluídas.');
        texto(card,'p','Custo medio conhecido por km, incluindo tempo e pedagios conhecidos: '+money(data.custos?.custo_medio_original_conhecido_por_km_brl)+'/km.');
        if(data.custos?.combustivel){const c=data.custos.combustivel;texto(card,'p',`Custo variavel: ${money(c.custo_por_km_aplicado)}/km · consumo ${c.consumo_km_l||'incluido no custo total'} km/L · ${c.consumo_estimado?'estimativa estatistica; ajuste com consumo real':'premissa informada'}`);texto(card,'p',c.aviso);}
        const detalhe=document.createElement('div');card.appendChild(detalhe);
        const dados=document.createElement('details');dados.className='infra-complemento';card.appendChild(dados);
        window.DadosViagem?.exibir([data.rota.geojson],dados);
        mostrar(detalhe,{dimensoes:dims,original:data.rota.infraestrutura});
        if(map.getSource('rota-segura')) map.getSource('rota-segura').setData(data.rota.geojson);
        if(markerOrig) markerOrig.remove();if(markerDest)markerDest.remove();
        function marcador(texto,coord,cor){const e=document.createElement('div');e.className='marker-pin';e.style.background=cor;e.textContent=texto;return new maplibregl.Marker({element:e}).setLngLat(coord).addTo(map);}
        markerOrig=marcador('O',[-48.1867913,-21.8126273],'#10b981');
        markerDest=marcador('D',[-46.7561156,-23.444725],'#38bdf8');
        ['rota-original','trechos-criticos'].forEach(id=>map.getSource(id)?.setData({type:'FeatureCollection',features:[]}));
        const bounds=new maplibregl.LngLatBounds();data.rota.geojson.features.forEach(f=>f.geometry.coordinates.forEach(c=>bounds.extend(c)));
        if(!bounds.isEmpty()) map.fitBounds(bounds,{padding:70});
    }
    formulario('infra-veic','Medidas e custos do caminhão',document.querySelector('#frota-panel .panel-card'));
    const despacho=formulario('infra-desp','Medidas e custos desta viagem',document.getElementById('desp-feedback').parentElement);
    document.getElementById('desp-feedback').before(despacho);
    const parent=document.querySelector('#corredor-panel .panel-card');
    const label=texto(parent,'label','Caminhão da frota para avaliar restrições');
    const sel=document.createElement('select');sel.id='infra-corredor-veiculo';sel.className='ctrl-input';label.appendChild(sel);
    formulario('infra-corredor','Medidas do caminhão no corredor',parent);
    const btn=texto(parent,'button','Avaliar corredor para este caminhão');btn.className='btn-top';btn.onclick=()=>carregarCorredorRegional();
    sel.onchange=()=>{preencher('infra-corredor',frotaAtual.find(v=>v.id_veiculo===sel.value));};
    document.getElementById('desp-veiculo').addEventListener('change',()=>preencher('infra-desp',frotaAtual.find(v=>v.id_veiculo===document.getElementById('desp-veiculo').value)));
    const audit=document.createElement('details');audit.id='infra-auditoria';audit.className='infra-complemento';
    document.getElementById('modal-limitacao').after(audit);
    map.on('load',()=>{
        map.addSource('infra-limites',{type:'geojson',data:limitesMapa});
        map.addLayer({id:'infra-limites',type:'line',source:'infra-limites',paint:{'line-width':7,
            'line-color':['match',['get','status_limite'],'BLOQUEADO','#ef4444','#a78bfa']}});
        map.on('click','infra-limites',e=>{
            const f=e.features?.[0];if(!f)return;const p=f.properties,box=document.createElement('div');box.style.color='#111827';
            texto(box,'strong','Limite cadastrado · trecho #'+p.id_trecho);
            texto(box,'p',limitesTexto(p.limites_importados));
            texto(box,'p','Fonte: '+(p.fonte_malha||'A conferir'));texto(box,'p','Revisar até: '+(p.valido_ate||'Não informado'));
            texto(box,'p','Conferir sinalização e cadastro; não autoriza a passagem.');
            new maplibregl.Popup().setLngLat(e.lngLat).setDOMContent(box).addTo(map);
        });
        map.addSource('infra-pontos',{type:'geojson',data:pontos});
        map.addLayer({id:'infra-pontos',type:'circle',source:'infra-pontos',paint:{'circle-radius':6,
            'circle-color':['match',['get','tipo'],'PEDAGIO','#fbbf24','#a78bfa'],
            'circle-stroke-width':1,'circle-stroke-color':'#111827'}});
        map.on('click','infra-pontos',e=>{
            const f=e.features?.[0];if(!f) return;const p=f.properties,box=document.createElement('div');box.style.color='#111827';
            texto(box,'strong',p.nome);texto(box,'p',p.tipo+' · '+(p.status||'A conferir'));
            texto(box,'p','Fonte: '+p.fonte);texto(box,'p','Revisar até: '+(p.valido_ate||'Nao informado; referencia OSM nao confirma limite'));
            if(p.tipo==='PEDAGIO') texto(box,'p','Custo conhecido: '+money(p.custo_estimado_reais));
            else medidas.slice(0,4).forEach(([k,nome])=>{const lim={altura_m:'altura_max_m',largura_m:'largura_max_m',comprimento_m:'comprimento_max_m',peso_total_t:'peso_max_t'}[k];texto(box,'p',nome+' máximo: '+(p[lim]??'Não informado'));});
            new maplibregl.Popup().setLngLat(e.lngLat).setDOMContent(box).addTo(map);
        });
    });
    return {ler,preencher,frota,limpar,corredor,inspector:info=>mostrar(audit,info)};
})();
