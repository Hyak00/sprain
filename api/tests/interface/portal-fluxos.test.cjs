const{test}=require('node:test');const assert=require('node:assert/strict');const vm=require('node:vm');const fs=require('node:fs');const path=require('node:path');const{parseHTML}=require('linkedom');
const viagem={id_operacao:'NOVA_01',origem_nome:'Origem',origem_lat:-23.54,origem_lon:-46.46,destino_nome:'Destino',destino_lat:-23.55,destino_lon:-46.45,janela_inicio:'2026-10-20T08:00:00-03:00',janela_fim:'2026-10-20T12:00:00-03:00'};
const base='/api/v1/logistica/';
const resposta={
    [base+'operacoes']:[{id_operacao:'OP1',origem_nome:'Origem',destino_nome:'Destino'}],
    [base+'relatorios/sumario-executivo']:{periodo:'D-0 / D+1',kpis:{total_operacoes:1,rotas_em_risco_alagamento:0,rotas_recalculadas_com_sucesso:0,prejuizo_estimado_evitado_brl:0}},
    [base+'operacoes/OP1/explicacao']:{id_operacao:'OP1',acao_recomendada:'MANTER_ROTA',justificativa:'<img src=x onerror=alert(1)>',infraestrutura:{}},
    [base+'operacoes/OP1/decisoes']:[],
    '/api/v1/health/liveness':{status:'UP'},'/api/v1/health/readiness':{status:'READY'},
    '/api/v1/alertas/precisao':{total_eventos_analisados:0},'/api/v1/dados-publicos/fontes':{fontes:[]},'/api/v1/indicadores/qualidade':{status_geral:'ATENCAO_FONTES'}
};
const tick=()=>new Promise(r=>setImmediate(r));
async function ambiente(role='OPERATOR',handler){
    const{window}=parseHTML('<html><head></head><body><div class="top-controls"></div></body></html>');const{document}=window;const chamadas=[],downloads=[];let perfil=role;
    const criar=document.createElement.bind(document);document.createElement=tag=>{const el=criar(tag);if(tag==='dialog'){
        el.showModal=()=>{el.open=true;};el.close=()=>{if(!el.open)return;el.open=false;el.dispatchEvent(new window.Event('close'));};
    }return el;};
    Object.defineProperty(window.HTMLSelectElement.prototype,'value',{configurable:true,get(){return this.querySelector('option[selected]')?.value||this.querySelector('option')?.value||'';},set(v){this.querySelectorAll('option').forEach(o=>{if(o.value===v)o.setAttribute('selected','');else o.removeAttribute('selected');});}});
    window.PainelSessao={perfil:()=>perfil,podeEscrever:()=>['ADMIN','OPERATOR'].includes(perfil),request:async(url,options={})=>{chamadas.push({url,options});const d=handler?await handler(url,options):resposta[url];if(d instanceof Error)throw d;if(d===undefined)throw Error('Indisponível');return {json:async()=>d};}};
    const contexto=vm.createContext({window,document,console,Blob,TextEncoder,AbortController,URL:{createObjectURL:b=>{downloads.push(b);return 'blob:teste';},revokeObjectURL(){}},setTimeout:fn=>{fn();},Date});
    for(const arq of ['portal-dados.js','portal-pdf.js','portal-operacional.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../../static',arq),'utf8'),contexto);
    const app=window.PortalOperacional;app.sessao({tenant_id:'empresa',role,email:'demo@exemplo.com'});
    const botao=texto=>Array.from(document.querySelectorAll('button')).find(b=>b.textContent===texto);
    const clicar=async texto=>{const b=botao(texto);assert(b,'Botão ausente: '+texto);await b.onclick();await tick();return b;};
    return{window,document,app,chamadas,downloads,clicar,botao,encerrar:()=>{perfil=null;app.limpar();}};
}
test('central carrega relatórios, exporta PDF e não interpreta dados como HTML',async()=>{
    const a=await ambiente();a.app.abrir();await tick();await a.clicar('Carregar consulta e decisões');
    assert(a.document.body.textContent.includes('<img src=x'));assert.equal(a.document.querySelectorAll('img').length,0);
    await a.clicar('Baixar PDF da consulta e decisões');assert.equal(a.downloads[0].type,'application/pdf');assert((await a.downloads[0].text()).startsWith('%PDF-1.4'));
    assert(!a.document.body.textContent.includes('api_key'));a.encerrar();
});
test('logout limpa dados, fecha central e impede nova abertura anônima',async()=>{
    const a=await ambiente();a.app.abrir();await tick();a.encerrar();a.app.abrir();assert.equal(a.document.querySelector('dialog').open,false);assert.equal(a.document.querySelector('#portal-conteudo').textContent,'');
});
test('resposta da empresa anterior não preenche nova sessão',async()=>{
    let liberar;const atraso=new Promise(r=>liberar=r);const a=await ambiente('OPERATOR',async url=>url===base+'operacoes'?atraso:resposta[url]);
    a.app.abrir();await tick();a.app.sessao({tenant_id:'outra',role:'VIEWER'});liberar([{id_operacao:'SEGREDO_ANTIGO'}]);await tick();assert(!a.document.body.textContent.includes('SEGREDO_ANTIGO'));a.encerrar();
});
test('VIEWER valida arquivo mas não envia importação nem consulta métricas restritas',async()=>{
    const a=await ambiente('VIEWER');a.app.abrir();await tick();await a.clicar('Importar rotas');const input=a.document.querySelector('#portal-arquivo');input.files=[{size:100,text:async()=>JSON.stringify([viagem])}];await input.onchange();
    assert(a.botao('Importar operações validadas').disabled);await a.clicar('Importar operações validadas');assert(!a.chamadas.some(c=>c.options.method==='POST'));
    await a.clicar('Qualidade e serviços');assert(!a.chamadas.some(c=>c.url.includes('observabilidade')));assert(a.document.body.textContent.includes('Amostra insuficiente'));a.encerrar();
});
test('importador não envia lote inválido ou identificador já existente',async()=>{
    const a=await ambiente();a.app.abrir();await tick();await a.clicar('Importar rotas');const input=a.document.querySelector('#portal-arquivo');
    input.files=[{size:20,text:async()=>'[{}]'}];await input.onchange();assert(a.botao('Importar operações validadas').disabled);
    input.files=[{size:100,text:async()=>JSON.stringify([{...viagem,id_operacao:'OP1'}])}];await input.onchange();assert(a.document.body.textContent.includes('já cadastrados'));assert(!a.chamadas.some(c=>c.options.method==='POST'));a.encerrar();
});
test('lote parcial informa resultados e exporta somente falhas, sem reenvio automático',async()=>{
    const a=await ambiente('OPERATOR',async(url,options)=>options.method==='POST'?{total_recebido:2,sucessos:1,falhas:1,detalhe_falhas:[{id_operacao:'NOVA_02',erro:'Rota indisponível'}]}:resposta[url]);
    a.app.abrir();await tick();await a.clicar('Importar rotas');const input=a.document.querySelector('#portal-arquivo');input.files=[{size:300,text:async()=>JSON.stringify([viagem,{...viagem,id_operacao:'NOVA_02'}])}];await input.onchange();
    await a.clicar('Importar operações validadas');assert(a.document.body.textContent.includes('1 operação(ões) gravada(s); 1 falha(s)'));await a.clicar('Baixar somente operações com falha');
    const falhas=JSON.parse(await a.downloads[0].text());assert.deepEqual(falhas.map(o=>o.id_operacao),['NOVA_02']);assert.equal(a.chamadas.filter(c=>c.options.method==='POST').length,1);a.encerrar();
});
test('resultado incerto não confirma sucesso nem reenvia lote',async()=>{
    const a=await ambiente('OPERATOR',async(url,options)=>options.method==='POST'?new Error('Rede'):resposta[url]);a.app.abrir();await tick();await a.clicar('Importar rotas');
    const input=a.document.querySelector('#portal-arquivo');input.files=[{size:100,text:async()=>JSON.stringify([viagem])}];await input.onchange();await a.clicar('Importar operações validadas');await a.clicar('Importar operações validadas');
    assert(a.document.body.textContent.includes('Algumas operações podem ter sido gravadas'));assert.equal(a.chamadas.filter(c=>c.options.method==='POST').length,1);a.encerrar();
});
test('qualidade parcial distingue serviço indisponível de ausência de risco',async()=>{
    const a=await ambiente('OPERATOR',async url=>url.includes('readiness')?new Error('Conexão'):resposta[url]);a.app.abrir();await tick();await a.clicar('Qualidade e serviços');assert(a.document.body.textContent.includes('Consulta parcial'));assert(a.document.body.textContent.includes('Indisponível'));a.encerrar();
});
