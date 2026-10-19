const {test, expect} = require('@playwright/test');

test('página pública mostra a prontidão real da API', async ({page}) => {
  await page.goto('/static/status.html');
  await expect(page.getByRole('heading', {name: 'API respondendo'})).toBeVisible();
  await expect(page.getByText('Nenhuma janela de manutenção está programada.')).toBeVisible();
});

test('aviso programado aparece como texto e inclui a janela', async ({page}) => {
  await page.route('**/api/v1/health/manutencao', route => route.fulfill({json: {
    situacao: 'PROGRAMADA', consultado_em: '2026-10-18T12:00:00Z',
    inicio_em: '2026-10-20T13:00:00Z', fim_em: '2026-10-20T15:00:00Z',
    aviso: 'Atualização <b>planejada</b>'
  }}));
  await page.goto('/static/status.html');
  await expect(page.getByRole('heading', {name: 'Manutenção programada'})).toBeVisible();
  await expect(page.getByText('Atualização <b>planejada</b>')).toBeVisible();
  await expect(page.locator('section b')).toHaveCount(0);
  await expect(page.getByText(/Janela:/)).toBeVisible();
});

test('falha de prontidão não aparece como API pronta', async ({page}) => {
  await page.route('**/api/v1/health/readiness', route => route.fulfill({status: 503, json: {detail: 'Indisponível'}}));
  await page.goto('/static/status.html');
  await expect(page.getByRole('heading', {name: 'Não foi possível confirmar a prontidão da API'})).toBeVisible();
  await expect(page.getByText('API pronta', {exact: true})).toHaveCount(0);
});
