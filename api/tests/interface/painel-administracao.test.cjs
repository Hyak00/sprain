const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const {parseHTML}=require('linkedom');
async function ambiente(role='ADMIN',handler=async()=>({}),individual=true){
    const {window}=parseHTML('<html><body><div class="top-controls"></div><div id="infra-auditoria"></div><div><input id="login-senha"></div></body></html>');
    const {document}=window,secoes={},chamadas=[];
    window.HTMLElement.prototype.reportValidity=()=>true;
    window.HTMLDialogElement=window.HTMLElement;
    window.HTMLElement.prototype.showModal=function(){this.open=true;};
    window.HTMLElement.prototype.close=function(){this.open=false;this.dispatchEvent(new window.Event('close'));};
    Object.defineProperty(window.HTMLSelectElement.prototype,'value',{configurable:true,get(){return this.querySelector('option[selected]')?.value||this.querySelector('option')?.value||'';},set(v){this.querySelectorAll('option').forEach(o=>o.toggleAttribute('selected',o.value===v));}});
    let atual=true;
    window.PainelSessao={podeEscrever:()=>role!=='VIEWER',identidade:()=>({role,usuario_id:individual?'eu':null,tipo_acesso:individual?'INDIVIDUAL':'DEMONSTRACAO'}),request:async(url,options={})=>{chamadas.push({url,options});const d=await handler(url,options);return{json:async()=>d,blob:async()=>new Blob(['teste'])};}};
    window.PortalOperacional={registrarSecao:(id,label,fn)=>secoes[id]=fn};
    const contexto=vm.createContext({window,document,console,Blob,URL,AbortController,setTimeout,clearTimeout});
    for(const arq of ['portal-dados.js','painel-fluxo.js','painel-administracao.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../../static',arq),'utf8'),contexto);
    const ctx={atual:()=>atual,obter:async url=>{chamadas.push({url});return handler(url,{});},recarregar:async()=>chamadas.push({url:'recarregar'})};
    const p=document.createElement('section');document.body.appendChild(p);
    const botao=s=>Array.from(document.querySelectorAll('button')).find(b=>b.textContent===s);
    const clicar=async s=>{assert(botao(s),s);await botao(s).onclick();};
    return{window,document,secoes,chamadas,ctx,p,botao,clicar,encerrar:()=>{atual=false;}};
}
const listar=async url=>url.includes('/usuarios?')?{usuarios:[{id:'eu',email:'admin@example.test',papel:'ADMIN',ativo:true},{id:'outro',email:'operador@example.test',papel:'OPERATOR',ativo:true}],total:2}:url.includes('/recuperacao?')?{items:[],proximo_offset:null}:{custos:{custo_por_km:0},versao:2,referencias_sistema:{custo_por_km:4.5}};

test('gestao exige ADMIN individual e nao consulta dados administrativos para outros perfis',async()=>{
    for(const [role,individual]of [['VIEWER',true],['OPERATOR',true],['ADMIN',false]]){
        const a=await ambiente(role,listar,individual);await a.secoes.administracao(a.p,a.ctx);assert.equal(a.chamadas.length,0);assert(a.p.textContent.includes('ADMIN com conta individual'));
    }
});
test('admin cria usuario com papel, limpa senha e impede segundo envio do formulario salvo',async()=>{
    const a=await ambiente('ADMIN',listar);await a.secoes.administracao(a.p,a.ctx);
    a.document.querySelector('input[name=email]').value='novo@example.test';a.document.querySelector('input[name=senha]').value='senha de teste suficientemente longa';
    await a.clicar('Criar usuário');const r=a.chamadas.find(c=>c.options?.method==='POST');assert.equal(JSON.parse(r.options.body).papel,'VIEWER');assert(!a.botao('Criar usuário'));assert(!a.document.querySelector('input[name=senha]'));
});
test('papel e desativacao exigem confirmacao e nao oferecem alteracao da propria conta',async()=>{
    const a=await ambiente('ADMIN',listar);await a.secoes.administracao(a.p,a.ctx);assert(!a.botao('Desativar admin@example.test'));
    await a.clicar('Salvar papel de operador@example.test');assert(!a.chamadas.some(c=>c.options?.method==='PATCH'));
    const article=a.botao('Salvar papel de operador@example.test').parentElement;article.querySelector('input[type=checkbox]').checked=true;
    await a.clicar('Salvar papel de operador@example.test');assert(a.chamadas.some(c=>c.options?.method==='PATCH'));
});
test('premissas preservam zero, versao e usam endpoint da empresa',async()=>{
    const a=await ambiente('ADMIN',listar);await a.secoes.financeiro(a.p,a.ctx);await a.clicar('Salvar padrões financeiros');
    const r=a.chamadas.find(c=>c.options?.method==='PUT');assert.equal(JSON.parse(r.options.body).custos.custo_por_km,0);assert.equal(JSON.parse(r.options.body).versao,2);
});
test('VIEWER consulta premissas sem gravar mesmo se handler for invocado',async()=>{
    const a=await ambiente('VIEWER',listar);await a.secoes.financeiro(a.p,a.ctx);assert(a.botao('Salvar padrões financeiros').disabled);await a.clicar('Salvar padrões financeiros');assert(!a.chamadas.some(c=>c.options?.method==='PUT'));
});
test('recuperacao usa requisicao publica e remove segredos ao fechar',async()=>{
    const a=await ambiente('VIEWER',async()=>({mensagem:'Solicitação recebida'}));await a.clicar('Recuperar acesso');a.document.querySelector('[name=email_recuperacao]').value='alguem@example.test';
    await a.clicar('Solicitar recuperação');const r=a.chamadas[0];assert(r.options.publico);assert(!r.url.includes('alguem'));assert.equal(JSON.parse(r.options.body).email,'alguem@example.test');
    await a.clicar('Fechar recuperação');assert(!a.document.querySelector('[name=email_recuperacao]'));
});
test('senhas divergentes nao concluem recuperacao e resposta atrasada nao reaparece depois de fechar',async()=>{
    let liberar;const a=await ambiente('VIEWER',()=>new Promise(r=>liberar=r));await a.clicar('Recuperar acesso');
    a.document.querySelector('[name=senha_recuperacao]').value='primeira senha longa';a.document.querySelector('[name=confirmacao_senha]').value='outra senha longa';
    await a.clicar('Definir nova senha');assert.equal(a.chamadas.length,0);
    const pendente=a.botao('Solicitar recuperação').onclick();await a.clicar('Fechar recuperação');liberar({mensagem:'TEXTO ATRASADO'});await pendente;assert(!a.document.body.textContent.includes('TEXTO ATRASADO'));
});
test('perda de sessao impede envio administrativo mesmo com botao anterior',async()=>{
    const a=await ambiente('ADMIN',listar);await a.secoes.financeiro(a.p,a.ctx);a.encerrar();await a.clicar('Salvar padrões financeiros');assert(!a.chamadas.some(c=>c.options?.method==='PUT'));
});
