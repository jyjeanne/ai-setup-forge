/**
 * pptx-to-carousel.js
 * Converts PowerPoint presentations to LinkedIn carousel PDFs
 * 
 * Usage: node pptx-to-carousel.js <input.pptx> [output.pdf] [--format square|vertical]
 * 
 * Dependencies: sharp, pdf-lib, adm-zip
 * 
 * IMPORTANT: This script converts PNG/JPEG slide images to carousel PDF.
 * For best results, export slides as images first, OR provide a folder of images.
 */

const fs = require('fs');
const path = require('path');
const sharp = require('sharp');
const { PDFDocument } = require('pdf-lib');
const AdmZip = require('adm-zip');

// LinkedIn carousel dimensions
const FORMATS = {
  square: { width: 1080, height: 1080, safeZone: 960 },
  vertical: { width: 1080, height: 1350, safeZone: 960 }
};

/**
 * Get slide count from PPTX file
 */
function getSlideCount(pptxPath) {
  const zip = new AdmZip(pptxPath);
  const slideEntries = zip.getEntries().filter(e => 
    e.entryName.match(/ppt\/slides\/slide\d+\.xml$/)
  );
  return slideEntries.length;
}

/**
 * Convert PPTX to images using LibreOffice (best quality)
 */
async function convertWithLibreOffice(pptxPath, outputDir, format) {
  const { execSync } = require('child_process');
  const absolutePptx = path.resolve(pptxPath);
  const baseName = path.basename(pptxPath, '.pptx');
  
  // First convert PPTX to PDF
  console.log('Converting PPTX to PDF via LibreOffice...');
  execSync(`soffice --headless --convert-to pdf --outdir "${outputDir}" "${absolutePptx}"`, {
    timeout: 120000,
    stdio: 'pipe'
  });
  
  const pdfPath = path.join(outputDir, `${baseName}.pdf`);
  if (!fs.existsSync(pdfPath)) {
    throw new Error('LibreOffice PDF conversion failed');
  }
  
  // Then convert PDF pages to images using pdftoppm (poppler-utils) or similar
  console.log('Converting PDF pages to images...');
  
  // Try pdftoppm first
  try {
    execSync(`pdftoppm -png -r 150 "${pdfPath}" "${path.join(outputDir, 'slide')}"`, {
      timeout: 120000,
      stdio: 'pipe'
    });
  } catch (e) {
    // Try magick/convert as fallback
    try {
      execSync(`magick -density 150 "${pdfPath}" "${path.join(outputDir, 'slide-%03d.png')}"`, {
        timeout: 120000,
        stdio: 'pipe'
      });
    } catch (e2) {
      throw new Error('Neither pdftoppm nor ImageMagick available for PDF to image conversion');
    }
  }
  
  // Collect generated images
  const images = fs.readdirSync(outputDir)
    .filter(f => f.startsWith('slide') && f.endsWith('.png'))
    .sort()
    .map(f => path.join(outputDir, f));
  
  return images;
}

/**
 * Extract images already embedded in PPTX (if presentation was made with images)
 */
function extractEmbeddedImages(pptxPath, outputDir) {
  const zip = new AdmZip(pptxPath);
  const mediaEntries = zip.getEntries().filter(e => 
    e.entryName.startsWith('ppt/media/') && 
    (e.entryName.endsWith('.png') || e.entryName.endsWith('.jpg') || e.entryName.endsWith('.jpeg'))
  );
  
  const images = [];
  for (const entry of mediaEntries) {
    const imagePath = path.join(outputDir, path.basename(entry.entryName));
    fs.writeFileSync(imagePath, entry.getData());
    images.push(imagePath);
  }
  
  return images.sort();
}

/**
 * Resize images to LinkedIn carousel dimensions
 */
async function resizeForLinkedIn(imagePaths, outputDir, format) {
  const { width, height } = format;
  const resizedImages = [];
  
  for (let i = 0; i < imagePaths.length; i++) {
    const inputPath = imagePaths[i];
    const outputPath = path.join(outputDir, `carousel_${String(i + 1).padStart(3, '0')}.png`);
    
    await sharp(inputPath)
      .resize(width, height, {
        fit: 'contain',
        background: { r: 255, g: 255, b: 255, alpha: 1 }
      })
      .png()
      .toFile(outputPath);
    
    resizedImages.push(outputPath);
    console.log(`Resized slide ${i + 1}/${imagePaths.length} to ${width}x${height}`);
  }
  
  return resizedImages;
}

/**
 * Combine images into a multi-page PDF
 */
async function imagesToPdf(imagePaths, outputPath, format) {
  const { width, height } = format;
  
  // Validate slide count
  if (imagePaths.length < 2) {
    throw new Error('LinkedIn requires minimum 2 slides');
  }
  if (imagePaths.length > 20) {
    throw new Error('LinkedIn allows maximum 20 slides');
  }
  
  const pdfDoc = await PDFDocument.create();
  
  for (let i = 0; i < imagePaths.length; i++) {
    const imagePath = imagePaths[i];
    const imageBuffer = fs.readFileSync(imagePath);
    
    // Embed the image (handle both PNG and JPEG)
    const ext = path.extname(imagePath).toLowerCase();
    const image = (ext === '.jpg' || ext === '.jpeg')
      ? await pdfDoc.embedJpg(imageBuffer)
      : await pdfDoc.embedPng(imageBuffer);
    
    // Add a page with LinkedIn dimensions (convert px to points: 72 points = 1 inch, 96 px = 1 inch)
    // So: points = px * 72 / 96 = px * 0.75
    const pageWidth = width * 0.75;
    const pageHeight = height * 0.75;
    
    const page = pdfDoc.addPage([pageWidth, pageHeight]);
    
    // Draw image to fill the page
    page.drawImage(image, {
      x: 0,
      y: 0,
      width: pageWidth,
      height: pageHeight
    });
    
    console.log(`Added slide ${i + 1}/${imagePaths.length} to PDF`);
  }
  
  const pdfBytes = await pdfDoc.save();
  fs.writeFileSync(outputPath, pdfBytes);
  
  console.log(`\nCarousel PDF saved to: ${outputPath}`);
  console.log(`Format: ${format.width}x${format.height} (${Object.keys(FORMATS).find(k => FORMATS[k] === format)})`);
  console.log(`Slides: ${imagePaths.length}`);
  
  return outputPath;
}

/**
 * Convert images from a folder to carousel PDF
 */
async function imagesToCarousel(imageDir, outputPath, formatName = 'square') {
  const format = FORMATS[formatName];
  if (!format) {
    throw new Error(`Invalid format: ${formatName}. Use 'square' or 'vertical'`);
  }

  // Find all images in directory
  const imageExtensions = ['.png', '.jpg', '.jpeg', '.webp'];
  const images = fs.readdirSync(imageDir)
    .filter(f => imageExtensions.some(ext => f.toLowerCase().endsWith(ext)))
    .sort()
    .map(f => path.join(imageDir, f));

  if (images.length === 0) {
    throw new Error(`No images found in ${imageDir}`);
  }

  console.log(`Found ${images.length} images`);

  // Create temp directory
  const tempDir = path.join(path.dirname(outputPath), '.carousel_temp');
  if (!fs.existsSync(tempDir)) {
    fs.mkdirSync(tempDir, { recursive: true });
  }

  try {
    // Resize images
    const resizedImages = await resizeForLinkedIn(images, tempDir, format);
    
    // Create PDF
    await imagesToPdf(resizedImages, outputPath, format);
    
    return { success: true, slides: images.length, output: outputPath };
  } finally {
    // Cleanup
    if (fs.existsSync(tempDir)) {
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  }
}

/**
 * Main conversion function - converts PPTX to carousel PDF
 */
async function convertPptxToCarousel(pptxPath, outputPath, formatName = 'square') {
  const format = FORMATS[formatName];
  if (!format) {
    throw new Error(`Invalid format: ${formatName}. Use 'square' or 'vertical'`);
  }
  
  console.log(`\nConverting: ${pptxPath}`);
  console.log(`Format: ${formatName} (${format.width}x${format.height})`);
  console.log(`Output: ${outputPath}\n`);
  
  const slideCount = getSlideCount(pptxPath);
  console.log(`Found ${slideCount} slides in presentation`);
  
  // Create temp directory
  const tempDir = path.join(path.dirname(outputPath), '.carousel_temp');
  if (!fs.existsSync(tempDir)) {
    fs.mkdirSync(tempDir, { recursive: true });
  }
  
  try {
    let images = [];
    
    // Try LibreOffice first (best quality)
    try {
      images = await convertWithLibreOffice(pptxPath, tempDir, format);
      console.log(`LibreOffice extracted ${images.length} slide images`);
    } catch (err) {
      console.log(`LibreOffice conversion failed: ${err.message}`);
      
      // Fallback: Extract embedded images from PPTX
      console.log('Trying to extract embedded images...');
      images = extractEmbeddedImages(pptxPath, tempDir);
      
      if (images.length === 0) {
        throw new Error(
          'Could not convert PPTX. Please either:\n' +
          '1. Install LibreOffice for automatic conversion\n' +
          '2. Export slides as PNG images manually and use: node pptx-to-carousel.js <image-folder> output.pdf'
        );
      }
      console.log(`Extracted ${images.length} embedded images`);
    }
    
    // Resize images for LinkedIn
    const resizedImages = await resizeForLinkedIn(images, tempDir, format);
    
    // Combine into PDF
    await imagesToPdf(resizedImages, outputPath, format);
    
    return { success: true, slides: resizedImages.length, output: outputPath };
    
  } finally {
    // Cleanup temp directory
    if (fs.existsSync(tempDir)) {
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  }
}

// CLI interface
if (require.main === module) {
  const args = process.argv.slice(2);
  
  if (args.length === 0 || args.includes('--help') || args.includes('-h')) {
    console.log(`
LinkedIn Carousel Converter
===========================

Converts PowerPoint presentations or image folders to LinkedIn carousel PDFs.

Usage:
  node pptx-to-carousel.js <input.pptx> [output.pdf] [options]
  node pptx-to-carousel.js <image-folder> [output.pdf] [options]

Options:
  --format <type>   Output format: 'square' (1080x1080) or 'vertical' (1080x1350)
                    Default: square
  --help, -h        Show this help message

Examples:
  node pptx-to-carousel.js presentation.pptx
  node pptx-to-carousel.js presentation.pptx carousel.pdf --format vertical
  node pptx-to-carousel.js ./slide-images/ carousel.pdf --format square

LinkedIn Carousel Requirements:
  - Square: 1080x1080 pixels (recommended)
  - Vertical: 1080x1350 pixels
  - Safe zone: 960x960 pixels (content may be cropped outside this)
  - Max slides: 20
  - Format: Multi-page PDF

Note: For PPTX conversion, LibreOffice must be installed for best results.
      Alternatively, export slides as PNG images and provide the folder path.
`);
    process.exit(0);
  }
  
  const inputPath = args[0];
  let outputPath = args[1];
  let formatName = 'square';
  
  // Parse format flag
  const formatIndex = args.indexOf('--format');
  if (formatIndex !== -1 && args[formatIndex + 1]) {
    formatName = args[formatIndex + 1].toLowerCase();
    // If output path was the format flag, clear it
    if (outputPath === '--format') {
      outputPath = null;
    }
  }
  
  // Determine if input is a directory (images) or file (pptx)
  const isDirectory = fs.existsSync(inputPath) && fs.statSync(inputPath).isDirectory();
  
  // Default output path
  if (!outputPath || outputPath.startsWith('--')) {
    if (isDirectory) {
      outputPath = path.join(inputPath, 'carousel.pdf');
    } else {
      const baseName = path.basename(inputPath, '.pptx');
      outputPath = path.join(path.dirname(inputPath), `${baseName}-carousel.pdf`);
    }
  }
  
  // Run conversion
  const convertFn = isDirectory ? imagesToCarousel : convertPptxToCarousel;
  
  convertFn(inputPath, outputPath, formatName)
    .then(result => {
      console.log('\n✓ Conversion complete!');
      process.exit(0);
    })
    .catch(err => {
      console.error('\n✗ Error:', err.message);
      process.exit(1);
    });
}

module.exports = { convertPptxToCarousel, imagesToCarousel, FORMATS };
