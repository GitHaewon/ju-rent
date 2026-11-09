import { chromium, devices, expect } from '@playwright/test'
import { existsSync } from 'node:fs'
import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '../..')
const out = resolve(root, 'docs/design/screens')
await mkdir(out, { recursive: true })

const windowsChrome = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const executablePath = process.env.CHROME_PATH ?? (existsSync(windowsChrome) ? windowsChrome : undefined)
const browser = await chromium.launch({ executablePath, headless: true })

async function capture(prefix, contextOptions) {
  const context = await browser.newContext(contextOptions)
  for (const scenario of ['default', 'monthly-45', 'insufficient']) {
    const page = await context.newPage()
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    await page.goto('http://127.0.0.1:5173/', { waitUntil: 'networkidle' })
    await page.locator('.verdict').waitFor()
    if (scenario === 'monthly-45') {
      await page.locator('#mon').fill('45')
      await page.waitForFunction(() => document.querySelector('.converted .big')?.textContent?.includes('47.08'))
      await page.locator('#mon').evaluate(element => element.blur())
    } else if (scenario === 'insufficient') {
      await page.getByRole('button', { name: '빌라', exact: true }).click()
      await page.locator('#area').focus()
      await page.locator('#area').press('End')
      await page.waitForFunction(() => document.querySelector('.verdict')?.textContent === '판단 보류')
      await page.locator('#area').evaluate(element => element.blur())
    }
    await page.waitForTimeout(700)
    await page.screenshot({ path: resolve(out, `${prefix}-${scenario}.png`), fullPage: true, animations: 'disabled' })
    if (errors.length) throw new Error(`${prefix}-${scenario}: ${errors.join('; ')}`)
    await page.close()
  }
  await context.close()
}

await capture('desktop', { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 })
await capture('iphone14', { ...devices['iPhone 14'], defaultBrowserType: undefined })

const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const page = await context.newPage()
await page.goto('http://127.0.0.1:5173/', { waitUntil: 'networkidle' })
const previousVerdict = await page.locator('.verdict').textContent()
await page.route('**/api/judge', async route => {
  if (JSON.parse(route.request().postData() ?? '{}').monthly === 45) {
    await new Promise(resolve => setTimeout(resolve, 900))
  }
  await route.continue()
})
await page.locator('#mon').fill('45')
await expect(page.locator('.panel-progress')).toBeVisible()
await expect(page.locator('.verdict')).toHaveText(previousVerdict ?? '')
await expect(page.locator('.verdict')).toHaveText('많이 비싼 편')
await page.locator('#mon').fill('0')
await expect(page.getByText('월세를 0보다 큰 정수로 입력해 주세요.')).toBeVisible()
await expect(page.locator('.verdict')).toHaveText('많이 비싼 편')
await context.close()
await browser.close()
