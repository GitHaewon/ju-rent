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
  for (const campus of ['효자동권', '전북대권']) {
    const page = await context.newPage()
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    await page.goto('http://127.0.0.1:5174/', { waitUntil: 'networkidle' })
    await page.getByRole('tab', { name: '예산으로 찾기' }).click()
    await page.getByRole('group', { name: '예산 대학가' }).getByRole('button', { name: campus }).click()
    await page.getByRole('group', { name: '우선순위' }).getByRole('button', { name: '통학 가깝게' }).click()
    await expect(page.locator('.budget-card').first()).toBeVisible()
    await expect(page.locator('.budget-summary')).toContainText(campus)
    await page.screenshot({ path: resolve(out, `${device}-commute-budget-${campus}.png`),
      fullPage: true, animations: 'disabled' })
    await page.getByRole('button', { name: '더 보기' }).click()
    const neighborhood = page.locator('.budget-card').filter({ has: page.locator('.commute-badge', { hasText: '버스 정류장' }) }).first()
    const chosenDong = await neighborhood.locator('.budget-card-head strong').textContent()
    await neighborhood.click()
    await expect(page.locator('#judge-dong')).toHaveValue(chosenDong ?? '')
    if (errors.length) throw new Error(errors.join('; '))
    await page.close()
  }
  const judge = await context.newPage()
  const errors = []
  judge.on('pageerror', error => errors.push(error.message))
  await judge.goto('http://127.0.0.1:5174/', { waitUntil: 'networkidle' })
  await judge.locator('#judge-dong').selectOption('서신동')
  await expect(judge.locator('.hero .context')).toContainText('서신동')
  await expect(judge.locator('.verdict')).toBeVisible()
  await judge.screenshot({ path: resolve(out, `${device}-commute-judge-서신동.png`),
    fullPage: true, animations: 'disabled' })
  if (errors.length) throw new Error(errors.join('; '))
  await judge.close()
  const compare = await context.newPage()
  await compare.goto('http://127.0.0.1:5174/', { waitUntil: 'networkidle' })
  await compare.getByRole('tab', { name: '대학가 비교' }).click()
  await expect(compare.locator('.commute-neighborhoods').first()).toBeVisible()
  await compare.screenshot({ path: resolve(out, `${device}-commute-compare.png`),
    fullPage: true, animations: 'disabled' })
  await compare.close()
  await context.close()
}
await browser.close()
