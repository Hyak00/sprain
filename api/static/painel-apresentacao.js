(function(root){
    'use strict';
    const numero=(v,d=1)=>typeof v==='number'&&Number.isFinite(v)?v.toFixed(d):'Sem dado';
    const escapar=v=>String(v??'Sem dado').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    root.PainelApresentacao={numero,escapar};if(typeof module!=='undefined'&&module.exports)module.exports=root.PainelApresentacao;
})(typeof window!=='undefined'?window:globalThis);
