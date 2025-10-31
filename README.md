# Firecrawl Web Scraper

A simple, powerful web scraper using the Firecrawl API that converts web pages to clean markdown format with automatic dynamic content handling.

## Features

- =� **Simple**: Just provide URLs, get markdown output
- = **Smart Retry**: Automatically detects incomplete content and retries with enhanced settings
- � **Dynamic Content**: Handles JavaScript-rendered pages, animations, and lazy-loaded content
- =� **Clean Output**: Returns well-formatted markdown for easy processing
- <� **Auto-Detection**: Detects when pages need scroll/wait actions and applies them automatically

## Installation

1. Clone this repository:
```bash
git clone <your-repo-url>
cd firecrawl-tool
```

2. Install dependencies:
```bash
pip install -r requirements.txt
# OR using uv:
uv pip install -e .
```

3. Set up your environment:
```bash
cp example.env .env
# Edit .env and add your Firecrawl API key
```

## Configuration

Create a `.env` file in the project root:

```env
FIRECRAWL_API_KEY=your_api_key_here
```

Get your API key from [Firecrawl](https://firecrawl.dev).

## Usage

### Basic Usage

Create a `urls.txt` file with your URLs:

```
Company Name,https://example.com
Another Site,https://example.org
```

Run the scraper:

```bash
python scraper.py --urls urls.txt
```

### Force Dynamic Content Handling

For sites with heavy JavaScript/animations:

```bash
python scraper.py --urls urls.txt --wait-for-dynamic
```

### URL File Format

The URLs file should contain one entry per line in the format:

```
Name,URL
```

- **Name**: A friendly name for the site (used for the output filename)
- **URL**: The full URL to scrape

Example:
```
Google,https://www.google.com
GitHub,https://github.com
Example Company,https://example.com/about
```

Lines starting with `#` are treated as comments and ignored.

## Output

All scraped content is saved to the `data/` directory:

- Each URL is saved as `{sanitized_name}.md`
- Names are sanitized (spaces � underscores, lowercase)
- Example: "Company Name" � `data/company_name.md`

## How It Works

1. **Initial Scrape**: Firecrawl retrieves the page content
2. **Content Check**: Analyzes if content seems complete (length, indicators)
3. **Smart Retry**: If incomplete, automatically retries with:
   - Scroll actions to trigger animations
   - Wait periods for JS rendering
   - Multiple scroll passes through the page
4. **Save**: Writes clean markdown to file

## Features in Detail

### Automatic Dynamic Content Detection

The scraper checks for content indicators like:
- Headings (`##`, `###`)
- Tables (`|`)
- Lists (`-`)
- Multiple paragraphs

If these are missing or content is suspiciously short (<500 chars), it automatically retries with enhanced settings.

### Enhanced Scraping

When `--wait-for-dynamic` is enabled or auto-triggered:
- Scrolls through the page in increments
- Waits for animations to complete
- Scrolls back to top to capture initial state
- Total ~10-15 second wait time per page

### Error Handling

- Gracefully handles failed scrapes
- Reports success/failure for each URL
- Provides detailed error messages
- Final summary with statistics

## Examples

### Example 1: Simple Scraping

```bash
# Create urls.txt
echo "OpenAI,https://openai.com" > urls.txt
echo "Anthropic,https://anthropic.com" >> urls.txt

# Run scraper
python scraper.py --urls urls.txt
```

Output:
```
data/openai.md
data/anthropic.md
```

### Example 2: Dynamic Content

For sites with animations or JS-heavy content:

```bash
python scraper.py --urls urls.txt --wait-for-dynamic
```

## Troubleshooting

### Issue: Empty or incomplete markdown

**Solution**: Use `--wait-for-dynamic` flag:
```bash
python scraper.py --urls urls.txt --wait-for-dynamic
```

### Issue: "FIRECRAWL_API_KEY not set"

**Solution**: Create `.env` file with your API key:
```bash
echo "FIRECRAWL_API_KEY=your_key_here" > .env
```

### Issue: Import errors

**Solution**: Install dependencies:
```bash
pip install firecrawl-py python-dotenv
```

## Command-Line Options

```
python scraper.py --help

options:
  --urls URLS           Path to text file containing 'Name,URL' pairs (required)
  --wait-for-dynamic    Force enhanced scraping for all URLs (optional)
  -h, --help           Show this help message
```

## Requirements

- Python 3.12+
- firecrawl-py >= 4.5.0
- python-dotenv >= 1.1.1

## API Limits

Be aware of your Firecrawl API plan limits:
- Free tier: Limited scrapes per month
- Paid tiers: Higher limits

Check [Firecrawl pricing](https://firecrawl.dev/pricing) for details.

## License

MIT License - see LICENSE file for details

## Contributing

Contributions welcome! Please feel free to submit a Pull Request.

---source .venv/bin/activate && python scraper.py --urls urls.txt
