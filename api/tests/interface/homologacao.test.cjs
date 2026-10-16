const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const {parseHTML}=require('linkedom');
async function ambiente(resposta){
    const {window}=parseHTML('<html><body><div id="login-overlay"><input id="login-email"><input id="login-senha"><div id="login-erro"></div><div class="demo-accounts" hidden></div></div><div id="frota-panel"></div><div id="corredor-panel"></div><div class="map-legend"></div></body></html>');
    const chamadas=[];window.PainelSessao={request:async(p,o)=>{chamadas.push({p,o});if(resposta instanceof Error)throw resposta;return{json:async()=>resposta};}};
    const ctx=vm.createContext({window,document:window.document});vm.runInContext(fs.readFileSync(path.join(__dirname,'../../static/painel-homologacao.js'),'utf8'),ctx);
    await new Promise(r=>setImmediate(r));return {window,document:window.document,chamadas};
}
test('producao nao apresenta atalhos de contas demo nem preenche credenciais',async()=>{
    const a=await ambiente({demonstracao_disponivel:false});assert(a.document.querySelector('.demo-accounts').hidden);
    assert.equal(a.document.querySelector('#login-email').value,'');assert.equal(a.chamadas[0].p,'/api/v1/acesso/configuracao');assert(a.chamadas[0].o.publico);
});
test('ambiente de demonstracao preserva os atalhos de acesso existentes',async()=>{
    const a=await ambiente({demonstracao_disponivel:true});assert.equal(a.document.querySelector('.demo-accounts').hidden,false);
});
test('falha ao consultar configuracao nao libera demonstracao e informa recuperacao',async()=>{
    const a=await ambiente(new Error('offline'));assert(a.document.querySelector('.demo-accounts').hidden);assert.match(a.document.querySelector('#login-erro').textContent,/conexão/);
});
