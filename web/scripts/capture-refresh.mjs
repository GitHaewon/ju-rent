import { chromium, devices, expect } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'

const out = resolve(import.meta.dirname, '../../docs/design/screens')
await mkdir(out, { recursive: true })
const browser = await chromium.launch({
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true,
})

for (const [device, options] of [
  ['desktop', { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 }],
  ['iphone14', { ...devices['iPhone 14'], defaultBrowserType: undefined }],
]) {
  const context = await browser.newContext(options)
  const page = await context.newPage()
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto('http://127.0.0.1:5173/', { waitUntil: 'networkidle' })
  await expect(page.locator('.source-date')).toContainText(/실거래 기준: \d{4}년 \d{1,2}월 계약까지 · \d{1,2}월 \d{1,2}일 갱신/)
  await page.screenshot({ path: resolve(out, `${device}-refresh-judge.png`), fullPage: true, animations: 'disabled' })
  await page.getByRole('tab', { name: '예산으로 찾기' }).click()
  await expect(page.locator('.budget-card').first()).toBeVisible()
  await expect(page.locator('.source-date')).toContainText(/실거래 기준: \d{4}년 \d{1,2}월 계약까지 · \d{1,2}월 \d{1,2}일 갱신/)
  await page.screenshot({ path: resolve(out, `${device}-refresh-budget.png`), fullPage: true, animations: 'disabled' })
  await page.getByRole('tab', { name: '대학가 비교' }).click()
  await expect(page.locator('.trend-chart')).toBeVisible({ timeout: 60000 })
  if (await page.locator('.trend-chart .hint').count()) {
    await expect(page.locator('.trend-chart .hint')).toContainText(/\d{4}년은 1~\d{1,2}월 계약/)
  }
  await page.screenshot({ path: resolve(out, `${device}-refresh-compare.png`), fullPage: true, animations: 'disabled' })
  if (errors.length) throw new Error(errors.join('; '))
  await context.close()
}
await browser.close()
