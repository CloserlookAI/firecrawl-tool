import os
import json
from datetime import datetime
from dotenv import load_dotenv
from firecrawl import FirecrawlApp
from firecrawl.v2.types import ScrapeOptions
from playwright.sync_api import sync_playwright
import asyncio

# Load environment variables from .env file
load_dotenv()

# Initialize Firecrawl with your API key
api_key = os.getenv("FIRECRAWL_API_KEY")
app = FirecrawlApp(api_key=api_key)

def scrape_url(url: str, wait_for: int = 5000, include_screenshot: bool = False, include_video: bool = False, video_duration: int = 10):
    """
    Scrape a single URL and return the content.

    Args:
        url: The URL to scrape
        wait_for: Time to wait in milliseconds for dynamic content (default: 5000ms)
        include_screenshot: Whether to include a screenshot for preview (default: False)
        include_video: Whether to include a video recording of animations (default: False)
        video_duration: Duration of video recording in seconds (default: 10)

    Returns:
        dict: The scraped content with optional video path
    """
    try:
        # Configure formats list
        formats = ['markdown', 'html']  # Get both markdown and HTML
        if include_screenshot:
            formats.append('screenshot')

        # Scrape the URL with dynamic content handling
        result = app.scrape(
            url,
            formats=formats,
            wait_for=wait_for
        )

        # If video recording is requested, record the page
        if include_video and result:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_filename = f"page_recording_{timestamp}.webm"

            print(f"Recording video of animations...")
            video_path = record_page_video(url, video_duration, video_filename)

            # Add video path to result
            if video_path:
                # Convert result to dict if it's a Pydantic model
                if hasattr(result, 'model_dump'):
                    result_dict = result.model_dump(mode='json')
                elif hasattr(result, 'dict'):
                    result_dict = result.dict()
                else:
                    result_dict = result

                # Add video information
                result_dict['video'] = {
                    'path': video_path,
                    'duration': video_duration,
                    'format': 'webm'
                }

                return result_dict

        return result
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None

def scrape_url_structured(url: str, schema: dict, wait_for: int = 5000, prompt: str = None):
    """
    Scrape a URL and extract structured data based on a schema.
    This captures all dynamic content and returns it in a clean JSON format.

    Args:
        url: The URL to scrape
        schema: JSON schema defining the structure of data to extract
        wait_for: Time to wait in milliseconds for dynamic content (default: 5000ms)
        prompt: Optional prompt to guide the extraction

    Returns:
        dict: Structured data extracted from the page
    """
    try:
        print(f"Extracting structured data from {url}...")
        print("Waiting for dynamic content to load...\n")

        # Create ScrapeOptions object for dynamic content handling
        scrape_opts = ScrapeOptions(
            wait_for=wait_for,
            formats=['markdown', 'html']
        )

        # Use Firecrawl's extract method
        result = app.extract(
            urls=[url],
            schema=schema,
            prompt=prompt if prompt else 'Extract all the data according to the schema',
            scrape_options=scrape_opts
        )

        # Convert result to dict if needed
        if hasattr(result, 'model_dump'):
            result_dict = result.model_dump(mode='json')
        elif hasattr(result, 'dict'):
            result_dict = result.dict()
        else:
            result_dict = result

        return result_dict
    except Exception as e:
        print(f"Error extracting structured data from {url}: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_schema_templates():
    """
    Returns predefined schema templates for common use cases.
    """
    return {
        "news": {
            "type": "object",
            "properties": {
                "articles": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "url": {"type": "string"},
                            "author": {"type": "string"},
                            "points": {"type": "number"},
                            "comments_count": {"type": "number"},
                            "time_posted": {"type": "string"}
                        }
                    }
                }
            }
        },
        "ecommerce": {
            "type": "object",
            "properties": {
                "products": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "price": {"type": "string"},
                            "currency": {"type": "string"},
                            "rating": {"type": "number"},
                            "reviews_count": {"type": "number"},
                            "availability": {"type": "string"},
                            "image_url": {"type": "string"},
                            "product_url": {"type": "string"}
                        }
                    }
                }
            }
        },
        "social_media": {
            "type": "object",
            "properties": {
                "posts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "author": {"type": "string"},
                            "content": {"type": "string"},
                            "likes_count": {"type": "number"},
                            "comments_count": {"type": "number"},
                            "shares_count": {"type": "number"},
                            "timestamp": {"type": "string"},
                            "post_url": {"type": "string"}
                        }
                    }
                }
            }
        },
        "real_estate": {
            "type": "object",
            "properties": {
                "listings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "price": {"type": "string"},
                            "bedrooms": {"type": "number"},
                            "bathrooms": {"type": "number"},
                            "area": {"type": "string"},
                            "location": {"type": "string"},
                            "description": {"type": "string"},
                            "image_url": {"type": "string"}
                        }
                    }
                }
            }
        },
        "jobs": {
            "type": "object",
            "properties": {
                "job_listings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "company": {"type": "string"},
                            "location": {"type": "string"},
                            "salary": {"type": "string"},
                            "job_type": {"type": "string"},
                            "posted_date": {"type": "string"},
                            "description": {"type": "string"},
                            "apply_url": {"type": "string"}
                        }
                    }
                }
            }
        }
    }

def crawl_website(url: str, max_pages: int = 10, wait_for: int = 5000):
    """
    Crawl an entire website starting from the given URL.

    Args:
        url: The starting URL to crawl
        max_pages: Maximum number of pages to crawl (default: 10)
        wait_for: Time to wait in milliseconds for dynamic content (default: 5000ms)

    Returns:
        dict: The crawl results
    """
    try:
        # Start a crawl job with dynamic content handling
        crawl_result = app.crawl(
            url,
            limit=max_pages,
            scrape_formats=['markdown', 'html'],
            wait_for=wait_for
        )
        return crawl_result
    except Exception as e:
        print(f"Error crawling {url}: {e}")
        return None

def preview_dynamic_page(url: str, include_video: bool = False, video_duration: int = 10):
    """
    Preview a dynamic page with screenshot and optional video before crawling.
    Useful for inspecting what content is being loaded.

    Args:
        url: The URL to preview
        include_video: Whether to include video recording (default: False)
        video_duration: Duration of video recording in seconds (default: 10)

    Returns:
        dict: Preview results including screenshot and optional video
    """
    print(f"Previewing {url}...")
    if include_video:
        print("This will take a screenshot and record a video of animations.\n")
    else:
        print("This will take a screenshot and show you what Firecrawl sees.\n")

    result = scrape_url(url, wait_for=5000, include_screenshot=True, include_video=include_video, video_duration=video_duration)

    if result:
        print("Preview successful!")

        # Handle both dict and object results
        if isinstance(result, dict):
            if 'screenshot' in result:
                print(f"Screenshot saved in the response data")
            if 'video' in result:
                print(f"Video saved at: {result['video']['path']}")

            metadata = result.get('metadata', {})
            title = metadata.get('title', 'N/A') if isinstance(metadata, dict) else getattr(metadata, 'title', 'N/A')
            markdown = result.get('markdown', '')
            content_length = len(markdown) if markdown else 0
        else:
            if hasattr(result, 'screenshot'):
                print(f"Screenshot saved in the response data")
            title = getattr(result.metadata, 'title', 'N/A') if hasattr(result, 'metadata') else 'N/A'
            content_length = len(result.markdown) if hasattr(result, 'markdown') else 0

        print(f"\nPage Title: {title}")
        print(f"Content Length: {content_length} characters")
        return result
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

def record_page_video(url: str, duration: int = 10, output_filename: str = None):
    """
    Record a video of a webpage to capture animations and dynamic content.

    Args:
        url: The URL to record
        duration: Recording duration in seconds (default: 10)
        output_filename: Optional custom filename (auto-generated if not provided)

    Returns:
        str: The filename where video was saved
    """
    if output_filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"page_recording_{timestamp}.webm"

    print(f"Recording {url} for {duration} seconds...")
    print("This will capture all animations and dynamic content.\n")

    try:
        with sync_playwright() as p:
            # Launch browser
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                record_video_dir=".",
                record_video_size={'width': 1920, 'height': 1080}
            )
            page = context.new_page()

            # Navigate to the URL
            print(f"Loading page...")
            page.goto(url, wait_until='networkidle', timeout=30000)

            # Wait for initial content and scroll through page to capture animations
            print(f"Capturing animations...")
            page.wait_for_timeout(2000)  # Wait 2 seconds after load

            # Scroll through the page to trigger scroll animations
            page.evaluate("""
                async () => {
                    const distance = 100;
                    const delay = 100;
                    const scrollHeight = document.body.scrollHeight;

                    for (let i = 0; i < scrollHeight; i += distance) {
                        window.scrollBy(0, distance);
                        await new Promise(resolve => setTimeout(resolve, delay));
                    }

                    // Scroll back to top
                    window.scrollTo(0, 0);
                }
            """)

            # Wait for the specified duration
            remaining_time = duration - 2
            if remaining_time > 0:
                page.wait_for_timeout(remaining_time * 1000)

            # Get the video path before closing
            video_path = page.video.path()

            # Close context to save video
            print(f"Finalizing video...")
            context.close()
            browser.close()

            # Rename to our desired filename
            import shutil
            if os.path.exists(video_path):
                shutil.move(video_path, output_filename)
                print(f"✓ Video saved to: {output_filename}")
                return output_filename
            else:
                print(f"Warning: Video file not found at {video_path}")
                return None

    except Exception as e:
        print(f"Error recording video: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    print("=== Firecrawl Web Scraper ===\n")

    # Get user choice
    print("Choose an option:")
    print("1. Scrape a single page")
    print("2. Crawl multiple pages from a website")
    print("3. Preview a dynamic page (with screenshot)")
    print("4. Record page video (capture animations)")
    print("5. Extract structured JSON data (with dynamic content)")
    choice = input("\nEnter your choice (1, 2, 3, 4, or 5): ").strip()

    if choice == "1":
        # Scrape single page
        url = input("Enter the URL to scrape: ").strip()
        include_video = input("Include video recording of animations? (y/n, default: n): ").strip().lower() == 'y'

        video_duration = 10
        if include_video:
            duration_input = input("Enter video duration in seconds (default 10): ").strip()
            video_duration = int(duration_input) if duration_input else 10

        print(f"\nScraping {url}...\n")
        result = scrape_url(url, include_video=include_video, video_duration=video_duration)

        if result:
            # Handle both dict and object results
            if isinstance(result, dict):
                metadata = result.get('metadata', {})
                title = metadata.get('title', 'N/A') if isinstance(metadata, dict) else getattr(metadata, 'title', 'N/A')
                result_url = metadata.get('url', url) if isinstance(metadata, dict) else getattr(metadata, 'url', url)
                markdown = result.get('markdown', result.get('content', ''))

                print(f"Title: {title}")
                print(f"URL: {result_url}")
                if markdown:
                    print(f"\nContent preview:\n{markdown[:500]}...")
                if 'video' in result:
                    print(f"\n✓ Video recording saved at: {result['video']['path']}")
            else:
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

    elif choice == "3":
        # Preview dynamic page
        url = input("Enter the URL to preview: ").strip()
        include_video = input("Include video recording of animations? (y/n, default: n): ").strip().lower() == 'y'

        video_duration = 10
        if include_video:
            duration_input = input("Enter video duration in seconds (default 10): ").strip()
            video_duration = int(duration_input) if duration_input else 10

        print(f"\nPreviewing {url}...\n")
        result = preview_dynamic_page(url, include_video=include_video, video_duration=video_duration)

        if result:
            # Show content preview
            if isinstance(result, dict):
                markdown = result.get('markdown', '')
                if markdown:
                    print(f"\nContent preview (first 500 chars):\n{markdown[:500]}...")
            elif hasattr(result, 'markdown'):
                print(f"\nContent preview (first 500 chars):\n{result.markdown[:500]}...")

            # Save to JSON
            filename = save_to_json(result)
            print(f"\n✓ Preview data saved to: {filename}")
        else:
            print("Failed to preview the page.")

    elif choice == "4":
        # Record video of page animations
        url = input("Enter the URL to record: ").strip()
        duration_input = input("Enter recording duration in seconds (default 10): ").strip()
        duration = int(duration_input) if duration_input else 10

        print(f"\nRecording video of {url} for {duration} seconds...\n")
        video_file = record_page_video(url, duration)

        if video_file:
            print(f"\n✓ Successfully recorded animations to: {video_file}")
            print(f"Open the video file to view captured animations and dynamic content.")
        else:
            print("Failed to record video.")

    elif choice == "5":
        # Extract structured JSON data
        print("\n=== Structured Data Extraction ===")
        print("This will extract dynamic content into clean, structured JSON format.\n")

        url = input("Enter the URL to scrape: ").strip()

        # Show available templates
        print("\nAvailable schema templates:")
        print("1. News/Blog (articles with title, author, points, comments)")
        print("2. E-commerce (products with price, rating, availability)")
        print("3. Social Media (posts with likes, comments, shares)")
        print("4. Real Estate (listings with price, bedrooms, location)")
        print("5. Jobs (job listings with company, salary, location)")
        print("6. Custom (provide your own schema)")

        template_choice = input("\nSelect a template (1-6): ").strip()

        schemas = get_schema_templates()
        schema_map = {
            "1": ("news", schemas["news"]),
            "2": ("ecommerce", schemas["ecommerce"]),
            "3": ("social_media", schemas["social_media"]),
            "4": ("real_estate", schemas["real_estate"]),
            "5": ("jobs", schemas["jobs"])
        }

        if template_choice in schema_map:
            schema_name, schema = schema_map[template_choice]
            print(f"\nUsing {schema_name} schema...")
        elif template_choice == "6":
            print("\nPlease provide your custom schema as a JSON string:")
            schema_input = input("Schema: ").strip()
            try:
                schema = json.loads(schema_input)
            except json.JSONDecodeError as e:
                print(f"Invalid JSON schema: {e}")
                return
        else:
            print("Invalid template choice.")
            return

        # Extract with schema
        result = scrape_url_structured(url, schema, wait_for=5000)

        if result:
            print("\n✓ Successfully extracted structured data!")

            # Show preview of extracted data
            if isinstance(result, dict):
                # The extract method returns data in 'data' field
                extracted = result.get('data', result.get('extract', result))

                print("\n--- Extracted Data Preview ---")
                preview = json.dumps(extracted, indent=2, ensure_ascii=False)
                if len(preview) > 1000:
                    print(preview[:1000] + "\n... (truncated, see JSON file for full data)")
                else:
                    print(preview)

            # Save to JSON
            filename = save_to_json(result)
            print(f"\n✓ Structured data saved to: {filename}")
            print("This file contains all the dynamic content in clean JSON format!")
        else:
            print("Failed to extract structured data.")

    else:
        print("Invalid choice. Please run the script again and select 1, 2, 3, 4, or 5.")

if __name__ == "__main__":
    main()
