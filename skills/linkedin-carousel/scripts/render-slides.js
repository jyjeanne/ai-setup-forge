/**
 * render-slides.js
 * Renders PowerPoint slides to PNG images using Playwright
 * This works by re-generating slides from PptxGenJS presentations
 * 
 * Usage: node render-slides.js <slide-script.js> <output-folder>
 */

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

async function renderSlidesToImages(htmlSlides, outputDir, width = 1080, height = 1080) {
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.setViewportSize({ width, height });

  const images = [];

  for (let i = 0; i < htmlSlides.length; i++) {
    const html = htmlSlides[i];
    const imagePath = path.join(outputDir, `slide_${String(i + 1).padStart(3, '0')}.png`);
    
    await page.setContent(html, { waitUntil: 'networkidle' });
    await page.screenshot({ path: imagePath, type: 'png' });
    images.push(imagePath);
    
    console.log(`Rendered slide ${i + 1}/${htmlSlides.length}`);
  }

  await browser.close();
  return images;
}

module.exports = { renderSlidesToImages };
