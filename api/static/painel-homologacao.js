/* Proveniencia e navegacao acessivel complementares aos controles existentes. */
(function(root){
    'use strict';
    async function configurarAcesso(){
        try{
            const r=await root.PainelSessao.request('/api/v1/acesso/configuracao',{publico:true,timeout:10000});
            const d=await r.json();document.querySelector('.demo-accounts').hidden=!d.demonstracao_disponivel;
        }catch(e){document.getElementById('login-erro').textContent='Não foi possível consultar as opções de acesso. O login individual continua disponível; confira a conexão.';}
    }
    function nota(id,texto){const p=document.createElement('p');p.className='mvp-proveniencia';p.textContent=texto;document.getElementById(id)?.prepend(p);}
    nota('frota-panel','Fonte: cadastro da frota da empresa. A data de atualização está em cada veículo; cadastros antigos sem data continuam identificados como não informados. Medidas e custos precisam corresponder ao veículo carregado.');
    nota('corredor-panel','Fonte: serviço de corredor intermunicipal. Fonte, validade de pedágios e limites estão nos detalhes quando fornecidas; ausência de data não comprova atualização.');
    const legenda=document.createElement('details'),s=document.createElement('summary');s.textContent='Como interpretar os níveis de risco';legenda.appendChild(s);
    for(const texto of ['NORMAL: o cálculo não detectou o limiar de risco no cenário consultado; não garante passagem segura.',
        'RISCO: o cenário requer atenção aos trechos vulneráveis e à cobertura dos dados.',
        'CRÍTICO: há limiar crítico ou incompatibilidade física; confira a justificativa e a alternativa.',
        'IVI: vulnerabilidade física/hidrológica da malha; não é probabilidade de acidente nem ocorrência confirmada.',
        'Cores das ocorrências identificam a natureza declarada da fonte. Previsão, histórico e relato pendente não equivalem a confirmação.']){
        const p=document.createElement('p');p.textContent=texto;legenda.appendChild(p);
    }document.querySelector('.map-legend').appendChild(legenda);
    const overlay=document.getElementById('login-overlay');
    for(const[id,label]of Object.entries({'veic-id':'Identificação do caminhão','veic-placa':'Placa do caminhão','veic-modelo':'Modelo do caminhão','veic-tipo':'Tipo do caminhão'}))document.getElementById(id)?.setAttribute('aria-label',label);
    overlay.addEventListener('keydown',e=>{
        if(e.key==='Enter'&&e.target.id==='login-email'){e.preventDefault();root.realizarLogin();}
        if(e.key!=='Tab')return;
        const c=Array.from(overlay.querySelectorAll('input,button')).filter(x=>!x.disabled&&x.getClientRects().length);
        const primeiro=c[0],ultimo=c[c.length-1];
        if(e.shiftKey&&document.activeElement===primeiro){e.preventDefault();ultimo?.focus();}
        else if(!e.shiftKey&&document.activeElement===ultimo){e.preventDefault();primeiro?.focus();}
    });
    document.getElementById('login-email').focus();configurarAcesso();
    root.PainelHomologacao={configurarAcesso};
})(window);
