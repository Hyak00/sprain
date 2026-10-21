const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const {parseHTML}=require('linkedom');
const piloto={empresa:'empresa',emitido_em:'2026-10-20T12:00:00Z',periodo:{inicio:null,fim:null,criterio:'Critério explícito'},amostra:{operacoes:2,recomendacoes:1,consultas:2,decisoes:1,ultimo_calculo:'2026-10-20T10:00:00'},
    indicadores:{economia_comprovada:{valor_brl:null,natureza:'NAO_DISPONIVEL',motivo:'Sem evidência'},custo_observado:{valor_brl:null,natureza:'NAO_DISPONIVEL',motivo:'Sem despesa registrada'},custo_estimado:{valor_brl:0,natureza:'ESTIMATIVA_PARCIAL',operacoes_com_valor:1,operacoes_sem_valor:1,fonte:'Operações'},impacto_potencial:{valor_brl:50,natureza:'POTENCIAL_NAO_COMPROVADO',operacoes_com_valor:1,operacoes_sem_valor:1,fonte:'Recomendações'}},limitacoes:['Cobertura parcial'],fontes:['Banco da empresa']};
const registro={empresa:'empresa',emitido_em:'2026-10-20T12:00:00Z',decisao:{id_decisao:7,id_operacao:'OP1',decisao:'AGUARDAR_MELHORA',motivo_gestor:'Motivo histórico <script>malicioso</script>',usuario_id:'usuario-real',perfil_registro:'OPERATOR',consulta_id:'consulta-antiga',registrado_em:'2026-10-18T12:00:00Z'},snapshot:{id_operacao:'OP1',justificativa:'Cenário da época',infraestrutura:{financeiro:{custo_original_conhecido_brl:42}},contexto_consulta:{fonte:'Fonte histórica',natureza:'SIMULACAO'}},fonte_snapshot:'decisao.snapshot',limitacoes:['Não comprova execução']};
async function ambiente(handler){
    const {window}=parseHTML('<html><body><section id="relatorios"></section></body></html>');const {document}=window;const chamadas=[],downloads=[];let ativo=true;
    window.HTMLElement.prototype.reportValidity=()=>true;
    Object.defineProperty(window.HTMLSelectElement.prototype,'value',{configurable:true,get(){return this.querySelector('option[selected]')?.value||this.querySelector('option')?.value||'';},set(v){this.querySelectorAll('option').forEach(o=>o.toggleAttribute('selected',o.value===v));}});
    async function dados(url,options={}){
        chamadas.push({url,options});if(handler){const r=await handler(url,options);if(r!==undefined)return r;}
        if(url.includes('/relatorios/piloto'))return piloto;
        if(url.includes('/relatorios/decisoes/'))return registro;
        if(url.includes('/relatorios/decisoes')&&!url.includes('.csv'))return{items:[registro.decisao],proximo_offset:null};
        if(url.endsWith('/logistica/operacoes'))return[{id_operacao:'OP1'}];
        if(url==='/api/v1/painel/consultas')return{consulta:{id:'consulta-atual'},explicacao:{id_operacao:'OP1',justificativa:'Consulta atual',infraestrutura:{}}};
        if(url.endsWith('/OP1/decisoes'))return[registro.decisao];
        return '\ufeffempresa;motivo\r\nempresa;registro';
    }
    window.PainelSessao={request:async(url,o)=>({text:async()=>dados(url,o)})};
    const contexto=vm.createContext({window,document,console,TextEncoder,Date,Uint8Array,setTimeout,clearTimeout});
    for(const arq of ['portal-dados.js','portal-pdf.js','painel-relatorios.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../../static',arq),'utf8'),contexto);
    const ctx={usuario:()=>ativo?{tenant_id:'empresa'}:null,atual:()=>ativo,obter:dados,nome:x=>x,
        download:(nome,dados,tipo)=>downloads.push({nome,dados,tipo}),tabela:(p,cols,rows)=>{const pre=document.createElement('pre');pre.textContent=JSON.stringify({cols,rows});p.appendChild(pre);}};
    const p=document.getElementById('relatorios'),botao=s=>Array.from(document.querySelectorAll('button')).find(b=>b.textContent===s),clicar=async s=>{assert(botao(s),s);await botao(s).onclick();};
    return{window,document,app:window.RelatoriosPainel,ctx,p,chamadas,downloads,botao,clicar,encerrar:()=>ativo=false};
}
test('modelo piloto distingue ausencia, zero, cobertura, fonte e fuso nao registrado',async()=>{
    const a=await ambiente(),s=a.app.linhasPiloto(piloto).join('\n');
    for(const trecho of ['Economia comprovada: Não informado','Custo observado: Não informado','Custo estimado da rota original: R$','0,00','1 sem valor','Cobertura parcial','Banco da empresa','fuso não registrado'])assert(s.includes(trecho),trecho);
});
test('relatorio individual conserva fotografia e autoria e nao inventa dados legados',async()=>{
    const a=await ambiente(),s=a.app.linhasIndividual(registro).join('\n');assert(s.includes('42,00'));assert(s.includes('usuario-real'));assert(s.includes('consulta-antiga'));assert(s.includes('Fonte histórica'));
    const legado=a.app.linhasIndividual({...registro,snapshot:null,fonte_snapshot:null}).join('\n');assert(legado.includes('Sem fotografia histórica'));assert(!legado.includes('42,00'));
});
test('HTML interno e autonomo, UTF-8 e trata conteudo como texto',async()=>{
    const a=await ambiente(),s=a.app.html(['<script>alert("x")</script>','ação']);assert(s.includes('&lt;script&gt;'));assert(!s.includes('<script>'));assert(s.includes('charset="utf-8"'));assert(s.includes("default-src 'none'"));assert(s.includes('ação'));
});
test('VIEWER gera piloto PDF e CSV historicos sem chamar endpoints de gravacao',async()=>{
    const a=await ambiente();await a.app.render(a.p,a.ctx);await a.clicar('Baixar PDF do piloto');assert.equal(a.downloads[0].tipo,'application/pdf');assert(Buffer.from(a.downloads[0].dados).toString('latin1').startsWith('%PDF-1.4'));
    await a.clicar('Exportar histórico de consultas (CSV)');await a.clicar('Exportar histórico de decisões (CSV)');assert.equal(a.downloads.length,3);assert(!a.chamadas.some(c=>c.options.method==='POST'));
});
test('decisao individual baixa PDF e HTML da fotografia, sem consultar rota atual',async()=>{
    const a=await ambiente();await a.app.render(a.p,a.ctx);await a.clicar('Abrir relatório da decisão #7');await a.clicar('Baixar PDF da decisão #7');await a.clicar('Baixar HTML da decisão #7');
    assert(Buffer.from(a.downloads[0].dados).toString('latin1').includes('42,00'));assert(a.downloads[1].dados.includes('&lt;script&gt;'));
    assert(!a.chamadas.some(c=>c.url.includes('/explicacao')||c.options.method==='POST'));assert.equal(a.document.querySelectorAll('script').length,0);
});
test('CSV da consulta carregada seleciona seu identificador exato e decisoes usam autor real',async()=>{
    const a=await ambiente();await a.app.render(a.p,a.ctx);await a.clicar('Carregar consulta e decisões');assert(a.p.textContent.includes('usuario-real'));await a.clicar('Baixar consulta (CSV)');assert(a.chamadas.some(c=>c.url.endsWith('consultas.csv?id_consulta=consulta-atual')));
});
test('logout durante preparo do CSV descarta o arquivo sem download',async()=>{
    let liberar;const a=await ambiente(url=>url.includes('consultas.csv')?new Promise(r=>liberar=r):undefined);await a.app.render(a.p,a.ctx);
    const pendente=a.botao('Exportar histórico de consultas (CSV)').onclick();await new Promise(r=>setImmediate(r));a.encerrar();liberar('DADOS ANTIGOS');await pendente;assert.equal(a.downloads.length,0);
});
test('filtros invalidos nao alteram escopo e datas validas chegam aos tres relatorios',async()=>{
    const a=await ambiente();await a.app.render(a.p,a.ctx);const inicio=a.document.querySelector('[name=relatorio_inicio]'),fim=a.document.querySelector('[name=relatorio_fim]');
    inicio.value='2026-10-01';const antes=a.chamadas.length;await a.clicar('Atualizar período e relatórios');assert.equal(a.chamadas.length,antes);
    fim.value='2026-10-20';await a.clicar('Atualizar período e relatórios');await a.clicar('Exportar histórico de consultas (CSV)');assert(a.chamadas.filter(c=>c.url.includes('inicio=2026-10-01&fim=2026-10-20')).length>=3);
});
test('falha parcial do piloto preserva acesso ao historico e nao declara economia',async()=>{
    const a=await ambiente(url=>{if(url.includes('/relatorios/piloto'))throw Error('Offline');});await a.app.render(a.p,a.ctx);assert(a.p.textContent.includes('Indicadores indisponíveis'));assert(a.botao('Abrir relatório da decisão #7'));assert(!a.botao('Baixar PDF do piloto'));
});

test('piloto inclui custos e desvios informados sem convertê-los em economia comprovada',async()=>{
 const a=await ambiente(),d=structuredClone(piloto);d.amostra.viagens_com_resultado=1;d.amostra.viagens_com_custo_informado=1;d.indicadores.custo_informado={valor_brl:0,natureza:'AUTODECLARADO_NAO_VERIFICADO',viagens_com_valor:1,viagens_sem_valor:1,fonte:'Resultado declarado'};d.indicadores.desvios_informados={quantidade:1};
 const linhas=a.app.linhasPiloto(d).join('\n');for(const s of ['Custo informado (não verificado): R$','Autodeclarado; não verificado','1 sem custo','Viagens com resultado informado: 1','Desvios informados (não verificados): 1','Economia comprovada: Não informado'])assert(linhas.includes(s),s);
});
