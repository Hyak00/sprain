/* PDF de texto paginado, gerado localmente. Nenhum dado é enviado a terceiros. */
(function(root){
    'use strict';
    function gerar(linhas){
        if(linhas.reduce((n,l)=>n+String(l??'').length,0)>300000)throw Error('Relatório excede o limite de geração local.');
        const extras={'€':128,'‘':145,'’':146,'“':147,'”':148,'–':150,'—':151,'•':149,'…':133};
        const bytes=s=>Uint8Array.from(Array.from(s,c=>extras[c]??(c.charCodeAt(0)<=255?c.charCodeAt(0):63)));
        let unicode=false;
        const normalizadas=linhas.map(l=>Array.from(String(l??'').normalize('NFC'),c=>{
            if(c.codePointAt(0)<=255||extras[c]!==undefined)return c;
            unicode=true;return '[U+'+c.codePointAt(0).toString(16).toUpperCase()+']';
        }).join(''));
        if(unicode)normalizadas.push('Nota: caracteres fora da fonte latina aparecem como codigos Unicode [U+...].',
            'O HTML, JSON e CSV preservam o texto original em UTF-8.');
        if(normalizadas.reduce((n,l)=>n+l.length,0)>300000)throw Error('Relatório excede o limite local. Use HTML/JSON para o conteúdo integral.');
        const texto=[];
        for(const linha of normalizadas)for(const parte of linha.replace(/[\x00-\x08\x0b-\x1f]/g,' ').split(/\r?\n/)){
            let restante=parte;
            while(restante.length>88){let corte=restante.lastIndexOf(' ',88);if(corte<25)corte=88;texto.push(restante.slice(0,corte));restante=restante.slice(corte).trimStart();}
            texto.push(restante);
        }
        const paginas=[];for(let i=0;i<texto.length;i+=47)paginas.push(texto.slice(i,i+47));if(!paginas.length)paginas.push(['Sem conteúdo.']);
        const objetos=[null,'<< /Type /Catalog /Pages 2 0 R >>',null,'<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>','<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>'];
        const ids=[];
        paginas.forEach((linhas,i)=>{
            const pagina=objetos.length,conteudo=pagina+1;ids.push(pagina);
            const escapar=s=>s.replace(/([\\()])/g,'\\$1');
            const stream='q 0.06 0.09 0.16 rg 0 800 595 42 re f Q\nBT /F2 14 Tf 1 1 1 rg 45 816 Td (SPRain | Relatorio operacional) Tj ET\n'+
                'BT /F1 9.5 Tf 0.08 0.1 0.16 rg 14 TL 45 780 Td '+linhas.map((l,n)=>(n?'T* ':'')+'('+escapar(l)+') Tj').join('\n')+' ET\nBT /F1 9 Tf 45 30 Td (Uso interno | SPRain | '+(i+1)+' / '+paginas.length+') Tj ET';
            objetos.push('<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents '+conteudo+' 0 R >>');
            objetos.push('<< /Length '+bytes(stream).length+' >>\nstream\n'+stream+'\nendstream');
        });
        objetos[2]='<< /Type /Pages /Kids ['+ids.map(id=>id+' 0 R').join(' ')+'] /Count '+ids.length+' >>';
        let saida='%PDF-1.4\n%\xE2\xE3\xCF\xD3\n';const offsets=[0];
        objetos.slice(1).forEach((o,i)=>{offsets.push(bytes(saida).length);saida+=(i+1)+' 0 obj\n'+o+'\nendobj\n';});
        const xref=bytes(saida).length;
        saida+='xref\n0 '+objetos.length+'\n0000000000 65535 f \n'+offsets.slice(1).map(n=>String(n).padStart(10,'0')+' 00000 n \n').join('');
        saida+='trailer\n<< /Size '+objetos.length+' /Root 1 0 R >>\nstartxref\n'+xref+'\n%%EOF\n';return bytes(saida);
    }
    root.PortalPDF={gerar};if(typeof module!=='undefined'&&module.exports)module.exports=root.PortalPDF;
})(typeof window!=='undefined'?window:globalThis);
