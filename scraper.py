import os
import json
from datetime import datetime
from dotenv import load_dotenv
from firecrawl import FirecrawlApp

# Load environment variables from .env file
load_dotenv()

# Initialize Firecrawl with your API key
api_key = os.getenv("FIRECRAWL_API_KEY")
app = FirecrawlApp(api_key=api_key)

def scrape_url(url: str):
    """
    Scrape a single URL and return the content.

    Args:
        url: The URL to scrape

    Returns:
        dict: The scraped content
    """
    try:
        # Scrape the URL using v2 API
        result = app.scrape(url)
        return result
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None

def crawl_website(url: str, max_pages: int = 10):
    """
    Crawl an entire website starting from the given URL.

    Args:
        url: The starting URL to crawl
        max_pages: Maximum number of pages to crawl (default: 10)

    Returns:
        dict: The crawl results
    """
    try:
        # Start a crawl job with limit parameter
        crawl_result = app.crawl(url, limit=max_pages)
        return crawl_result
    except Exception as e:
        print(f"Error crawling {url}: {e}")
        return None

def save_to_json(data, filename=None):
    """
    Save crawl/scrape data to a JSON file.

    Args:
        data: The data to save (Document or CrawlJob object)
        filename: Optional custom filename (auto-generated if not provided)

    Returns:
        str: The filename where data was saved
    """
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"scraped_data_{timestamp}.json"

    # Convert Pydantic objects to dictionary with mode='json' for proper serialization
    if hasattr(data, 'model_dump'):
        data_dict = data.model_dump(mode='json')
    elif hasattr(data, 'dict'):
        data_dict = data.dict()
    else:
        data_dict = data

    # Custom JSON encoder for any remaining non-serializable objects
    def default_encoder(obj):
        if hasattr(obj, 'model_dump'):
            return obj.model_dump(mode='json')
        elif hasattr(obj, 'dict'):
            return obj.dict()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        else:
            return str(obj)

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data_dict, f, indent=2, ensure_ascii=False, default=default_encoder)

    return filename

def main():
    print("=== Firecrawl Web Scraper ===\n")

    # Get user choice
    print("Choose an option:")
    print("1. Scrape a single page")
    print("2. Crawl multiple pages from a website")
    choice = input("\nEnter your choice (1 or 2): ").strip()

    if choice == "1":
        # Scrape single page
        url = input("Enter the URL to scrape: ").strip()
        print(f"\nScraping {url}...\n")
        result = scrape_url(url)

        if result:
            # Result is a Document object, access attributes directly
            print(f"Title: {getattr(result.metadata, 'title', 'N/A') if hasattr(result, 'metadata') else 'N/A'}")
            print(f"URL: {getattr(result.metadata, 'url', url) if hasattr(result, 'metadata') else url}")
            if hasattr(result, 'markdown'):
                print(f"\nContent preview:\n{result.markdown[:500]}...")
            elif hasattr(result, 'content'):
                print(f"\nContent preview:\n{result.content[:500]}...")

            # Save to JSON
            filename = save_to_json(result)
            print(f"\n✓ Data saved to: {filename}")
        else:
            print("Failed to scrape the URL.")

    elif choice == "2":
        # Crawl website
        url = input("Enter the starting URL to crawl: ").strip()
        max_pages_input = input("Enter max number of pages to crawl (default 10): ").strip()
        max_pages = int(max_pages_input) if max_pages_input else 10

        print(f"\nCrawling {url} (max {max_pages} pages)...\n")
        crawl_result = crawl_website(url, max_pages)

        if crawl_result:
            # Get the data from the crawl result
            pages = getattr(crawl_result, 'data', [])
            print(f"Successfully crawled {len(pages)} pages:\n")
            for i, page in enumerate(pages, 1):
                title = getattr(page.metadata, 'title', 'N/A') if hasattr(page, 'metadata') else 'N/A'
                page_url = getattr(page.metadata, 'url', 'N/A') if hasattr(page, 'metadata') else 'N/A'
                print(f"{i}. {title}")
                print(f"   URL: {page_url}")

            # Save to JSON
            filename = save_to_json(crawl_result)
            print(f"\n✓ Crawl data saved to: {filename}")
        else:
            print("Failed to crawl the website.")

    else:
        print("Invalid choice. Please run the script again and select 1 or 2.")

if __name__ == "__main__":
    main()
