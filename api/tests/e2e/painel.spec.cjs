const {test,expect}=require('@playwright/test');
const fs=require('node:fs/promises'),path=require('node:path');
const senha='Apenas-Teste-Isolado-2026!';
test.beforeEach(async({page,request,baseURL})=>{
 const r=await request.get('/api/v1/demonstracao/estado');expect(r.ok()).toBeTruthy();expect((await r.json()).demo_isolada).toBe(true);
 // Backend real. Somente os assets externos do mapa são servidos localmente,
 // com a mesma versão; o estilo vazio elimina dependência de tiles da Internet.
 await page.route('**/*',async route=>{const u=new URL(route.request().url());
  if(u.origin===new URL(baseURL).origin)return route.continue();
  if(u.hostname==='unpkg.com'&&u.pathname.includes('maplibre-gl@3.6.2/dist/maplibre-gl.')){
   const nome=u.pathname.endsWith('.css')?'maplibre-gl.css':'maplibre-gl.js';
   return route.fulfill({path:path.join(__dirname,'../../..','node_modules/maplibre-gl/dist',nome),contentType:nome.endsWith('css')?'text/css':'text/javascript'});
  }
  if(u.hostname==='basemaps.cartocdn.com'&&u.pathname.endsWith('style.json'))return route.fulfill({json:{version:8,sources:{},layers:[{id:'fundo-teste',type:'background',paint:{'background-color':'#111827'}}]}});
  return route.abort();
 });
 await page.goto('/static/b2b.html');
});
async function entrar(page,nome){await page.getByLabel('E-mail Corporativo',{exact:true}).fill(nome+'@e2e.invalid');await page.getByLabel('Senha de Acesso',{exact:true}).fill(senha);await page.getByRole('button',{name:'Entrar na Torre de Controle',exact:true}).click();await expect(page.locator('#login-overlay')).toBeHidden();await expect(page.getByRole('button',{name:'Central de trabalho',exact:true})).toBeVisible();}
async function central(page,secao){await page.getByRole('button',{name:'Central de trabalho',exact:true}).click();await ferramenta(page,secao);}
async function ferramenta(page,secao){await page.getByText('Navegar entre ferramentas',{exact:true}).click();await page.getByRole('navigation',{name:'Seções da central',exact:true}).getByRole('button',{name:secao,exact:true}).click();}
async function comparar(page){await page.getByRole('button',{name:'Comparar rotas',exact:true}).click();await expect(page.getByRole('dialog',{name:'Comparação e decisão da viagem',exact:true})).toBeVisible();}
async function baixar(page,nome){const evento=page.waitForEvent('download');await page.getByRole('button',{name:nome,exact:true}).click();const d=await evento;const file=await d.path();expect(file).toBeTruthy();return fs.readFile(file);}
function proximaSegunda(){
 const hoje=new Intl.DateTimeFormat('en-CA',{timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
 const data=new Date(hoje+'T12:00:00Z');data.setUTCDate(data.getUTCDate()+((8-data.getUTCDay())%7||7));return data.toISOString().slice(0,10);
}

test('VIEWER: login, controle de papel, PDF/CSV reais e logout',async({page})=>{
 await entrar(page,'leitor');await expect(page.getByText('PERFIL: VIEWER',{exact:true})).toBeVisible();await page.getByText('Cenário e indicadores',{exact:true}).click();await expect(page.getByRole('button',{name:'↓ Exportar CSV',exact:true})).toBeDisabled();
 await central(page,'Relatórios e exportações');await expect(page.getByRole('button',{name:'Painel operacional interno',exact:true})).toBeHidden();
 expect((await baixar(page,'Baixar PDF do piloto')).subarray(0,8).toString()).toContain('%PDF-1.4');
 expect((await baixar(page,'Exportar histórico de consultas (CSV)')).toString('utf8')).toContain('empresa');
 await page.getByRole('button',{name:'Fechar',exact:true}).click();await page.getByRole('button',{name:'Trocar Conta',exact:true}).click();await expect(page.getByRole('button',{name:'Entrar na Torre de Controle',exact:true})).toBeVisible();
});

test('OPERADOR: corredor persistente, recorrência e despacho idempotente',async({page})=>{
 await entrar(page,'operador');await central(page,'Corredores e recorrências');await page.getByRole('button',{name:'Novo corredor',exact:true}).click();
 const nome='E2E corredor '+Date.now();
 for(const [label,v]of [['Nome do corredor',nome],['Nome da origem','DEMO A'],['Latitude da origem','-22.25'],['Longitude da origem','-47.84'],['Nome do destino','DEMO C'],['Latitude do destino','-22.25'],['Longitude do destino','-47.82']])await page.getByLabel(label,{exact:true}).fill(v);
 await page.getByRole('button',{name:'Salvar corredor',exact:true}).click();await expect(page.getByRole('heading',{name:nome,exact:true})).toBeVisible();
 const card=page.getByRole('article').filter({has:page.getByRole('heading',{name:nome,exact:true})});await card.getByRole('button',{name:'Adicionar recorrência',exact:true}).click();
 await page.getByLabel('Nome da recorrência',{exact:true}).fill('E2E semanal');await page.getByLabel('Horário de partida (São Paulo)',{exact:true}).fill('08:00');await page.getByLabel('Duração da janela (minutos)',{exact:true}).fill('240');await page.getByLabel('Segunda',{exact:true}).check();
 await page.getByRole('combobox',{name:'Caminhão da frota (opcional)',exact:true}).selectOption('DEMO_34_CAMINHAO');await page.getByRole('button',{name:'Salvar recorrência',exact:true}).click();
 await card.getByText('E2E semanal',{exact:true}).click();await card.getByRole('button',{name:'Preparar despacho',exact:true}).click();await page.getByLabel('Data da viagem',{exact:true}).fill(proximaSegunda());
 await page.getByRole('button',{name:'Criar viagem desta recorrência',exact:true}).click();await expect(page.getByRole('button',{name:'Abrir viagem criada',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Criar viagem desta recorrência',exact:true}).click();await expect(page.getByText(/nenhum despacho duplicado/)).toBeVisible();
});

test('ADMIN: premissas versionadas, fontes e falhas internas reais',async({page})=>{
 await entrar(page,'admin');await central(page,'Premissas financeiras');
 await page.getByRole('dialog').getByLabel('Custo total por km (R$/km)',{exact:true}).fill('4.5');await page.getByRole('button',{name:'Salvar padrões financeiros',exact:true}).click();await expect(page.getByText(/Versão: [1-9]/)).toBeVisible();
 await ferramenta(page,'Painel operacional interno');await expect(page.getByRole('heading',{name:'Fontes e atualização',exact:true})).toBeVisible();
 await expect(page.getByRole('heading',{name:'Métricas de qualidade',exact:true})).toBeVisible();await page.getByRole('combobox',{name:'Situação da importação',exact:true}).selectOption('FALHA');await expect(page.getByText(/offset=0&status=FALHA/)).toBeVisible();
});

test('DEMO: bloqueio, custo, liberação e mapa pelo motor real',async({page})=>{
 await entrar(page,'leitor');await central(page,'Demonstração');await expect(page.getByText(/evento originalmente pretendido pela equipe não foi identificado/)).toBeVisible();
 await page.getByRole('button',{name:'2. Simular bloqueio ilustrativo',exact:true}).click();await expect(page.getByRole('cell',{name:'3.03',exact:true})).toBeVisible();await expect(page.getByText(/Economia comprovada: indisponível/)).toBeVisible();
 await page.getByRole('button',{name:'Ver exercício sintético no mapa',exact:true}).click();await page.getByText('Legenda e camadas do mapa',{exact:true}).click();await expect(page.getByText(/Exercício sintético: linha roxa original/)).toBeVisible();
 await central(page,'Demonstração');await page.getByRole('button',{name:'3. Simular liberação',exact:true}).click();await expect(page.getByRole('cell',{name:'2.06',exact:true})).toHaveCount(2);
});

test('ADMIN: cadastro de usuário, papel e desativação com backend real',async({page})=>{
 await entrar(page,'admin');await central(page,'Administração da empresa');
 const email='novo-'+Date.now()+'@e2e.invalid';await page.getByText('Criar usuário',{exact:true}).first().click();await page.getByLabel('E-mail do usuário',{exact:true}).fill(email);await page.getByLabel('Senha inicial (15 a 256 caracteres)',{exact:true}).fill(senha);
 await page.getByRole('button',{name:'Criar usuário',exact:true}).click();await expect(page.getByText(/Usuário criado/)).toBeVisible();await page.getByRole('button',{name:'Atualizar administração',exact:true}).click();
 const usuario=page.getByRole('article').filter({has:page.getByRole('heading',{name:email,exact:true})});await expect(usuario).toBeVisible();
 await usuario.getByRole('combobox',{name:'Papel de acesso',exact:true}).selectOption('OPERATOR');await usuario.getByLabel('Conferi o usuário e o novo papel.',{exact:true}).check();await usuario.getByRole('button',{name:'Salvar papel de '+email,exact:true}).click();await expect(usuario.getByText('OPERATOR · Ativo',{exact:true})).toBeVisible();
 await usuario.getByLabel('Confirmo a desativação deste usuário.',{exact:true}).check();await usuario.getByRole('button',{name:'Desativar '+email,exact:true}).click();await expect(usuario.getByText('OPERATOR · Desativado',{exact:true})).toBeVisible();
});

test('OPERADOR: comparação, premissas, decisão vinculada, histórico e relato',async({page})=>{
 await entrar(page,'operador');
 const linha=page.getByRole('row',{name:/^Inspecionar/}).first();await expect(linha).toBeVisible({timeout:45000});await linha.click();await comparar(page);
 await expect(page.getByText('Editar premissas e recalcular esta operação',{exact:true})).toBeVisible();
 await page.getByText('Editar premissas e recalcular esta operação',{exact:true}).click();
 await page.locator('#inspector summary').filter({hasText:/^Premissas financeiras$/}).click();
 await page.getByLabel('Custo total por km (R$/km)',{exact:true}).fill('4.75');
 await page.getByLabel('Chuva simulada para este recálculo (mm/h)',{exact:true}).fill('35');
 await page.getByRole('button',{name:'Salvar premissas e recalcular',exact:true}).click();
 await expect(page.getByText('Natureza: SIMULACAO',{exact:true})).toBeVisible();
 const motivo='E2E decisão '+Date.now();await page.getByLabel('Motivo da decisão do gestor',{exact:true}).fill(motivo);
 await page.getByRole('button',{name:'Aguardar',exact:true}).click();
 await expect(page.getByText(/Decisao \[AGUARDAR_MELHORA\] auditada/)).toBeVisible();
 await page.getByRole('button',{name:'Ver histórico persistente de consultas',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Histórico de consultas',exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:/^Abrir fotografia /}).first()).toBeVisible();
 await ferramenta(page,'Reportar ocorrência');
 await page.getByLabel('Descrição do que foi observado',{exact:true}).fill('E2E relato sintético sem confirmação');
 await page.getByLabel('Data/hora observada (horário do seu navegador)',{exact:true}).fill('2026-10-12T08:00');
 await page.getByLabel('Latitude do relato',{exact:true}).fill('-22.25');await page.getByLabel('Longitude do relato',{exact:true}).fill('-47.84');
 await page.getByRole('button',{name:'Registrar ocorrência não detectada',exact:true}).click();
 await expect(page.getByText('Relato registrado e exibido no mapa, identificado como não validado.',{exact:true})).toBeVisible();
});

test('VIEWER: central acessível em tela pequena e Escape devolve foco',async({page})=>{
 await page.setViewportSize({width:360,height:800});await entrar(page,'leitor');await central(page,'Relatórios e exportações');
 await page.getByRole('button',{name:'Baixar PDF do piloto',exact:true}).scrollIntoViewIfNeeded();await expect(page.getByRole('button',{name:'Baixar PDF do piloto',exact:true})).toBeInViewport();
 await page.keyboard.press('Escape');await expect(page.getByRole('dialog')).toBeHidden();
 await expect(page.getByRole('button',{name:'Central de trabalho',exact:true})).toBeFocused();
});

test('UX: menu principal e configuração do primeiro cliente persistem o aceite',async({page,request})=>{
 await entrar(page,'operador');const nav=page.getByRole('navigation',{name:'Navegação principal',exact:true});
 await expect(nav.getByRole('button',{name:'Frota',exact:true})).toBeVisible();
 await page.locator('#ux-navegacao').getByRole('button',{name:'Configurar primeiro cliente',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Configurar primeiro cliente',exact:true})).toBeVisible();
 const iniciar=page.getByRole('button',{name:'Iniciar configuração do cliente',exact:true});
 if(await iniciar.isVisible())await iniciar.click();
 await expect(page.getByRole('button',{name:'Consultar viagens',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Consultar viagens',exact:true}).click();
 await expect(page.getByRole('row',{name:/^Inspecionar/}).first()).toBeVisible({timeout:45000});
 await page.getByRole('row',{name:/^Inspecionar/}).first().click();await comparar(page);
 await page.getByRole('button',{name:'Confirmar primeiro resultado útil',exact:true}).click();
 await expect(page.getByText('Primeiro resultado útil registrado no servidor. Consulte Configurar primeiro cliente para ver a medição.',{exact:true})).toBeVisible();await page.keyboard.press('Escape');
 await page.locator('#ux-navegacao').getByRole('button',{name:'Configurar primeiro cliente',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Primeiro resultado registrado',exact:true})).toBeVisible();
 await expect(page.getByText(/Tempo até o primeiro resultado: .* segundos/)).toBeVisible();
 await page.getByRole('button',{name:'Fechar',exact:true}).click();await page.getByRole('button',{name:'Trocar Conta',exact:true}).click();
 await entrar(page,'operador');await page.locator('#ux-navegacao').getByRole('button',{name:'Configurar primeiro cliente',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Primeiro resultado registrado',exact:true})).toBeVisible();
});

test('UX: comparação de espera consome o motor econômico sem afirmar economia real',async({page})=>{
 await entrar(page,'operador');
 const linha=page.getByRole('row',{name:/^Inspecionar/}).first();await expect(linha).toBeVisible({timeout:45000});await linha.click();await comparar(page);
 await expect(page.getByRole('heading',{name:'Compare os custos da viagem',exact:true})).toBeVisible();
 await page.getByText('Comparar um cenário de espera',{exact:true}).click();
 await page.getByLabel('Tempo de espera informado (min)',{exact:true}).fill('30');
 await page.getByLabel('Chuva simulada para comparar a espera (mm/h)',{exact:true}).fill('35');
 await page.getByRole('button',{name:'Calcular cenário de espera',exact:true}).click();
 await expect(page.getByText('Cenário calculado. Confira os valores e as premissas abaixo.',{exact:true})).toBeVisible();
 await expect(page.getByText(/Custo estimado original: R\$.*Alternativa: R\$.*Aguardar: R\$/)).toBeVisible();
 await expect(page.getByText(/Risco apos a espera nao foi reavaliado/)).toBeVisible();
});

test('UX: menu recolhível em celular mantém acesso à frota e aos relatórios',async({page})=>{
 await page.setViewportSize({width:390,height:844});await entrar(page,'leitor');
 const nav=page.getByRole('navigation',{name:'Navegação principal',exact:true});await expect(nav).toBeHidden();
 await page.getByRole('button',{name:'Menu',exact:true}).click();await nav.getByRole('button',{name:'Frota',exact:true}).click();
 await expect(nav).toBeHidden();await expect(page.getByRole('button',{name:'Menu',exact:true})).toHaveAttribute('aria-expanded','false');
 await page.getByRole('button',{name:'Menu',exact:true}).click();await nav.getByRole('button',{name:'Relatórios',exact:true}).click();
 expect((await baixar(page,'Baixar PDF do piloto')).subarray(0,8).toString()).toContain('%PDF-1.4');
});

test('Organização: preserva os controles anteriores, infraestrutura, fontes e camadas',async({page})=>{
 const falhas=[];page.on('pageerror',e=>falhas.push(e.message));
 await entrar(page,'leitor');
 for(const id of require('./controles-preservados.json'))await expect(page.locator('[id="'+id+'"]')).toHaveCount(1);
 const nav=page.getByRole('navigation',{name:'Navegação principal',exact:true});
 await expect(nav.getByRole('button')).toHaveText(['Operações','Frota','Corredores','Relatórios','Configurações']);
 await expect(page.getByRole('row',{name:/^Inspecionar/}).first()).toBeVisible({timeout:45000});
 await page.getByRole('row',{name:/^Inspecionar/}).first().click();
 await expect(page.locator('#ux-comparar')).not.toBeVisible();await comparar(page);
 for(const id of ['box-orig-km','box-alt-km','modal-custo','modal-prejuizo','modal-justificativa'])await expect(page.locator('#'+id)).not.toBeEmpty();
 await page.getByText('Pedágios, caminhão e restrições',{exact:true}).click();await expect(page.locator('#infra-auditoria')).toContainText(/(altura|Medidas|medidas)/);
 await page.getByText('Postos, historico e atualizacao dos dados',{exact:true}).click();
 await expect(page.getByLabel('Incluir localizacoes aproximadas da ANP (conferir antes de usar)',{exact:true})).toBeVisible();
 await expect(page.getByText('Editar premissas e recalcular esta operação',{exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'Confirmar primeiro resultado útil',exact:true})).toBeDisabled();
 await page.keyboard.press('Escape');await expect(page.getByRole('button',{name:'Comparar rotas',exact:true})).toBeFocused();
 await nav.getByRole('button',{name:'Frota',exact:true}).click();await nav.getByRole('button',{name:'Operações',exact:true}).click();await comparar(page);
 await expect(page.getByText('Postos, historico e atualizacao dos dados',{exact:true})).toBeVisible();await page.keyboard.press('Escape');
 await page.getByText('Legenda e camadas do mapa',{exact:true}).click();await page.getByText('Controlar camadas do mapa',{exact:true}).click();
 await expect(page.locator('.portal-camadas input[type=checkbox]')).toHaveCount(8);
 const camada=page.getByLabel('Pedágios e limites cadastrados',{exact:true});await camada.uncheck();await expect(camada).not.toBeChecked();await camada.check();
 await page.getByText('Cenário e indicadores',{exact:true}).click();await page.getByText('Indicadores e impacto potencial',{exact:true}).click();
 for(const id of ['kpi-total','kpi-afetadas','kpi-custo','kpi-evitado'])await expect(page.locator('#'+id)).toBeVisible();
 expect(falhas).toEqual([]);
});

test('ADMIN: a escolha de ponte no mapa continua utilizável dentro da frota',async({page})=>{
 await entrar(page,'admin');await page.getByRole('navigation',{name:'Navegação principal',exact:true}).getByRole('button',{name:'Frota',exact:true}).click();
 await page.getByText('Administrar pedágios e pontes (ADMIN)',{exact:true}).click();
 await page.getByRole('button',{name:'Escolher localização no mapa',exact:true}).click();
 await expect(page.locator('#map-container')).toBeVisible();await expect(page.getByRole('button',{name:'Concluir escolha no mapa',exact:true})).toBeVisible();
 const canvas=page.locator('#map canvas');await expect(canvas).toBeVisible();await canvas.click({position:{x:100,y:120}});
 await expect(page.locator('#infra-cadastro').getByLabel('Latitude',{exact:true})).not.toHaveValue('');
 await expect(page.locator('#infra-cadastro').getByLabel('Longitude',{exact:true})).not.toHaveValue('');
 await expect(page.locator('#map-container')).toBeHidden();
 await page.getByRole('button',{name:'Escolher localização no mapa',exact:true}).click();await page.getByRole('button',{name:'Concluir escolha no mapa',exact:true}).click();await expect(page.locator('#map-container')).toBeHidden();
 await page.setViewportSize({width:360,height:800});
 await page.getByRole('button',{name:'Escolher localização no mapa',exact:true}).click();
 expect(await page.locator('html').evaluate(el=>el.scrollWidth)).toBeLessThanOrEqual(360);
 await page.getByRole('button',{name:'Concluir escolha no mapa',exact:true}).click();
 await page.getByRole('button',{name:'Menu',exact:true}).click();await page.getByRole('navigation',{name:'Navegação principal',exact:true}).getByRole('button',{name:'Operações',exact:true}).click();
 const latitude=await page.locator('#infra-cadastro').getByLabel('Latitude',{exact:true}).inputValue();await page.locator('#map canvas').click({position:{x:80,y:100}});
 await expect(page.locator('#infra-cadastro').getByLabel('Latitude',{exact:true})).toHaveValue(latitude);
});

test('Celular: lista, comparação e restrições cabem na largura e logout limpa a viagem',async({page})=>{
 await page.setViewportSize({width:360,height:800});await entrar(page,'leitor');
 await expect(page.getByRole('row',{name:/^Inspecionar/}).first()).toBeVisible({timeout:45000});await page.getByRole('row',{name:/^Inspecionar/}).first().click();
 await comparar(page);await page.getByText('Pedágios, caminhão e restrições',{exact:true}).click();
 expect(await page.locator('html').evaluate(el=>el.scrollWidth)).toBeLessThanOrEqual(360);
 const dialog=page.locator('#ux-comparar');expect(await dialog.evaluate(el=>el.scrollWidth<=el.clientWidth)).toBe(true);
 await page.keyboard.press('Escape');await page.getByRole('button',{name:'Trocar Conta',exact:true}).click();
 await expect(page.locator('#ux-rota-resumo')).toBeHidden();await expect(dialog).not.toBeVisible();await expect(page.locator('.ux-cabecalho-pagina')).toBeHidden();
 await expect(page.getByRole('button',{name:'Entrar na Torre de Controle',exact:true})).toBeVisible();
});

test('Falha de consulta: não oferece comparação anterior como se fosse a viagem atual',async({page})=>{
 await entrar(page,'leitor');await expect(page.getByRole('button',{name:'Comparar rotas',exact:true})).toBeEnabled({timeout:45000});
 await page.route('**/api/v1/painel/consultas',route=>route.request().method()==='POST'?route.fulfill({status:503,json:{detail:'Indisponível no teste'}}):route.continue());
 await page.getByRole('row',{name:/^Inspecionar/}).nth(1).click();
 await expect(page.locator('#ux-rota-resumo')).toContainText('Consulta indisponível');await expect(page.getByRole('button',{name:'Comparar rotas',exact:true})).toBeDisabled();
 await expect(page.locator('#ux-comparar')).not.toBeVisible();
});
