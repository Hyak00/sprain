const {defineConfig}=require('@playwright/test');
const baseURL=process.env.E2E_BASE_URL||'http://127.0.0.1:18002';
const u=new URL(baseURL);
if(u.protocol!=='http:'||!['localhost','127.0.0.1'].includes(u.hostname)||u.port!=='18002'||u.pathname!=='/'||u.username||u.password||u.search||u.hash)throw Error('E2E aceita somente a API isolada local na porta 18002.');
module.exports=defineConfig({testDir:'./api/tests/e2e',timeout:90000,expect:{timeout:20000},workers:1,fullyParallel:false,retries:0,
 reporter:[['list'],['html',{open:'never',outputFolder:'test-results/html'}]],outputDir:'test-results/artifacts',
 use:{baseURL,headless:true,actionTimeout:15000,viewport:{width:1280,height:900},trace:'retain-on-failure',screenshot:'only-on-failure',launchOptions:{args:['--use-angle=swiftshader']}},
 projects:[{name:'chromium',use:{browserName:'chromium'}}]});
