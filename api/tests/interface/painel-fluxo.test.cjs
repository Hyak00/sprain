const{test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');const{parseHTML}=require('linkedom');const{webcrypto}=require('node:crypto');
const op={id_operacao:'OP1',contexto_consulta:{natureza:'SIMULACAO',selo_premissas:'a'.repeat(64),premissas_editaveis:{custo_por_km:8},precipitacao_mm:35},coordenadas:{origem_nome:'Origem',origem_lat:-23.5,origem_lon:-46.4,destino_nome:'Destino',destino_lat:-23.6,destino_lon:-46.5},infraestrutura:{}};
const tick=()=>new Promise(r=>setImmediate(r));
async function ambiente(role='OPERATOR',handler=async()=>({}),opcoes={}){
    const{window}=parseHTML('<html><body><div class="top-controls"></div><div class="map-legend"></div><div id="inspector"><div id="infra-auditoria"></div></div><dialog id="portal-operacional"></dialog></body></html>');const{document}=window;const chamadas=[],secoes={},sources={},selecoes=[];
    window.HTMLElement.prototype.reportValidity=()=>true;
    Object.defineProperty(window.HTMLSelectElement.prototype,'value',{configurable:true,get(){return this.querySelector('option[selected]')?.value||this.querySelector('option')?.value||'';},set(v){this.querySelectorAll('option').forEach(o=>o.toggleAttribute('selected',o.value===v));}});
    window.PainelSessao={podeEscrever:()=>role!=='VIEWER',request:async(url,options={})=>{chamadas.push({url,options});return{json:async()=>handler(url,options)};}};
    window.PortalOperacional={registrarSecao:(id,label,fn)=>secoes[id]=fn,navegar:id=>id};window.selecionarOperacao=async id=>selecoes.push(id);
    const map={loaded:()=>true,getSource:id=>sources[id],addSource:(id,d)=>sources[id]={data:d.data,setData(v){this.data=v;}},addLayer(){},on(){}};
    const contexto=vm.createContext({window,document,console,crypto:webcrypto,map,TextEncoder,Date:opcoes.Date||Date,AbortController,setTimeout:opcoes.setTimeout||setTimeout,clearTimeout:opcoes.clearTimeout||clearTimeout});
    for(const arq of ['portal-dados.js','painel-fluxo.js','painel-corredores.js','painel-eventos.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../../static',arq),'utf8'),contexto);
    const botao=texto=>Array.from(document.querySelectorAll('button')).find(b=>b.textContent===texto),clicar=async texto=>{assert(botao(texto),texto);await botao(texto).onclick();await tick();};
    const ctx={atual:()=>true,obter:async url=>{chamadas.push({url});return handler(url,{});}};
    return{window,document,secoes,chamadas,sources,selecoes,clicar,botao,ctx};
}
test('premissas editaveis enviam ao servidor, preservam chuva zero e atualizam a operacao',async()=>{
    const a=await ambiente('OPERATOR',async url=>url.endsWith('/eventos')?{items:[],mapa:{type:'FeatureCollection',features:[]}}:{sucesso:true});a.window.FluxoPainel.exibir(op,{registrado_em:'2026-10-16T12:00:00Z'});
    a.document.querySelector('input[name="custo_por_km"]').value='10';a.document.querySelector('input[name="precipitacao_mm"]').value='0';await a.clicar('Salvar premissas e recalcular');
    const envio=a.chamadas.find(c=>c.options?.method==='PUT');assert(envio);const body=JSON.parse(envio.options.body);assert.equal(body.custos_operacionais.custo_por_km,10);assert.equal(body.precipitacao_mm,0);assert.equal(a.selecoes[0],'OP1');
});
test('VIEWER nao altera premissas nem envia gravacao mesmo se o handler for chamado',async()=>{
    const a=await ambiente('VIEWER',async()=>({items:[],mapa:{features:[]}}));a.window.FluxoPainel.exibir(op,{});assert(a.botao('Salvar premissas e recalcular').disabled);await a.clicar('Salvar premissas e recalcular');assert(!a.chamadas.some(c=>c.options?.method==='PUT'));a.window.FluxoPainel.limpar();assert.equal(a.document.querySelector('.mvp-complemento').textContent,'');
});
test('corredor usa coordenadas confirmadas da selecao e salva antes de listar',async()=>{
    let rows=[];const a=await ambiente('OPERATOR',async(url,o)=>{if(url.endsWith('/veiculos'))return[];if(o.method==='POST'){const body=JSON.parse(o.body);rows=[{id:'c1',dados:body,versao:1,recorrencias:[]}];return rows[0];}if(url.includes('/corredores'))return{items:rows,proximo_offset:null};return{items:[],mapa:{features:[]}};});
    a.window.FluxoPainel.exibir(op,{});const p=a.document.createElement('section');a.document.body.appendChild(p);await a.secoes.corredores(p,a.ctx);await a.clicar('Novo corredor');await a.clicar('Usar origem/destino da operação selecionada');a.document.querySelector('input[name="nome"]').value='Meu corredor';await a.clicar('Salvar corredor');
    const post=a.chamadas.find(c=>c.options?.method==='POST');assert(post);const body=JSON.parse(post.options.body);assert.equal(body.origem_lat,-23.5);assert.equal(body.nome,'Meu corredor');assert(a.document.body.textContent.includes('Editar Meu corredor'));
});
test('historico abre fotografia persistida em leitura e nunca a grava como decisao atual',async()=>{
    const a=await ambiente('VIEWER',async url=>url.endsWith('/consultas/c1')?{id_operacao:'OP1',criado_em:'2026-10-16T12:00:00Z',snapshot:{metricas:{custo_desvio_brl:20},justificativa:'Fotografia antiga'}}:{items:[{id:'c1',id_operacao:'OP1',perfil:'VIEWER',criado_em:'2026-10-16T12:00:00Z'}],proximo_offset:null});
    const p=a.document.createElement('section');a.document.body.appendChild(p);await a.secoes.consultas(p,a.ctx);await a.clicar('Abrir fotografia OP1');assert(a.document.body.textContent.includes('Fotografia antiga'));assert(!a.chamadas.some(c=>c.options?.method==='POST'));
});
test('eventos usam cache curto e falha limpa a camada anterior',async()=>{
    let erro=false;const a=await ambiente('OPERATOR',async()=>{if(erro)throw Error('Offline');return{items:[],mapa:{type:'FeatureCollection',features:[{type:'Feature',geometry:{type:'Point',coordinates:[-46,-23]},properties:{natureza:'PREVISAO'}}]}};});
    await a.window.PainelEventos.consultar();await a.window.PainelEventos.consultar();assert.equal(a.chamadas.length,1);assert.equal(a.sources['mvp-eventos'].data.features.length,1);erro=true;await assert.rejects(a.window.PainelEventos.consultar(true));assert.equal(a.sources['mvp-eventos'].data.features.length,0);
});
test('resposta de eventos pendente nao preenche mapa depois de sair',async()=>{
    let resolver;const espera=new Promise(r=>resolver=r);const a=await ambiente('OPERATOR',()=>espera);const tarefa=a.window.PainelEventos.consultar();a.window.PainelEventos.limpar();resolver({items:[],mapa:{features:[{geometry:{type:'Point',coordinates:[0,0]}}]}});await assert.rejects(tarefa);assert.equal(a.sources['mvp-eventos'].data.features.length,0);
});
test('formatacao nao transforma ausencias em zero e escapa texto dinamico',()=>{
    const{numero,escapar}=require('../../static/painel-apresentacao.js');assert.equal(numero(null),'Sem dado');assert.equal(numero(0,2),'0.00');assert.equal(numero(NaN),'Sem dado');assert.equal(escapar('<img "x">'), '&lt;img &quot;x&quot;&gt;');
});

test('fotografia antiga atrasada nao substitui a ultima selecionada',async()=>{
    let liberar;const antiga=new Promise(r=>liberar=r);
    const a=await ambiente('VIEWER',url=>url.endsWith('/consultas/c1')?antiga:url.endsWith('/consultas/c2')?{id_operacao:'OP2',snapshot:{justificativa:'Fotografia atual'}}:{items:[{id:'c1',id_operacao:'OP1'},{id:'c2',id_operacao:'OP2'}],proximo_offset:null});
    const p=a.document.createElement('section');a.document.body.appendChild(p);await a.secoes.consultas(p,a.ctx);
    const pendente=a.botao('Abrir fotografia OP1').onclick();await a.clicar('Abrir fotografia OP2');liberar({id_operacao:'OP1',snapshot:{justificativa:'Resposta antiga'}});await pendente;
    assert(a.document.body.textContent.includes('Fotografia atual'));assert(!a.document.body.textContent.includes('Resposta antiga'));
});

test('falha da fotografia substitui carregamento por mensagem recuperavel',async()=>{
    const a=await ambiente('VIEWER',url=>{if(url.endsWith('/consultas/c1'))throw Error('Fotografia indisponível');return{items:[{id:'c1',id_operacao:'OP1'}],proximo_offset:null};});
    const p=a.document.createElement('section');a.document.body.appendChild(p);await a.secoes.consultas(p,a.ctx);await a.clicar('Abrir fotografia OP1');
    assert(a.document.body.textContent.includes('Fotografia indisponível'));assert(!a.document.body.textContent.includes('Carregando fotografia histórica'));
});

test('mapa retira eventos vencidos mesmo ao reutilizar cache e preserva relato sem validade',async()=>{
    let agora=Date.now();class Relogio extends Date{static now(){return agora;}}
    const feature=expiracao=>({type:'Feature',geometry:{type:'Point',coordinates:[-46,-23]},properties:{expiracao}});
    const a=await ambiente('OPERATOR',async()=>({items:[],mapa:{type:'FeatureCollection',features:[feature(new Date(agora+1000).toISOString()),feature(null)]}}),{Date:Relogio});
    await a.window.PainelEventos.consultar();assert.equal(a.sources['mvp-eventos'].data.features.length,2);
    agora+=2000;await a.window.PainelEventos.consultar();assert.equal(a.chamadas.length,1);assert.equal(a.sources['mvp-eventos'].data.features.length,1);assert.match(a.document.body.textContent,/expiradas foram retiradas/);a.window.PainelEventos.limpar();
});

test('relato salvo nao e reenviado quando a atualizacao do mapa falha',async()=>{
    let offline=true;const a=await ambiente('OPERATOR',async(url,o)=>{if(o.method==='POST')return{id:'relato-1'};if(offline)throw Error('offline');return{items:[],mapa:{type:'FeatureCollection',features:[]}};});
    const p=a.document.createElement('section');a.document.body.appendChild(p);await a.secoes.relatos(p,a.ctx);
    a.document.querySelector('textarea').value='Relato de teste';a.document.querySelector('input[name="ocorrido_em"]').value='2026-01-01T12:00';a.document.querySelector('input[name="latitude"]').value='-23';a.document.querySelector('input[name="longitude"]').value='-46';
    await a.clicar('Registrar ocorrência não detectada');assert(a.document.body.textContent.includes('já registrado'));assert(a.botao('Registrar ocorrência não detectada').disabled);
    await a.clicar('Registrar ocorrência não detectada');assert.equal(a.chamadas.filter(c=>c.options?.method==='POST').length,1);
    offline=false;await a.clicar('Tentar atualizar o mapa');assert(a.document.body.textContent.includes('mapa atualizado'));assert.equal(a.chamadas.filter(c=>c.options?.method==='POST').length,1);
});

test('validade agenda retirada automatica sem nova requisicao',async()=>{
    let agora=Date.now(),agendado;class Relogio extends Date{static now(){return agora;}}
    const a=await ambiente('OPERATOR',async()=>({items:[],mapa:{type:'FeatureCollection',features:[{type:'Feature',geometry:{type:'Point',coordinates:[-46,-23]},properties:{expiracao:new Date(agora+1000).toISOString()}}]}}),{Date:Relogio,setTimeout:fn=>{agendado=fn;return 1;},clearTimeout:()=>{}});
    await a.window.PainelEventos.consultar();assert.equal(typeof agendado,'function');agora+=1001;agendado();assert.equal(a.sources['mvp-eventos'].data.features.length,0);assert.equal(a.chamadas.length,1);a.window.PainelEventos.limpar();
});

test('atualizacao explicita aguarda consulta anterior e busca dados novos',async()=>{
    let liberar,n=0;const antiga=new Promise(r=>liberar=r);
    const a=await ambiente('OPERATOR',async()=>++n===1?antiga:{items:[{id_evento:'novo'}],mapa:{type:'FeatureCollection',features:[]}});
    const inicial=a.window.PainelEventos.consultar();const forcar=a.window.PainelEventos.consultar(true);liberar({items:[],mapa:{type:'FeatureCollection',features:[]}});await inicial;
    assert.equal((await forcar).items[0].id_evento,'novo');assert.equal(a.chamadas.length,2);a.window.PainelEventos.limpar();
});

test('reenvio de relato apos resposta incerta reutiliza identificador',async()=>{
    let tentativas=0;const a=await ambiente('OPERATOR',async(url,o)=>{if(o.method==='POST'){if(++tentativas===1)throw Error('Conexão interrompida');return{id:'relato-2'};}return{items:[],mapa:{type:'FeatureCollection',features:[]}};});
    const p=a.document.createElement('section');a.document.body.appendChild(p);await a.secoes.relatos(p,a.ctx);
    a.document.querySelector('textarea').value='Relato de teste';a.document.querySelector('input[name="ocorrido_em"]').value='2026-01-01T12:00';a.document.querySelector('input[name="latitude"]').value='-23';a.document.querySelector('input[name="longitude"]').value='-46';
    await a.clicar('Registrar ocorrência não detectada');assert(a.document.body.textContent.includes('envio não foi confirmado'));assert.equal(a.botao('Registrar ocorrência não detectada').disabled,false);
    await a.clicar('Registrar ocorrência não detectada');const envios=a.chamadas.filter(c=>c.options?.method==='POST').map(c=>JSON.parse(c.options.body));assert.equal(envios.length,2);assert.equal(envios[0].chave_idempotencia,envios[1].chave_idempotencia);assert(a.document.body.textContent.includes('exibido no mapa'));
});
