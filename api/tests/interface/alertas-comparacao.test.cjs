const {test}=require('node:test');
const assert=require('node:assert/strict');
const {evento,comparacao,moeda,instante}=require('../../static/alertas-comparacao.js');
const agora=Date.parse('2026-10-15T12:00:00Z');
const geo=(...ids)=>({type:'FeatureCollection',features:ids.map(id=>({type:'Feature',properties:{id_trecho:id},geometry:{type:'LineString',coordinates:[[0,0],[1,1]]}}))});
const op={validacao_rota:{rota_alternativa_disponivel:true},geometrias:{rota_original_geojson:geo(1,2),rota_alternativa_geojson:geo(2,3)}};
const alerta={id_evento:'a',trechos_afetados:[2],expiracao_em:'2026-10-15T13:00:00Z',ultima_atualizacao:'2026-10-15T11:00:00Z',confianca:0.9};
test('associação exige IDs nas geometrias, não apenas proximidade ou confiança',()=>{
    assert.match(evento(alerta,op,agora).local,/original e à rota alternativa/);
    assert.match(evento({...alerta,trechos_afetados:[9]},op,agora).local,/Sem associação/);
    assert.match(evento({...alerta,trechos_afetados:['1']},op,agora).local,/original/);
    assert.match(evento({...alerta,trechos_afetados:null},{},agora).local,/contexto público/);
});
test('expiração é avaliada pelo relógio, não pela idade retornada pelo servidor',()=>{
    assert.equal(evento(alerta,op,agora).expirado,false);
    assert.equal(evento(alerta,op,agora+3600000).expirado,true);
    assert.match(evento({...alerta,idade_minutos:0},op,agora+3600000).temporal,/EXPIRADO/);
});
test('datas sem fuso, inválidas e futuras não são tratadas como atualização válida',()=>{
    for(const v of [null,'','ruim','2026-10-15T11:00:00']) assert.equal(instante(v),null);
    assert.match(evento({...alerta,expiracao_em:null},op,agora).temporal,/Validade não informada/);
    assert.match(evento({...alerta,ultima_atualizacao:'2026-10-15T12:30:00Z'},op,agora).temporal,/futura/);
    assert.match(evento({...alerta,ultima_atualizacao:null},op,agora).temporal,/Atualização não informada/);
});
test('confiança ausente ou fora do domínio não vira zero ou certeza',()=>{
    for(const confianca of [null,undefined,NaN,-1,2,'0.9']) assert.equal(evento({...alerta,confianca},op,agora).confianca,'Não informado');
    assert.equal(evento({...alerta,confianca:0},op,agora).confianca,'0%');
    assert.equal(evento(alerta,op,agora).confianca,'90%');
});
test('ausência de valor financeiro é diferente de custo zero',()=>{
    for(const v of [null,undefined,'',false,'0',NaN,Infinity])assert.equal(moeda(v),'Não informado');
    assert.match(moeda(0),/0,00/); assert.match(moeda(-12.5),/-.*12,50/);
});
test('caminho alternativo exige sinalização e geometria, sem reaproveitar fallback numérico',()=>{
    assert.equal(comparacao(op).alternativa,true);
    for(const candidato of [{}, {...op,validacao_rota:{}},{...op,geometrias:{}},{...op,geometrias:{rota_alternativa_geojson:geo()}}]) {
        const c=comparacao({...candidato,metricas:{distancia_alternativa_km:30},infraestrutura:{financeiro:{custo_alternativa_conhecido_brl:100,custo_desvio_brl:0}}});
        assert.equal(c.alternativa,false);assert.equal(c.rows[1][1],null);assert.equal(c.rows[2][1],null);
    }
});
test('preserva sinais e separa diferença operacional de perda potencial sem recalcular',()=>{
    const f={custo_original_conhecido_brl:100,custo_alternativa_conhecido_brl:80,custo_desvio_brl:-20,economia_operacional_conhecida_brl:20,prejuizo_potencial_evitado_brl:500,economia_liquida_potencial_brl:520,tarifas_pendentes_comparacao:2};
    const c=comparacao({...op,infraestrutura:{financeiro:f}});
    assert.equal(c.rows[2][1],-20);assert.equal(c.rows[5][1],20);assert.equal(c.rows[6][1],500);assert.equal(c.rows[7][1],520);assert.equal(c.pendentes,2);
    assert.equal(comparacao(op).pendentes,null);
});
test('fonte, estado e incógnitas não recebem valores padrão que aparentem confirmação',()=>{
    const v=evento({},op,agora);
    for(const campo of ['id','categoria','fonte','status','desconhecido','deteccao'])assert.equal(v[campo],'Não informado');
});
