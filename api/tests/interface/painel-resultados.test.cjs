const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const {parseHTML}=require('linkedom');
const registro={id:'registro-atual',finalizada_em:'2026-10-18T12:00:00Z',registrada_em:'2026-10-18T13:00:00Z',rota_executada:'DESVIO',duracao_real_min:null,distancia_real_km:20,custo_real_brl:0,fonte:'RELATO_OPERADOR',observacoes:'<img src=x onerror=alert(1)>',substitui_id:null,usuario_id:'usuario-registrado'};
async function ambiente(handler,role='OPERATOR'){
 const {window}=parseHTML('<html><body><div id="infra-auditoria"></div><main></main></body></html>');const {document}=window;let perfil=role;const chamadas=[];
 window.HTMLElement.prototype.reportValidity=()=>true;
 Object.defineProperty(window.HTMLSelectElement.prototype,'value',{configurable:true,get(){return this.querySelector('option[selected]')?.value||this.querySelector('option')?.value||'';},set(v){this.querySelectorAll('option').forEach(o=>o.toggleAttribute('selected',o.value===v));}});
 window.PortalOperacional={registrarSecao(){}};
 window.PainelSessao={perfil:()=>perfil,podeEscrever:()=>['ADMIN','OPERATOR'].includes(perfil),request:async(url,o={})=>{chamadas.push({url,o});const d=await handler(url,o);return{json:async()=>d};}};
 const contexto=vm.createContext({window,document,Date,AbortController,console});
 for(const arq of ['portal-dados.js','painel-fluxo.js','painel-resultados.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../../static',arq),'utf8'),contexto);
 const app=window.ResultadosViagem,p=document.querySelector('main'),botao=s=>Array.from(p.querySelectorAll('button')).find(b=>b.textContent===s),clicar=async s=>{assert(botao(s),s);await botao(s).onclick();};
 return{app,p,document,chamadas,botao,clicar,campo:(k,v)=>p.querySelector('[name="'+k+'"]').value=v,sair:()=>{perfil=null;app.limpar();}};
}
const vazio={items:[],proximo_offset:null};
test('resultado: desconhecido fica nulo e custo zero é enviado; grava uma vez e não cria economia',async()=>{
 let salvo=false;const a=await ambiente((u,o)=>{if(o.method==='POST'){salvo=true;return registro;}return salvo?{items:[registro],proximo_offset:null}:vazio;});await a.app.exibir(a.p,'OP/1');
 a.campo('finalizada_em','2026-10-18T09:00');a.campo('custo_real_brl','0');await a.clicar('Salvar resultado da viagem');
 const posts=a.chamadas.filter(c=>c.o.method==='POST');assert.equal(posts.length,1);const body=JSON.parse(posts[0].o.body);assert.equal(body.custo_real_brl,'0');assert.equal(body.distancia_real_km,null);assert.equal(body.substitui_id,null);assert(body.finalizada_em.endsWith('Z'));assert(posts[0].url.includes('OP%2F1'));
 assert(a.p.textContent.includes('Resultado salvo no servidor'));assert(a.p.textContent.includes('0,00'));assert(a.p.textContent.includes('<img'));assert.equal(a.p.querySelectorAll('img').length,0);assert(!a.botao('Salvar resultado da viagem'));
});
test('resultado: correção preserva vínculo e ID atual; conflito bloqueia reenvio até nova consulta',async()=>{
 const a=await ambiente((u,o)=>{if(o.method==='POST')throw Object.assign(Error('Conflito'),{status:409});return{items:[registro],proximo_offset:null};});await a.app.exibir(a.p,'OP1');await a.clicar('Corrigir este resultado');a.campo('custo_real_brl','42.50');await a.clicar('Salvar correção do resultado');
 const post=a.chamadas.find(c=>c.o.method==='POST');assert.equal(JSON.parse(post.o.body).substitui_id,registro.id);assert(a.p.textContent.includes('O resultado mudou'));assert(a.botao('Salvar correção do resultado').disabled);await a.clicar('Salvar correção do resultado');assert.equal(a.chamadas.filter(c=>c.o.method==='POST').length,1);
 await a.clicar('Atualizar resultados da viagem');assert(a.botao('Corrigir este resultado'));
});
test('resultado: VIEWER lê histórico e paginação, sem formulário ou envio',async()=>{
 const a=await ambiente(u=>u.includes('offset=20')?vazio:{items:[registro],proximo_offset:20},'VIEWER');await a.app.exibir(a.p,'OP1');assert.equal(a.p.querySelectorAll('input').length,0);assert(!a.botao('Corrigir este resultado'));await a.clicar('Resultados anteriores');assert(a.p.textContent.includes('Nenhum registro nesta página'));assert(a.botao('Resultados mais recentes'));assert(!a.chamadas.some(c=>c.o.method==='POST'));
});
test('resultado: exige medida e documento exige referência, sem enviar formulário inválido',async()=>{
 const a=await ambiente(()=>vazio);await a.app.exibir(a.p,'OP1');a.campo('finalizada_em','2026-10-18T09:00');await a.clicar('Salvar resultado da viagem');assert(a.p.textContent.includes('ao menos duração'));
 a.campo('custo_real_brl','1');a.campo('fonte','DOCUMENTO');await a.clicar('Salvar resultado da viagem');assert(a.p.textContent.includes('referência do documento'));assert(!a.chamadas.some(c=>c.o.method==='POST'));
});
test('resultado: falha de leitura não libera formulário',async()=>{
 const a=await ambiente(()=>{throw Error('offline');});await a.app.exibir(a.p,'OP1');assert(a.p.textContent.includes('Histórico indisponível'));assert.equal(a.p.querySelectorAll('input').length,0);
});
test('resultado: logout descarta resposta atrasada sem dados da empresa anterior',async()=>{
 let liberar;const a=await ambiente(()=>new Promise(r=>liberar=r));const pendente=a.app.exibir(a.p,'OP1');a.sair();liberar({items:[registro],proximo_offset:null});await pendente;assert.equal(a.p.textContent,'');
});
test('resultado: confirmação simultânea envia uma vez, erro incerto exige nova leitura',async()=>{
 let liberar;const a=await ambiente((u,o)=>o.method==='POST'?new Promise((r,rejeitar)=>liberar=()=>rejeitar(Error('timeout'))):vazio);await a.app.exibir(a.p,'OP1');a.campo('finalizada_em','2026-10-18T09:00');a.campo('custo_real_brl','3');
 const b=a.botao('Salvar resultado da viagem'),t=b.onclick();await b.onclick();assert.equal(a.chamadas.filter(c=>c.o.method==='POST').length,1);liberar();await t;assert(b.disabled);assert(a.p.textContent.includes('Atualize o histórico antes de reenviar'));
});

test('resultado: seleção nova descarta histórico pendente da viagem anterior',async()=>{
 let liberar;const a=await ambiente(u=>u.includes('/OP1/')?new Promise(r=>liberar=r):vazio);const antiga=a.app.exibir(a.p,'OP1');await a.app.exibir(a.p,'OP2');liberar({items:[registro],proximo_offset:null});await antiga;assert(!a.p.textContent.includes('usuario-registrado'));assert(a.botao('Salvar resultado da viagem'));
});

test('resultado: validação recusada preserva campos e permite corrigir antes de reenviar',async()=>{
 const a=await ambiente((u,o)=>{if(o.method==='POST')throw Object.assign(Error('Validação'),{status:422});return vazio;});await a.app.exibir(a.p,'OP1');a.campo('finalizada_em','2026-10-18T09:00');a.campo('custo_real_brl','45');a.campo('id_decisao','99');await a.clicar('Salvar resultado da viagem');assert(!a.botao('Salvar resultado da viagem').disabled);assert.equal(a.p.querySelector('[name=custo_real_brl]').value,'45');assert(a.p.textContent.includes('campos foram preservados'));
});
