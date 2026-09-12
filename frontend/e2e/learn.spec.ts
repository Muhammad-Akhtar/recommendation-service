import { expect, test } from '@playwright/test'

test('learn home lists phases and marks phase 1 completed', async ({ page }) => {
  await page.goto('/learn')
  await expect(page.getByRole('heading', { name: 'ML learning plan' })).toBeVisible()
  await expect(page.locator('.sidebar')).toContainText('ML fundamentals')
  await expect(page.locator('.sidebar')).toContainText('Data and features')
  await expect(page.locator('.sidebar')).toContainText('Logistic regression')
  await expect(page.locator('.sidebar')).toContainText('COMPLETED')
})

test('phase 1 overview shows fundamentals and task links', async ({ page }) => {
  await page.goto('/learn/phase/1')
  await expect(page.getByRole('heading', { name: 'ML Fundamentals', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: /Task 1.1/ })).toBeVisible()
})

test('phase 2 overview shows feature engineering and task links', async ({ page }) => {
  await page.goto('/learn/phase/2')
  await expect(
    page.getByRole('heading', { name: 'Data and Feature Engineering', exact: true }),
  ).toBeVisible()
  await expect(page.getByRole('link', { name: /Task 2.1/ })).toBeVisible()
})

test('task 1.1 shows spec and implementation source', async ({ page }) => {
  await page.goto('/learn/phase/1/task/1.1')
  await expect(page.getByText('y = 2x + 1')).toBeVisible()
  await expect(page.locator('.code-path')).toContainText(
    'task_1_1_what_is_a_model.py',
  )
  await expect(page.locator('.code-block')).toContainText('def predict')
})

test('phase 1 notes include leakage lesson', async ({ page }) => {
  await page.goto('/learn/phase/1/notes')
  await expect(page.getByRole('heading', { name: 'Notes' })).toBeVisible()
  await expect(page.locator('article')).toContainText('serving time')
})

test('phase 2 task 2.4 shows spec and point-in-time source', async ({ page }) => {
  await page.goto('/learn/phase/2/task/2.4')
  await expect(page.getByText('click_count_before', { exact: true })).toBeVisible()
  await expect(page.locator('.code-path')).toContainText('point_in_time.py')
  await expect(page.locator('.code-block')).toContainText('strictly before')
})

test('phase 2 notes include schema label lesson', async ({ page }) => {
  await page.goto('/learn/phase/2/notes')
  await expect(page.getByRole('heading', { name: 'Notes' })).toBeVisible()
  await expect(page.locator('article')).toContainText('clicked')
})

test('phase 3 task 3.1 shows sigmoid implementation', async ({ page }) => {
  await page.goto('/learn/phase/3/task/3.1')
  await expect(page.getByText('sigmoid(0) == 0.5')).toBeVisible()
  await expect(page.locator('.code-path')).toContainText('sigmoid.py')
  await expect(page.locator('.code-block')).toContainText('def sigmoid')
})

test('phase 4 notes include architecture fallback lesson', async ({ page }) => {
  await page.goto('/learn/phase/4/notes')
  await expect(page.getByRole('heading', { name: 'Notes' })).toBeVisible()
  await expect(page.locator('article')).toContainText('popular-fallback')
})

test('phase 5 task 5.3 shows ranking metrics source', async ({ page }) => {
  await page.goto('/learn/phase/5/task/5.3')
  await expect(page.getByText('ndcg_at_k', { exact: true })).toBeVisible()
  await expect(page.locator('.code-path')).toContainText('ranking_metrics.py')
  await expect(page.locator('.code-block')).toContainText('def ndcg_at_k')
})

test('phase 6 task 6.1 shows train/serve pipeline note', async ({ page }) => {
  await page.goto('/learn/phase/6/task/6.1')
  await expect(page.locator('.code-path')).toContainText('NOTES_pipeline.md')
  await expect(page.locator('.code-block')).toContainText('does not import')
})

test('phase 7 notes include serving vs training paths', async ({ page }) => {
  await page.goto('/learn/phase/7/notes')
  await expect(page.getByRole('heading', { name: 'Notes' })).toBeVisible()
  await expect(page.locator('article')).toContainText('click_count_before')
})

test('phase 8 experiment log lists v1 v2 and v3', async ({ page }) => {
  await page.goto('/learn/phase/8/task/8.1')
  await expect(page.locator('.code-path')).toContainText('EXPERIMENT_LOG.md')
  await expect(page.locator('.code-block')).toContainText('model_version')
})

test('phase 9 task shows implementation not started', async ({ page }) => {
  await page.goto('/learn/phase/9/task/9.1')
  await expect(page.getByText('Implementation not started')).toBeVisible()
})
