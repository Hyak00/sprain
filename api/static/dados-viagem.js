/* Consultas locais apenas ao abrir uma viagem. Nao altera o modelo de risco. */
window.DadosViagem = (() => {
    'use strict';
    let sequencia=0, controle;
    const vazio=()=>({type:'FeatureCollection',features:[]});
    const box=document.createElement('details');box.className='infra-complemento';
    document.getElementById('infra-auditoria').after(box);
    function texto(parent,tag,value){const e=document.createElement(tag);e.textContent=value;parent.appendChild(e);return e;}
    function limpar(){sequencia++;controle?.abort();box.replaceChildren();map.getSource('dados-viagem')?.setData(vazio());}
    function fonte(parent,url){try{const u=new URL(url);if(u.protocol!=='https:')return;const a=texto(parent,'a',' Fonte');a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';}catch{}}
    function linhas(rota){
        if(!rota)return [];
        if(rota.type==='FeatureCollection')return rota.features.flatMap(f=>linhas(f.geometry));
        if(rota.type==='LineString')return [rota.coordinates];
        return rota.type==='MultiLineString'?rota.coordinates:[];
    }
    async function exibir(geometrias,parent=box,incluirAproximados=false){
        limpar();const atual=sequencia;controle=new AbortController();
        parent.replaceChildren();texto(parent,'summary','Postos, historico e atualizacao dos dados');
        const label=texto(parent,'label','Incluir localizacoes aproximadas da ANP (conferir antes de usar) ');const check=document.createElement('input');check.type='checkbox';check.checked=incluirAproximados;label.appendChild(check);check.onchange=()=>exibir(geometrias,parent,check.checked);
        const aviso=texto(parent,'p','Consultando dados locais da rota...');
        const coordenadas=geometrias.flatMap(linhas);
        if(!coordenadas.length){aviso.textContent='Sem geometria disponivel para consultar.';return;}
        const headers={'Content-Type':'application/json','X-API-Key':window.API_KEY};
        async function consultar(url,body){const r=await window.PainelSessao.request(url,{headers,signal:controle.signal,...(body?{method:'POST',body:JSON.stringify(body)}:{})});if(!r.ok)throw new Error('Consulta indisponivel ('+r.status+').');return r.json();}
        try{
            const resultados=await Promise.allSettled([
                consultar('/api/v1/dados-publicos/consultar-rota',{rota:{type:'MultiLineString',coordinates:coordenadas},incluir_postos_nao_verificados:incluirAproximados}),
                consultar('/api/v1/dados-publicos/roubo-carga/por-regiao'),
                consultar('/api/v1/dados-publicos/fontes'),consultar('/api/v1/infraestrutura/pendencias')]);
            if(atual!==sequencia)return;
            aviso.textContent='Referencias proximas das rotas exibidas. Proximidade nao confirma entrada ou acesso para caminhao.';
            const [rota,roubo,fontes,pendencias]=resultados.map(r=>r.status==='fulfilled'?r.value:null);
            const features=[];
            if(rota){
                texto(parent,'p',`${rota.tombamentos.length} registro(s) historico(s) de tombamento com caminhao envolvido a ate 500 m. Nao identifica necessariamente qual veiculo tombou nem estima probabilidade.`);
                if(rota.truncado)texto(parent,'p','Resultado limitado aos primeiros 200 registros de cada tipo.');
                rota.tombamentos.forEach(a=>features.push({type:'Feature',geometry:{type:'Point',coordinates:[a.longitude,a.latitude]},properties:{tipo:'Historico de tombamento',nome:a.rodovia,data:String(a.data_ocorrencia),fonte:a.url_fonte}}));
                texto(parent,'p',`${rota.postos.length} posto(s) com preco pesquisado; localizacao indicada abaixo a ate 3 km; nao ha garantia de preco atual.`);
                rota.postos.forEach(p=>{
                    const preco=Number(p.preco_litro).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
                    const linha=texto(parent,'p',`${p.nome} · DIESEL S10 ${preco}/L · coleta ${p.data_coleta} · ${p.preco_recente?'referencia recente':'preco antigo, atualizar antes de usar'} · ${p.distancia_rota_m} m da rota · ${p.localizacao_confirmada?'localizacao conferida':'LOCALIZACAO APROXIMADA, NAO CONFERIDA'}.`);fonte(linha,p.url_fonte);
                    if(p.preco_recente && p.localizacao_confirmada){
                        const btn=texto(linha,'button',parent===box?'Usar no formulario de novo despacho':'Usar no formulario do corredor');btn.type='button';btn.className='btn-top';
                        btn.onclick=()=>{const id=parent===box?'infra-desp':'infra-corredor';
                            document.getElementById(id+'-preco_combustivel_litro').value=p.preco_litro;
                            document.getElementById(id+'-combustivel_data_coleta').value=p.data_coleta;
                            document.getElementById(id).open=true;
                            texto(linha,'span',' Preco preenchido no formulario; informe consumo e custo sem combustivel e salve/recalcule a viagem.');};
                    }
                    features.push({type:'Feature',geometry:{type:'Point',coordinates:[p.longitude,p.latitude]},properties:{tipo:p.localizacao_confirmada?'Posto · DIESEL S10':'Posto aproximado · conferir',nome:p.nome,data:String(p.data_coleta),preco:preco+'/L',fonte:p.url_fonte}});
                });
            }else texto(parent,'p','Dados proximos da rota indisponiveis. Isso nao significa ausencia de risco ou de postos.');
            if(roubo){texto(parent,'p',roubo.interpretacao);roubo.regioes.forEach(r=>{const p=texto(parent,'p',`${r.area}: ${r.ocorrencias} ocorrencia(s) · ${r.periodo_inicio} a ${r.periodo_fim}`);fonte(p,r.url_fonte);});}
            if(fontes){if(!fontes.fontes.length)texto(parent,'p','Fontes publicas ainda nao importadas.');fontes.fontes.forEach(f=>{const p=texto(parent,'p',`${f.nome} · ultima importacao ${f.ultimo_sucesso_em} · ${f.registros_importados} registro(s).`);fonte(p,f.url);});}
            if(pendencias)texto(parent,'p',`Cadastro da empresa: ${pendencias.pedagios_sem_tarifa_vigente} pedagio(s) sem tarifa vigente; ${pendencias.pontes_cadastradas} ponte(s) cadastrada(s), ${pendencias.pontes_sem_limites_completos_vigentes} a conferir; ${pendencias.caminhoes_sem_medidas} caminhao(oes) sem medidas. ${pendencias.estruturas_referencia||0} estruturas OSM identificadas na malha. Cobertura parcial; referencia nao comprova capacidade de carga.`);
            if(resultados.some(r=>r.status==='rejected'))texto(parent,'p','Uma das consultas complementares falhou; os resultados disponiveis foram mantidos.');
            map.getSource('dados-viagem')?.setData({type:'FeatureCollection',features});
        }catch(e){if(atual===sequencia&&e.name!=='AbortError')aviso.textContent='Nao foi possivel consultar os dados complementares.';}
    }
    map.on('load',()=>{
        map.addSource('dados-viagem',{type:'geojson',data:vazio()});
        map.addLayer({id:'dados-viagem',type:'circle',source:'dados-viagem',paint:{'circle-radius':5,'circle-color':['match',['get','tipo'],'Posto · DIESEL S10','#22c55e','#fb923c'],'circle-stroke-color':'#111827','circle-stroke-width':1}});
        map.on('click','dados-viagem',e=>{const p=e.features?.[0]?.properties;if(!p)return;const div=document.createElement('div');div.style.color='#111827';texto(div,'strong',p.tipo+' · '+p.nome);texto(div,'p',p.data+(p.preco?' · '+p.preco:''));texto(div,'p','Referencia historica. Conferir acesso e dados antes da viagem.');fonte(div,p.fonte);new maplibregl.Popup().setLngLat(e.lngLat).setDOMContent(div).addTo(map);});
    });
    return {exibir,limpar};
})();
