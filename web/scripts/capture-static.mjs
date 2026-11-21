import { chromium, devices, expect } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'

const out = resolve(import.meta.dirname, '../../docs/design/screens')
await mkdir(out, { recursive: true })
const browser = await chromium.launch({
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true,
})
const url = 'http://127.0.0.1:4173/ju-rent/'
for (const [name, options] of [
  ['desktop', { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 }],
  ['iphone14', { ...devices['iPhone 14'], defaultBrowserType: undefined }],
]) {
  const context = await browser.newContext(options)
  const page = await context.newPage()
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto(url, { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('계산 준비 중이에요. 처음 한 번만 10초쯤 걸려요')).toBeVisible()
  await page.screenshot({ path: resolve(out, `static_${name}_loading.png`), fullPage: true, animations: 'disabled' })
  await expect(page.locator('.verdict')).toBeVisible({ timeout: 120000 })
  await expect(page.getByText('공개 사이트에서는 기본 설명을 보여드려요')).toBeVisible()
  await page.screenshot({ path: resolve(out, `static_${name}_judge.png`), fullPage: true, animations: 'disabled' })
  await page.getByRole('tab', { name: '예산으로 찾기' }).click()
  await expect(page.locator('.budget-card').first()).toBeVisible({ timeout: 60000 })
  await page.screenshot({ path: resolve(out, `static_${name}_budget.png`), fullPage: true, animations: 'disabled' })
  await page.getByRole('tab', { name: '대학가 비교' }).click()
  await expect(page.locator('.trend-chart')).toBeVisible({ timeout: 60000 })
  await page.screenshot({ path: resolve(out, `static_${name}_compare.png`), fullPage: true, animations: 'disabled' })
  if (errors.length) throw new Error(errors.join('; '))
  await context.close()

  const failureContext = await browser.newContext(options)
  await failureContext.route('**/assets/pyWorker-*.js', route => route.abort())
  const failurePage = await failureContext.newPage()
  await failurePage.goto(url, { waitUntil: 'domcontentloaded' })
  await expect(failurePage.locator('#result')).toContainText('계산 도구를 불러오지 못했어요. 인터넷 연결을 확인하고 새로 고침해 주세요', { timeout: 30000 })
  await failurePage.screenshot({ path: resolve(out, `static_${name}_failure.png`), fullPage: true, animations: 'disabled' })
  await failureContext.close()
}
await browser.close()
