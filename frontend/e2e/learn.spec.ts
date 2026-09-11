import { expect, test } from '@playwright/test'

test('learn home lists phases and marks phase 1 completed', async ({ page }) => {
  await page.goto('/learn')
  await expect(page.getByRole('heading', { name: 'ML learning plan' })).toBeVisible()
  await expect(page.locator('.sidebar')).toContainText('ML fundamentals')
  await expect(page.locator('.sidebar')).toContainText('COMPLETED')
})

test('phase 1 overview shows fundamentals and task links', async ({ page }) => {
  await page.goto('/learn/phase/1')
  await expect(page.getByRole('heading', { name: 'ML Fundamentals', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: /Task 1.1/ })).toBeVisible()
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

test('phase 2 task shows implementation not started', async ({ page }) => {
  await page.goto('/learn/phase/2/task/2.1')
  await expect(page.getByText('Implementation not started')).toBeVisible()
})
