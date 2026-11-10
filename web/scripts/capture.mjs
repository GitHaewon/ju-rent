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
    await expect(page.getByRole('group', { name: '집 종류' }).getByRole('button')).toHaveCount(3)
    await expect(page.locator('.context')).toContainText('원룸·투룸·빌라')
    await expect(page.locator('.negotiation-hint')).toContainText("'보통'이 돼요")
    await expect(page.getByText("건물 이름에 '오피스텔'이 있으면 오피스텔, 아파트라면 아파트, 나머지는 원룸·투룸·빌라를 고르세요.")).toBeVisible()
    if (scenario === 'monthly-45') {
      await page.locator('#mon').fill('45')
      await page.waitForFunction(() => document.querySelector('.converted .big')?.textContent?.includes('47.08'))
      await page.locator('#mon').evaluate(element => element.blur())
    } else if (scenario === 'insufficient') {
      await page.getByRole('button', { name: '아파트', exact: true }).click()
      await page.locator('#area').focus()
      await page.locator('#area').press('End')
      for (let i = 0; i < 9; i++) await page.locator('#area').press('ArrowLeft')
      await expect(page.locator('#area')).toHaveValue('127.5')
      await page.waitForFunction(() => document.querySelector('.verdict')?.textContent === '판단 보류')
      await expect(page.locator('.dist-empty')).toHaveText('비슷한 거래가 적어 분포를 그리지 않았어요')
      await expect(page.locator('.dist .bars, .dist .track, .dist .pin')).toHaveCount(0)
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
await page.locator('#mon').fill('1000')
await expect(page.locator('.pin-high .tag')).toHaveText('비교한 거래보다 비싸요')
await expect(page.locator('.axis span')).toHaveCount(5)
await page.locator('#dep').fill('0')
await page.locator('#mon').fill('1')
await expect(page.locator('.pin-low .tag')).toHaveText('비교한 거래보다 싸요')
const housingRequests = []
page.on('request', request => {
  if (request.url().endsWith('/api/judge') && request.postData()) housingRequests.push(JSON.parse(request.postData()).housing_type)
})
await page.getByRole('button', { name: '오피스텔', exact: true }).click()
await expect(page.locator('.context')).toContainText('오피스텔')
await page.getByRole('button', { name: '원룸·투룸·빌라', exact: true }).click()
await expect(page.locator('.context')).toContainText('원룸·투룸·빌라')
if (!housingRequests.includes('officetel') || !housingRequests.includes('oneroom')) {
  throw new Error('Housing choice was not sent using its API code')
}
await page.getByRole('button', { name: '아파트', exact: true }).click()
await expect(page.locator('#area')).toHaveAttribute('min', '40')
await expect(page.locator('#area')).toHaveAttribute('max', '132')
await expect(page.locator('#area')).toHaveValue('40')
await expect(page.getByText('보증금이 커서 환산율에 따라 결과가 크게 달라져요.')).toBeVisible()
await page.locator('#area').focus()
await page.locator('#area').press('End')
await expect(page.locator('#area')).toHaveValue('132')
await page.getByRole('button', { name: '원룸·투룸·빌라', exact: true }).click()
await expect(page.locator('#area')).toHaveAttribute('min', '15')
await expect(page.locator('#area')).toHaveAttribute('max', '45')
await expect(page.locator('#area')).toHaveValue('45')
await page.getByRole('button', { name: '오피스텔', exact: true }).click()
await page.locator('#area').press('Home')
await expect(page.locator('.verdict')).toHaveText('판단 보류')
await expect(page.locator('.verdict-line')).toContainText('한 건물이에요')
await expect(page.locator('.negotiation-hint')).toHaveCount(0)
const yearToggle = page.getByRole('checkbox', { name: '건축년도 입력 (선택)' })
await yearToggle.focus()
await yearToggle.press('Space')
await expect(yearToggle).toBeChecked()
await expect(page.locator('#year')).toBeVisible()
const outline = await page.locator('.switch-track').evaluate(element => getComputedStyle(element).outlineStyle)
if (outline === 'none') throw new Error('Keyboard focus indicator is missing from the year switch')
await context.close()
await browser.close()
