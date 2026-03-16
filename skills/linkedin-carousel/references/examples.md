# LinkedIn Carousel Examples

## Complete Example: HTML Slides to Carousel

This is the recommended approach for creating LinkedIn carousels programmatically.

```javascript
const { chromium } = require('playwright');
const { PDFDocument } = require('pdf-lib');
const fs = require('fs');

const WIDTH = 1080, HEIGHT = 1080;
const colors = { primary: '#277884', accent: '#FE4447', dark: '#1C2833', light: '#F4F6F6' };

const slides = [
  // Slide 1: Hook
  `<!DOCTYPE html><html><head><style>
  body { margin: 0; width: ${WIDTH}px; height: ${HEIGHT}px; font-family: Arial;
         display: flex; flex-direction: column; justify-content: center; align-items: center; background: white; }
  h1 { font-size: 72px; color: ${colors.dark}; margin: 0 0 20px; }
  p { font-size: 32px; color: ${colors.primary}; }
  </style></head><body>
    <h1>Skills.sh</h1>
    <p>npm for AI Agents</p>
  </body></html>`,
  
  // Slide 2: Problem  
  `<!DOCTYPE html><html><head><style>
  body { margin: 0; width: ${WIDTH}px; height: ${HEIGHT}px; font-family: Arial; background: white; }
  .header { background: ${colors.primary}; padding: 40px; }
  h2 { color: white; font-size: 48px; margin: 0; }
  .content { padding: 50px; }
  p { font-size: 28px; color: ${colors.dark}; line-height: 1.6; }
  </style></head><body>
    <div class="header"><h2>The Problem</h2></div>
    <div class="content">
      <p>Building with AI agents means recreating the same workflows over and over.</p>
    </div>
  </body></html>`,
  
  // Slide 3: Solution
  `<!DOCTYPE html><html><head><style>
  body { margin: 0; width: ${WIDTH}px; height: ${HEIGHT}px; font-family: Arial; background: ${colors.primary};
         display: flex; flex-direction: column; justify-content: center; align-items: center; }
  h2 { color: white; font-size: 48px; margin-bottom: 40px; }
  .command { background: ${colors.dark}; padding: 20px 40px; border-radius: 10px; 
             font-family: monospace; font-size: 28px; color: #4AE88C; }
  </style></head><body>
    <h2>The Solution</h2>
    <div class="command">npx skills add owner/repo</div>
  </body></html>`,
  
  // Slide 4: CTA
  `<!DOCTYPE html><html><head><style>
  body { margin: 0; width: ${WIDTH}px; height: ${HEIGHT}px; font-family: Arial; background: ${colors.dark};
         display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; }
  h2 { color: white; font-size: 52px; margin-bottom: 30px; }
  .url { font-size: 36px; color: ${colors.accent}; font-weight: bold; }
  </style></head><body>
    <h2>Get Started Today</h2>
    <p class="url">skills.sh</p>
  </body></html>`,
];

async function createCarousel(outputPath = 'carousel.pdf') {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.setViewportSize({ width: WIDTH, height: HEIGHT });
  
  const pdfDoc = await PDFDocument.create();
  for (const html of slides) {
    await page.setContent(html, { waitUntil: 'networkidle' });
    const img = await pdfDoc.embedPng(await page.screenshot({ type: 'png' }));
    const p = pdfDoc.addPage([WIDTH * 0.75, HEIGHT * 0.75]);
    p.drawImage(img, { x: 0, y: 0, width: p.getWidth(), height: p.getHeight() });
  }
  await browser.close();
  fs.writeFileSync(outputPath, await pdfDoc.save());
  console.log(`Carousel created: ${outputPath}`);
}

createCarousel();
```

## Slide Templates

### Hook Slide Template

```html
<!DOCTYPE html><html><head><style>
body { 
  margin: 0; width: 1080px; height: 1080px; font-family: Arial;
  display: flex; flex-direction: column; justify-content: center; 
  align-items: center; text-align: center;
  background: linear-gradient(135deg, #1C2833 0%, #2E4053 100%);
}
.tag { background: #FE4447; color: white; padding: 12px 28px; border-radius: 30px; 
       font-size: 22px; font-weight: bold; margin-bottom: 40px; }
h1 { font-size: 72px; color: white; margin: 0 0 20px; }
p { font-size: 32px; color: #277884; }
</style></head><body>
  <div class="tag">🚀 YOUR TAG</div>
  <h1>Main Title</h1>
  <p>Subtitle or tagline</p>
</body></html>
```

### Content Slide Template

```html
<!DOCTYPE html><html><head><style>
body { margin: 0; width: 1080px; height: 1080px; font-family: Arial; background: white; }
.header { background: #277884; padding: 50px 60px; }
h2 { color: white; font-size: 48px; margin: 0; }
.content { padding: 60px; }
.item { display: flex; align-items: flex-start; margin-bottom: 30px; }
.icon { font-size: 32px; margin-right: 20px; }
.text { font-size: 28px; color: #1C2833; line-height: 1.4; }
</style></head><body>
  <div class="header"><h2>Section Title</h2></div>
  <div class="content">
    <div class="item"><span class="icon">✓</span><span class="text">Point one</span></div>
    <div class="item"><span class="icon">✓</span><span class="text">Point two</span></div>
    <div class="item"><span class="icon">✓</span><span class="text">Point three</span></div>
  </div>
</body></html>
```

### CTA Slide Template

```html
<!DOCTYPE html><html><head><style>
body { 
  margin: 0; width: 1080px; height: 1080px; font-family: Arial; 
  background: #277884;
  display: flex; flex-direction: column; justify-content: center; 
  align-items: center; text-align: center; padding: 60px;
}
h2 { font-size: 52px; color: white; margin-bottom: 40px; }
.url { font-size: 36px; color: white; font-weight: bold; margin-bottom: 40px; }
.question { font-size: 28px; color: rgba(255,255,255,0.9); }
</style></head><body>
  <h2>Get Started Today</h2>
  <p class="url">🌐 yoursite.com</p>
  <p class="question">What will you create?</p>
</body></html>
```

## CLI Usage Examples

### Convert image folder to carousel

```bash
# Square format (default)
node scripts/pptx-to-carousel.js ./my-slides/ output.pdf

# Vertical format
node scripts/pptx-to-carousel.js ./my-slides/ output.pdf --format vertical
```

### Convert PPTX to carousel (requires LibreOffice)

```bash
node scripts/pptx-to-carousel.js presentation.pptx carousel.pdf
```

## API Usage

```javascript
const { convertPptxToCarousel, imagesToCarousel, FORMATS } = require('./scripts/pptx-to-carousel');

// Convert images
await imagesToCarousel('./slides/', 'output.pdf', 'square');

// Convert PPTX
await convertPptxToCarousel('presentation.pptx', 'output.pdf', 'vertical');

// Access format constants
console.log(FORMATS.square);   // { width: 1080, height: 1080, safeZone: 960 }
console.log(FORMATS.vertical); // { width: 1080, height: 1350, safeZone: 960 }
```
