const{test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');const{parseHTML}=require('linkedom');const{webcrypto}=require('node:crypto');
const op={id_operacao:'OP1',contexto_consulta:{natureza:'SIMULACAO',selo_premissas:'a'.repeat(64),premissas_editaveis:{custo_por_km:8},precipitacao_mm:35},coordenadas:{origem_nome:'Origem',origem_lat:-23.5,origem_lon:-46.4,destino_nome:'Destino',destino_lat:-23.6,destino_lon:-46.5},infraestrutura:{}};
const tick=()=>new Promise(r=>setImmediate(r));
async function ambiente(role='OPERATOR',handler=async()=>({})){
    const{window}=parseHTML('<html><body><div class="top-controls"></div><div class="map-legend"></div><div id="inspector"><div id="infra-auditoria"></div></div><dialog id="portal-operacional"></dialog></body></html>');const{document}=window;const chamadas=[],secoes={},sources={},selecoes=[];
    window.HTMLElement.prototype.reportValidity=()=>true;
    Object.defineProperty(window.HTMLSelectElement.prototype,'value',{configurable:true,get(){return this.querySelector('option[selected]')?.value||this.querySelector('option')?.value||'';},set(v){this.querySelectorAll('option').forEach(o=>o.toggleAttribute('selected',o.value===v));}});
    window.PainelSessao={podeEscrever:()=>role!=='VIEWER',request:async(url,options={})=>{chamadas.push({url,options});return{json:async()=>handler(url,options)};}};
    window.PortalOperacional={registrarSecao:(id,label,fn)=>secoes[id]=fn,navegar:id=>id};window.selecionarOperacao=async id=>selecoes.push(id);
    const map={loaded:()=>true,getSource:id=>sources[id],addSource:(id,d)=>sources[id]={data:d.data,setData(v){this.data=v;}},addLayer(){},on(){}};
    const contexto=vm.createContext({window,document,console,crypto:webcrypto,map,TextEncoder,Date,AbortController});
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
