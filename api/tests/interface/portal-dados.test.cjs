const{test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');
const{validarImportacao,csv,linhasDecisao,data}=require('../../static/portal-dados.js');const{gerar}=require('../../static/portal-pdf.js');
const viagem=()=>({id_operacao:'NOVA_01',origem_nome:'Origem',origem_lat:-23.54,origem_lon:-46.46,destino_nome:'Destino',destino_lat:-23.55,destino_lon:-46.45,janela_inicio:'2026-10-20T08:00:00-03:00',janela_fim:'2026-10-20T12:00:00-03:00'});
test('valida lote e preserva somente campos do contrato, sem injetar empresa',()=>{const v=viagem();const r=validarImportacao(JSON.stringify([{...v,tenant_id:'empresa'}]),'empresa');assert.deepEqual(r.erros,[]);assert.deepEqual(r.operacoes,[v]);});
test('rejeita arquivo incompatível, enorme, vazio ou com excesso de operações',()=>{for(const t of ['<xml>','{}','[]',JSON.stringify(Array(101).fill(viagem())),' '.repeat(1024*1024+1)])assert.throws(()=>validarImportacao(t,'empresa'));});
test('rejeita empresa diferente, id duplicado, campos desconhecidos e coordenada inválida',()=>{
    const r=validarImportacao(JSON.stringify([{...viagem(),tenant_id:'outra',origem_lat:null,segredo:'x'},viagem()]),'empresa');
    for(const trecho of ['empresa','repetido','suportados','coordenada'])assert(r.erros.some(e=>e.mensagem.includes(trecho)));
});
test('janela exige fuso e calendário válido; fim anterior não é corrigido silenciosamente',()=>{
    for(const inicio of ['2026-02-30T08:00:00Z','2026-10-20T08:00:00','2026-10-20T24:00:00Z','ontem'])assert(validarImportacao(JSON.stringify([{...viagem(),janela_inicio:inicio}]),'e').erros.length);
    assert(validarImportacao(JSON.stringify([{...viagem(),janela_fim:'2026-10-19T12:00:00Z'}]),'e').erros.some(e=>e.mensagem.includes('posterior')));
});
test('medidas são completas, com eixos inteiros, custos sem negativos e coleta válida',()=>{
    const r=validarImportacao(JSON.stringify([{...viagem(),dimensoes:{altura_m:4,eixos:2.5},custos_operacionais:{consumo_km_l:0,custo_por_km:-1,combustivel_data_coleta:'2026-02-30'}}]),'e');
    assert(r.erros.length>=7);
    assert.equal(validarImportacao(JSON.stringify([{...viagem(),dimensoes:{altura_m:4,largura_m:2.6,comprimento_m:15,peso_total_t:30,eixos:4},custos_operacionais:{custo_por_km:0}}]),'e').erros.length,0);
});
test('CSV protege fórmulas de texto, aspas e quebras; número negativo mantém sinal',()=>{
    const s=csv([['=HYPERLINK("x")','  @a',-20,'ação;\ntexto',null]]);assert(s.startsWith('\uFEFF'));assert(s.includes("\"'=HYPERLINK(\"\"x\"\")\""));assert(s.includes('"-20"'));assert(s.includes('"ação;\ntexto"'));assert(!s.includes('null'));
});
test('relatório não inventa autor, economia comprovada ou alternativa a partir de valores substitutos',()=>{
    const r=linhasDecisao({id_operacao:'A',infraestrutura:{financeiro:{custo_alternativa_conhecido_brl:400,custo_desvio_brl:0}}},null,'e','2026-10-20T08:00:00Z').join('\n');
    assert(r.includes('Economia comprovada: não disponível'));assert(r.includes('Custo alternativo estimado, parcelas conhecidas: Não informado'));assert(r.includes('Histórico de decisões:\nIndisponível'));
    assert.equal(data('2026-10-20T08:00:00'),'Não informado');
});
test('PDF contém páginas, fonte com acentos, offsets válidos e conteúdo escapado',()=>{
    const b=gerar(['Decisão (operação) \\ ação',...Array.from({length:100},(_,i)=>'Linha '+i)]);const s=Buffer.from(b).toString('latin1');
    assert(s.startsWith('%PDF-1.4'));assert(s.includes('/Count 3'));assert(s.includes('\\(operação\\)'));assert(s.includes('/WinAnsiEncoding'));
    const offset=Number(s.match(/startxref\n(\d+)/)[1]);assert.equal(s.slice(offset,offset+4),'xref');
    for(const match of s.matchAll(/(\d{10}) 00000 n/g)){const n=Number(match[1]);assert.match(s.slice(n),/^\d+ 0 obj/);}
    if(process.env.SPRAIN_PDF_QA)fs.writeFileSync(process.env.SPRAIN_PDF_QA,b);
});
test('PDF limita documentos excessivos em vez de bloquear a interface',()=>assert.throws(()=>gerar(['a'.repeat(300001)])));
