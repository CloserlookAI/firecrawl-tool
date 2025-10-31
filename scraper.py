import os
import re
import base64
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Optional, Tuple
import asyncio

# Install required packages in the virtual environment before running this script.
# Expected environment variables:
#   FIRECRAWL_API_KEY - API key for Firecrawl
#   OPENAI_API_KEY - API key for OpenAI (optional, for image analysis)

try:
    from firecrawl import V1FirecrawlApp
except ImportError:
    raise ImportError(
        "firecrawl-py package not installed. Run pip install firecrawl-py")

# Optional dependencies
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("[!] OpenAI not installed. Image analysis will be disabled.")
    print("    To enable: pip install openai")

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("[!] Playwright not installed. Image/SVG extraction will be disabled.")
    print("    To enable: pip install playwright && playwright install chromium")

try:
    import fitz  # PyMuPDF
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print("[!] PyMuPDF not installed. PDF conversion will be disabled.")
    print("    To enable: pip install PyMuPDF")

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("[!] requests not installed. Direct downloads will be disabled.")
    print("    To enable: pip install requests")

# Initialize clients
load_dotenv()

firecrawl_api_key = os.getenv("FIRECRAWL_API_KEY")
if not firecrawl_api_key:
    raise EnvironmentError("FIRECRAWL_API_KEY not set in environment")
app = V1FirecrawlApp(api_key=firecrawl_api_key)

# Initialize OpenAI client if available
openai_client = None
if OPENAI_AVAILABLE:
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if openai_api_key:
        openai_client = OpenAI(api_key=openai_api_key)
    else:
        print("[!] OPENAI_API_KEY not set - image analysis will be disabled")
        OPENAI_AVAILABLE = False

DATA_DIR = Path.cwd() / "data"


def _sanitize_company_name(company_name: str) -> str:
    return company_name.strip().replace(' ', '_').replace('/', '_').lower()


def _ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def _ensure_company_dir(company_name: str) -> Path:
    """Create a directory for the company's files."""
    safe_name = _sanitize_company_name(company_name)
    company_dir = DATA_DIR / safe_name
    company_dir.mkdir(parents=True, exist_ok=True)
    return company_dir


def _has_pipeline_indicators(markdown: str) -> bool:
    """Check if markdown contains typical pipeline/program indicators."""
    indicators = [
        'phase', 'clinical', 'study', 'trial', 'program', 'candidate',
        'indication', 'therapeutic', 'mechanism', 'target', 'pipeline'
    ]
    markdown_lower = markdown.lower()
    # Check if at least 3 indicators are present
    found = sum(1 for indicator in indicators if indicator in markdown_lower)
    return found >= 3


def analyze_image_with_vision(image_path: Path, company_name: str) -> Optional[str]:
    """
    Analyze an image using GPT-4 Vision and return markdown description.

    Args:
        image_path: Path to the image file
        company_name: Company name for context

    Returns:
        str: Markdown formatted description of the image
    """
    if not OPENAI_AVAILABLE or not openai_client:
        print("  [!] OpenAI not available - skipping vision analysis")
        return None

    try:
        print(f"  [*] Analyzing image with GPT-4 Vision...")

        # Read and encode image
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')

        # Determine mime type
        ext = image_path.suffix.lower()
        mime_type_map = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        mime_type = mime_type_map.get(ext, 'image/png')

        # Simple prompt for image analysis
        prompt = f"""Analyze this pharmaceutical pipeline image for {company_name}.

Extract and describe all visible information in clean markdown format.

Include:
- Company name as main heading (# {company_name})
- Programs/products as subheadings (##)
- Key details: indication, phase, mechanism, targets, partners
- Any tables, charts, or timelines
- Development stages and status

Format your response as well-structured markdown. Be comprehensive but concise.
Only include information that is clearly visible in the image."""

        # Call GPT-4 Vision
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_data}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            temperature=0,
            max_tokens=4096
        )

        markdown_content = response.choices[0].message.content
        print(f"  [OK] Vision analysis complete ({len(markdown_content)} chars)")
        return markdown_content

    except Exception as e:
        print(f"  [X] Vision analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def is_pdf_url(url: str) -> bool:
    """Check if URL points to a PDF file by extension or Content-Type."""
    url_lower = url.lower()

    # First check URL extension
    if url_lower.endswith('.pdf') or '.pdf?' in url_lower or '.pdf&' in url_lower:
        return True

    # If no .pdf extension, make a HEAD request to check Content-Type
    if not REQUESTS_AVAILABLE:
        return False

    try:
        print(f"  [*] Checking Content-Type for: {url[:80]}...")
        response = requests.head(url, timeout=10, allow_redirects=True, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        content_type = response.headers.get('content-type', '').lower()

        if 'pdf' in content_type or 'application/pdf' in content_type:
            print(f"  [OK] Detected PDF via Content-Type: {content_type}")
            return True
    except Exception as e:
        print(f"  [!] Could not check Content-Type: {e}")

    return False


def is_image_url(url: str) -> bool:
    """Check if URL points to an image file."""
    url_lower = url.lower()
    image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp', '.tiff']

    for ext in image_extensions:
        if url_lower.endswith(ext) or f'{ext}?' in url_lower or f'{ext}&' in url_lower:
            return True
    return False


def download_pdf(url: str, company_name: str) -> Optional[Path]:
    """Download PDF from URL and save to company directory."""
    if not REQUESTS_AVAILABLE:
        print("  [X] requests library not available - cannot download PDF")
        return None

    try:
        print(f"  [*] Downloading PDF from {url[:80]}...")

        company_dir = _ensure_company_dir(company_name)
        safe_name = _sanitize_company_name(company_name)
        pdf_path = company_dir / f"{safe_name}_pipeline.pdf"

        # Download with timeout
        response = requests.get(url, timeout=60, stream=True)
        response.raise_for_status()

        # Verify it's actually a PDF
        content_type = response.headers.get('content-type', '').lower()
        if 'pdf' not in content_type:
            print(f"  [!] Warning: Content-Type is '{content_type}', expected PDF")

        # Save to file
        with open(pdf_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        file_size = pdf_path.stat().st_size / (1024 * 1024)  # MB
        print(f"  [OK] PDF downloaded: {pdf_path.name} ({file_size:.2f} MB)")
        return pdf_path

    except Exception as e:
        print(f"  [X] Failed to download PDF: {e}")
        return None


def pdf_to_images(pdf_path: Path, company_name: str) -> List[Path]:
    """Convert PDF pages to PNG images."""
    if not PDF_AVAILABLE:
        print("  [X] PyMuPDF not available - cannot convert PDF to images")
        return []

    try:
        print(f"  [*] Converting PDF to images...")

        company_dir = _ensure_company_dir(company_name)
        safe_name = _sanitize_company_name(company_name)

        # Open PDF
        doc = fitz.open(pdf_path)
        image_paths = []

        print(f"      PDF has {len(doc)} page(s)")

        # Convert each page to image
        for page_num in range(len(doc)):
            page = doc[page_num]

            # Render page to pixmap (image) at 2x resolution for better quality
            mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for better quality
            pix = page.get_pixmap(matrix=mat)

            # Save as PNG
            image_path = company_dir / f"{safe_name}_page_{page_num + 1}.png"
            pix.save(str(image_path))

            image_paths.append(image_path)
            print(f"      [OK] Page {page_num + 1}/{len(doc)} → {image_path.name}")

        doc.close()
        print(f"  [OK] Converted {len(image_paths)} page(s) to images")
        return image_paths

    except Exception as e:
        print(f"  [X] Failed to convert PDF to images: {e}")
        import traceback
        traceback.print_exc()
        return []


def download_regular_image(url: str, output_path: Path) -> bool:
    """Download non-SVG images directly."""
    if not REQUESTS_AVAILABLE:
        print("  [X] requests library not available - cannot download image")
        return False

    try:
        print(f"  [*] Downloading {url.split('/')[-1]}...")

        response = requests.get(url, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                f.write(response.content)
            print(f"  [OK] Downloaded: {output_path.name}")
            return True
        else:
            print(f"  [X] Download failed: HTTP {response.status_code}")
            return False

    except Exception as e:
        print(f"  [X] Download error: {e}")
        return False


async def screenshot_url_with_playwright(url: str, output_path: Path) -> bool:
    """Use Playwright to automatically screenshot a URL. Works perfectly for SVG files!"""
    if not PLAYWRIGHT_AVAILABLE:
        print("  [X] Playwright not available - cannot screenshot")
        return False

    try:
        print(f"  [*] Rendering {url.split('/')[-1]} with Playwright...")

        async with async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(viewport={'width': 2400, 'height': 3000})
            page = await context.new_page()

            # Navigate to URL with longer timeout
            try:
                await page.goto(url, wait_until='load', timeout=60000)
            except:
                # If load times out, try domcontentloaded
                await page.goto(url, wait_until='domcontentloaded', timeout=60000)

            # Wait for rendering
            await page.wait_for_timeout(3000)

            # Take screenshot with timeout
            await page.screenshot(
                path=str(output_path),
                full_page=True,
                timeout=60000
            )

            await browser.close()

        print(f"  [OK] Screenshot saved: {output_path.name} ({output_path.stat().st_size / 1024:.1f} KB)")
        return True

    except Exception as e:
        print(f"  [X] Playwright screenshot failed: {e}")
        # Try simpler approach without full_page
        try:
            print(f"  [*] Retrying with viewport-only screenshot...")
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(viewport={'width': 2400, 'height': 3000})
                page = await context.new_page()
                await page.goto(url, wait_until='domcontentloaded', timeout=60000)
                await page.wait_for_timeout(2000)
                await page.screenshot(path=str(output_path), timeout=30000)
                await browser.close()
            print(f"  [OK] Screenshot saved (viewport): {output_path.name}")
            return True
        except Exception as e2:
            print(f"  [X] Retry also failed: {e2}")
            return False


def is_likely_pipeline_image(url: str, alt_text: str = "") -> bool:
    """Filter out logos, icons, and other non-pipeline images."""
    url_lower = url.lower()
    alt_lower = alt_text.lower()

    # Skip common logo/icon patterns
    skip_patterns = [
        'logo', 'icon', 'banner', 'header', 'footer',
        'favicon', 'thumb', 'avatar', 'profile',
        'social', 'badge', 'button', 'arrow'
    ]

    # Check if URL or alt text contains skip patterns
    for pattern in skip_patterns:
        if pattern in url_lower or pattern in alt_lower:
            return False

    # Look for pipeline-related keywords (positive indicators)
    pipeline_patterns = [
        'pipeline', 'program', 'candidate', 'product',
        'development', 'clinical', 'phase', 'trial'
    ]

    for pattern in pipeline_patterns:
        if pattern in url_lower or pattern in alt_lower:
            return True

    # If URL contains date/version (often used for pipeline images)
    if re.search(r'\d{4}[-_]\d{2}', url):  # e.g., 2025-08, 2025_August
        return True

    # SVG files are often used for pipeline diagrams
    if url_lower.endswith('.svg'):
        return True

    # Large image dimensions in URL might indicate content image
    if any(size in url_lower for size in ['2000', '2400', '1920', 'full', 'large']):
        return True

    # Default: if unsure, process it (but log a warning)
    return True


def find_images_in_markdown(markdown: str) -> List[Tuple[str, str]]:
    """Find all image URLs in markdown content. Returns: List of (url, alt_text) tuples"""
    image_data = []

    # Pattern 1: Markdown image syntax ![alt](url)
    markdown_pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
    for match in re.finditer(markdown_pattern, markdown):
        alt_text = match.group(1)
        url = match.group(2)
        if url and not url.startswith('data:'):
            if is_likely_pipeline_image(url, alt_text):
                image_data.append((url, alt_text))
            else:
                print(f"  [SKIP] Filtered out likely non-pipeline image: {url.split('/')[-1]}")

    # Pattern 2: HTML img tags
    html_pattern = r'<img[^>]+src=["\']([^"\']+)["\'][^>]*(?:alt=["\']([^"\']*)["\'])?'
    for match in re.finditer(html_pattern, markdown, re.IGNORECASE):
        url = match.group(1)
        alt_text = match.group(2) if match.lastindex >= 2 else ""
        if url and not url.startswith('data:'):
            url_already_added = any(existing_url == url for existing_url, _ in image_data)
            if not url_already_added:
                if is_likely_pipeline_image(url, alt_text or ""):
                    image_data.append((url, alt_text or ""))
                else:
                    print(f"  [SKIP] Filtered out likely non-pipeline image: {url.split('/')[-1]}")

    # Pattern 3: Direct image URLs (be more selective here)
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+\.(?:png|jpg|jpeg|gif|svg|webp)'
    for match in re.finditer(url_pattern, markdown, re.IGNORECASE):
        url = match.group(0)
        url_already_added = any(existing_url == url for existing_url, _ in image_data)
        if not url_already_added:
            if is_likely_pipeline_image(url, ""):
                image_data.append((url, ""))
            else:
                print(f"  [SKIP] Filtered out likely non-pipeline image: {url.split('/')[-1]}")

    return image_data


async def process_images_from_markdown(markdown: str, company_name: str) -> List[Path]:
    """Detect and automatically download/screenshot images found in markdown."""
    image_data = find_images_in_markdown(markdown)

    if not image_data:
        print("  [!] No pipeline images found in markdown (logos/icons filtered out)")
        return []

    print(f"  [OK] Found {len(image_data)} potential pipeline image(s):")
    for i, (url, alt_text) in enumerate(image_data, 1):
        alt_display = f' (alt: "{alt_text[:30]}...")' if alt_text else ''
        print(f"      {i}. {url}{alt_display}")

    safe_name = _sanitize_company_name(company_name)
    company_dir = _ensure_company_dir(company_name)

    processed_images = []

    for idx, (url, alt_text) in enumerate(image_data):
        # Save images in company-specific folder
        suffix = f"_image{idx + 1}" if idx > 0 else "_image"
        image_path = company_dir / f"{safe_name}{suffix}.png"

        # Determine file type
        url_lower = url.lower()
        is_svg = url_lower.endswith('.svg')
        is_jpg_jpeg = url_lower.endswith(('.jpg', '.jpeg'))
        is_png = url_lower.endswith('.png')

        print(f"\n  [IMAGE {idx + 1}] {url.split('/')[-1]}")
        if alt_text:
            print(f"  [ALT TEXT] {alt_text}")

        success = False

        if is_svg:
            # SVG: Must use Playwright to render it as PNG
            print(f"  [*] SVG format detected - using automated browser rendering...")
            success = await screenshot_url_with_playwright(url, image_path)

        elif is_png:
            # PNG: Direct download (no conversion needed)
            print(f"  [*] PNG format detected - downloading directly...")
            if download_regular_image(url, image_path):
                print(f"  [OK] PNG downloaded directly (no conversion needed)")
                success = True

        elif is_jpg_jpeg:
            # JPG/JPEG: Direct download
            temp_path = company_dir / f"{safe_name}{suffix}{Path(url).suffix}"
            print(f"  [*] JPG format detected - downloading directly...")
            if download_regular_image(url, temp_path):
                print(f"  [OK] JPG downloaded directly")
                image_path = temp_path
                success = True

        else:
            # Other formats: Try direct download first, fallback to Playwright
            print(f"  [*] {Path(url).suffix} format - attempting download...")
            temp_path = company_dir / f"{safe_name}{suffix}{Path(url).suffix}"
            if download_regular_image(url, temp_path):
                image_path = temp_path
                success = True
            else:
                # Fallback: try Playwright
                print(f"  [*] Direct download failed, trying browser rendering...")
                success = await screenshot_url_with_playwright(url, image_path)

        if success:
            processed_images.append(image_path)
        else:
            print(f"  [X] Failed to process image {idx + 1}")

    return processed_images


async def process_image_url(company_name: str, image_url: str) -> bool:
    """Process a direct image URL: download/screenshot."""
    print(f"\n{'='*80}")
    print(f"Processing Image: {company_name}")
    print(f"URL: {image_url}")
    print('='*80)

    company_dir = _ensure_company_dir(company_name)
    safe_name = _sanitize_company_name(company_name)

    # Determine if it's SVG or regular image
    is_svg = image_url.lower().endswith('.svg') or '.svg?' in image_url.lower()

    if is_svg:
        # SVG needs Playwright rendering
        print("\n[STEP 1/1] Rendering SVG with Playwright...")
        image_path = company_dir / f"{safe_name}_pipeline.png"
        success = await screenshot_url_with_playwright(image_url, image_path)

        if not success:
            print(f"[X] Failed to render SVG for {company_name}.")
            return False
    else:
        # Regular image - download directly
        print("\n[STEP 1/1] Downloading image...")

        # Detect extension from URL
        url_lower = image_url.lower()
        if '.png' in url_lower:
            ext = '.png'
        elif '.jpg' in url_lower or '.jpeg' in url_lower:
            ext = '.jpg'
        elif '.webp' in url_lower:
            ext = '.webp'
        elif '.gif' in url_lower:
            ext = '.gif'
        else:
            ext = '.png'  # default

        image_path = company_dir / f"{safe_name}_pipeline{ext}"
        success = download_regular_image(image_url, image_path)

        if not success:
            print(f"[X] Failed to download image for {company_name}.")
            return False

    # Analyze image with GPT-4 Vision
    print(f"\n[STEP 2/2] Analyzing image with GPT-4 Vision...")
    markdown_analysis = analyze_image_with_vision(image_path, company_name)
    if markdown_analysis:
        # Save markdown analysis
        md_path = company_dir / f"{safe_name}_pipeline_analysis.md"
        try:
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(markdown_analysis)
            print(f"  [OK] Vision analysis saved: {md_path.name}")
        except Exception as e:
            print(f"  [X] Could not save analysis: {e}")

    print(f"\n[✓] Successfully processed image for {company_name}")
    return True


def process_pdf(company_name: str, pdf_url: str) -> bool:
    """Process a PDF URL: download, convert to images, analyze with vision."""
    print(f"\n{'='*80}")
    print(f"Processing PDF: {company_name}")
    print(f"URL: {pdf_url}")
    print('='*80)

    # Step 1: Download PDF
    print("\n[STEP 1/3] Downloading PDF...")
    pdf_path = download_pdf(pdf_url, company_name)

    if not pdf_path:
        print(f"[X] Failed to download PDF for {company_name}.")
        return False

    # Step 2: Convert PDF to images
    print("\n[STEP 2/3] Converting PDF pages to images...")
    image_paths = pdf_to_images(pdf_path, company_name)

    if not image_paths:
        print(f"[X] Failed to convert PDF to images for {company_name}.")
        return False

    # Step 3: Analyze each page with GPT-4 Vision
    print(f"\n[STEP 3/3] Analyzing {len(image_paths)} page(s) with GPT-4 Vision...")
    company_dir = _ensure_company_dir(company_name)
    safe_name = _sanitize_company_name(company_name)

    all_analyses = []
    for idx, image_path in enumerate(image_paths, 1):
        print(f"  [*] Analyzing page {idx}/{len(image_paths)}...")
        markdown_analysis = analyze_image_with_vision(image_path, company_name)
        if markdown_analysis:
            all_analyses.append(f"# Page {idx}\n\n{markdown_analysis}")

    # Save combined markdown analysis
    if all_analyses:
        combined_md = "\n\n---\n\n".join(all_analyses)
        md_path = company_dir / f"{safe_name}_pdf_analysis.md"
        try:
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(combined_md)
            print(f"  [OK] Combined analysis saved: {md_path.name}")
        except Exception as e:
            print(f"  [X] Could not save analysis: {e}")

    print(f"\n[✓] Successfully processed PDF: {len(image_paths)} page(s) converted and analyzed")
    return True


def scrape_url(url: str, company_name: str, wait_for_dynamic: bool = False) -> str:
    """Retrieve clean markdown content for a given URL using Firecrawl."""

    # Configure Firecrawl options based on content type
    scrape_options = {
        "formats": ["markdown"]
    }

    if wait_for_dynamic:
        # Enhanced settings for dynamic/animated content
        print(f"  [*] Using enhanced Firecrawl with scroll-triggered animation handling...")

        # Firecrawl actions to scroll through page and wait for animations
        scrape_options.update({
            "actions": [
                {"type": "scroll", "direction": "down", "amount": 1000},
                {"type": "wait", "milliseconds": 1000},
                {"type": "scroll", "direction": "down", "amount": 1000},
                {"type": "wait", "milliseconds": 1000},
                {"type": "scroll", "direction": "down", "amount": 1000},
                {"type": "wait", "milliseconds": 1000},
                {"type": "scroll", "direction": "down", "amount": 1000},
                {"type": "wait", "milliseconds": 1000},
                {"type": "scroll", "direction": "down", "amount": 1000},
                {"type": "wait", "milliseconds": 1000},
                {"type": "scroll", "direction": "down", "amount": 1000},
                {"type": "wait", "milliseconds": 1000},
                {"type": "scroll", "direction": "up", "amount": 10000},  # Scroll back to top
                {"type": "wait", "milliseconds": 3000},  # Final wait for animations
            ],
            "timeout": 90000,  # 90 second timeout for scrolling + animations
        })

    try:
        print(f"  [*] Scraping with Firecrawl...")
        if wait_for_dynamic:
            print(f"      → Executing scroll script to trigger animations...")
            print(f"      → This will take ~10-15 seconds to complete...")

        response = app.scrape_url(url, **scrape_options)
        markdown = response.markdown if hasattr(response, "markdown") else ""

        # Check if markdown is suspiciously short or missing key content
        if not wait_for_dynamic and (len(markdown) < 500 or not _has_pipeline_indicators(markdown)):
            print(f"  [!] Content seems incomplete (only {len(markdown)} chars)")
            print(f"  [*] Retrying with scroll + animation handling...")
            return scrape_url(url, company_name, wait_for_dynamic=True)

        # Sanitize the company name for safe use in a filename
        safe_company_name = _sanitize_company_name(company_name)
        file_name = f"{safe_company_name}.md"

        # Define the file path
        data_dir = _ensure_data_dir()
        file_path = data_dir / file_name

        # Write the content to the file
        try:
            with open(file_path, mode="w", encoding="utf-8") as f:
                f.write(markdown)
            print(f"  [OK] Scraped markdown saved to {file_path.resolve()} ({len(markdown)} chars)")
        except Exception as e:
            print(f"  [X] Could not save file to {file_path}. Details: {e}")

        return markdown

    except Exception as e:
        print(f"  [X] Firecrawl scraping failed: {e}")
        if not wait_for_dynamic:
            print(f"  [*] Retrying with scroll + animation handling...")
            return scrape_url(url, company_name, wait_for_dynamic=True)
        else:
            print(f"  [X] Enhanced scraping also failed. Returning empty content.")
            return ""


async def process_company_async(company_name: str, url: str, wait_for_dynamic: bool = False) -> bool:
    """Process a single company: scrape web URL with Firecrawl."""
    print(f"\n{'='*80}")
    print(f"Processing: {company_name}")
    print(f"URL: {url}")
    print('='*80)

    # Scrape with Firecrawl
    print("\nScraping with Firecrawl...")
    markdown = scrape_url(url, company_name, wait_for_dynamic=wait_for_dynamic)

    if not markdown:
        print(f"[X] Failed to scrape {company_name}.")
        return False

    print(f"\n[✓] Successfully processed {company_name}")
    return True


def main(urls_file: str, wait_for_dynamic: bool = False):
    """Main pipeline: scrape URLs and save markdown output."""
    urls_path = Path(urls_file)
    if not urls_path.is_file():
        raise FileNotFoundError(f"URLs file not found: {urls_file}")

    # Read and parse lines: assuming format is 'Company Name,URL'
    company_urls: List[Tuple[str, str]] = []
    for line in urls_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            # Split only on the first comma to handle commas that might be in the URL itself
            company_name, url = line.split(',', 1)
            company_urls.append((company_name.strip(), url.strip()))
        except ValueError:
            print(f"Skipping malformed line (expected 'Company Name,URL'): {line}")
            continue

    # Process all companies in one async context
    async def process_all_companies():
        successful = 0
        failed = 0

        print(f"\n{'='*80}")
        print(f"Starting processing of {len(company_urls)} URL(s)")
        print('='*80)

        for idx, (company_name, url) in enumerate(company_urls, 1):
            print(f"\n[{idx}/{len(company_urls)}]")

            # Check URL type and route to appropriate handler
            if is_pdf_url(url):
                print(f"[DETECTED] PDF URL for {company_name}")
                success = process_pdf(company_name, url)  # Synchronous call
            elif is_image_url(url):
                print(f"[DETECTED] Image URL for {company_name}")
                success = await process_image_url(company_name, url)  # Async call
            else:
                print(f"[DETECTED] Web URL for {company_name}")
                success = await process_company_async(company_name, url, wait_for_dynamic)

            if success:
                successful += 1
            else:
                failed += 1

        return successful, failed

    # Run all processing in single async context
    successful, failed = asyncio.run(process_all_companies())

    # Final summary
    print(f"\n{'='*80}")
    print(f"[SUCCESS] PROCESSING COMPLETE!")
    print(f"  Output directory: {DATA_DIR.resolve()}")
    print(f"  Total URLs: {len(company_urls)}")
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")
    print('='*80)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Scrape URLs using Firecrawl and save markdown output. "
                    "Automatically handles dynamic/animated content, PDFs, and images.")
    parser.add_argument("--urls", required=True,
                        help="Path to a text file containing 'Company Name,URL' pairs (one per line).")
    parser.add_argument(
        "--wait-for-dynamic", action="store_true",
        help="Force Firecrawl to wait for animations/dynamic content on all URLs. "
             "Use this for sites with CSS animations, JavaScript-rendered elements, or lazy-loaded content. "
             "Auto-detection will also trigger enhanced settings when needed.")
    args = parser.parse_args()
    main(args.urls, wait_for_dynamic=args.wait_for_dynamic)
