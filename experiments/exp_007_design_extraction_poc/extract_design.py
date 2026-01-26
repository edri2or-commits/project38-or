#!/usr/bin/env python3
"""Minimal POC: Extract design tokens from URL (No Playwright).

Usage:
    python extract_design.py https://example.com

Uses CSS extraction + Claude analysis (no browser required).

Requires:
    - requests, beautifulsoup4, cssutils
    - anthropic
    - ANTHROPIC_API_KEY or ANTHROPIC-API in GCP Secret Manager
"""

import json
import os
import re
import sys
from pathlib import Path

# Add src to path for secrets_manager
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Installing dependencies...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "requests", "beautifulsoup4"])
    import requests
    from bs4 import BeautifulSoup


def extract_colors_from_css(css_text: str) -> list[str]:
    """Extract hex colors from CSS text.

    Args:
        css_text: Raw CSS content

    Returns:
        List of unique hex colors
    """
    # Match hex colors (#RGB, #RRGGBB, #RRGGBBAA)
    hex_pattern = r'#(?:[0-9a-fA-F]{3,4}){1,2}\b'
    colors = re.findall(hex_pattern, css_text)

    # Normalize to 6-digit hex
    normalized = []
    for color in colors:
        color = color.upper()
        if len(color) == 4:  # #RGB -> #RRGGBB
            color = f"#{color[1]*2}{color[2]*2}{color[3]*2}"
        elif len(color) == 5:  # #RGBA -> #RRGGBBAA (drop alpha)
            color = f"#{color[1]*2}{color[2]*2}{color[3]*2}"
        elif len(color) == 9:  # #RRGGBBAA -> #RRGGBB (drop alpha)
            color = color[:7]
        normalized.append(color)

    # Return unique colors, sorted by frequency
    from collections import Counter
    counts = Counter(normalized)
    return [color for color, _ in counts.most_common(20)]


def extract_fonts_from_css(css_text: str) -> list[str]:
    """Extract font families from CSS.

    Args:
        css_text: Raw CSS content

    Returns:
        List of font family names
    """
    font_pattern = r'font-family\s*:\s*([^;]+)'
    matches = re.findall(font_pattern, css_text, re.IGNORECASE)

    fonts = []
    for match in matches:
        # Parse font stack
        for font in match.split(','):
            font = font.strip().strip('"\'')
            if font and font.lower() not in ['inherit', 'initial', 'sans-serif', 'serif', 'monospace']:
                fonts.append(font)

    # Return unique fonts
    return list(dict.fromkeys(fonts))[:10]


def fetch_page_data(url: str) -> dict:
    """Fetch page HTML and extract CSS.

    Args:
        url: Website URL

    Returns:
        Dictionary with html, inline_css, linked_css
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')

    # Extract inline CSS
    inline_css = ""
    for style in soup.find_all('style'):
        inline_css += style.get_text() + "\n"

    # Extract inline styles from elements
    for elem in soup.find_all(style=True):
        inline_css += elem['style'] + "\n"

    # Fetch linked CSS (first 3 only to avoid too many requests)
    linked_css = ""
    for link in soup.find_all('link', rel='stylesheet')[:3]:
        href = link.get('href')
        if href:
            if not href.startswith('http'):
                # Make absolute URL
                from urllib.parse import urljoin
                href = urljoin(url, href)
            try:
                css_response = requests.get(href, headers=headers, timeout=10)
                linked_css += css_response.text + "\n"
            except Exception:
                pass  # Skip failed CSS fetches

    return {
        'title': soup.title.string if soup.title else '',
        'inline_css': inline_css,
        'linked_css': linked_css,
        'meta_description': soup.find('meta', attrs={'name': 'description'})['content'] if soup.find('meta', attrs={'name': 'description'}) else ''
    }


def get_anthropic_client():
    """Get Anthropic client with API key."""
    try:
        from anthropic import Anthropic
    except ImportError:
        print("Installing anthropic...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "anthropic"])
        from anthropic import Anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if not api_key:
        try:
            from secrets_manager import SecretManager
            manager = SecretManager()
            api_key = manager.get_secret("ANTHROPIC-API")
        except Exception as e:
            print(f"WARNING: Could not get key from GCP: {e}")

    if not api_key:
        print("ERROR: No ANTHROPIC_API_KEY found")
        sys.exit(1)

    return Anthropic(api_key=api_key)


def analyze_with_claude(page_data: dict, colors: list[str], fonts: list[str], url: str) -> dict:
    """Use Claude to analyze and structure the design tokens.

    Args:
        page_data: Page metadata
        colors: Extracted colors
        fonts: Extracted fonts
        url: Original URL

    Returns:
        Structured design tokens
    """
    client = get_anthropic_client()

    prompt = f"""Analyze these extracted design elements from {url} and return structured design tokens.

**Page Title:** {page_data['title']}
**Description:** {page_data['meta_description'][:200] if page_data['meta_description'] else 'N/A'}

**Extracted Colors (by frequency):**
{json.dumps(colors[:15], indent=2)}

**Extracted Fonts:**
{json.dumps(fonts, indent=2)}

Based on this data, determine:
1. Which color is likely the PRIMARY brand color (usually bold, used for CTAs)
2. Which colors are SECONDARY, ACCENT, BACKGROUND, TEXT
3. The overall style (minimal/corporate/playful/elegant/bold)

Return ONLY valid JSON (no markdown) with this structure:
{{
    "brand_colors": {{
        "primary": "#XXXXXX",
        "secondary": "#XXXXXX",
        "accent": "#XXXXXX",
        "background": "#XXXXXX",
        "text": "#XXXXXX"
    }},
    "all_colors": ["#XXXXXX", ...],
    "fonts": {{
        "primary": "Font name",
        "fallback": "sans-serif/serif"
    }},
    "style": {{
        "overall": "minimal/corporate/playful/elegant/bold",
        "mood": "one word description"
    }},
    "confidence": 0.0-1.0
}}

If you can't determine a color, use null."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = response.content[0].text.strip()

    # Handle markdown code blocks
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]
        response_text = response_text.strip()

    try:
        return json.loads(response_text)
    except json.JSONDecodeError as e:
        return {"error": str(e), "raw": response_text[:500]}


def get_sample_data() -> dict:
    """Return sample data for testing without network access."""
    sample_css = """
    :root {
        --primary-color: #635BFF;
        --secondary-color: #0A2540;
        --accent-color: #00D4FF;
        --background: #F6F9FC;
        --text-color: #425466;
    }
    body {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        color: #425466;
        background-color: #FFFFFF;
    }
    h1, h2, h3 {
        font-family: 'Inter', sans-serif;
        color: #0A2540;
    }
    .btn-primary {
        background-color: #635BFF;
        color: #FFFFFF;
    }
    .btn-secondary {
        background-color: #0A2540;
        color: #FFFFFF;
    }
    a { color: #635BFF; }
    .card { background: #F6F9FC; border-radius: 8px; }
    .footer { background: #0A2540; color: #FFFFFF; }
    """
    return {
        'title': 'Stripe | Payment Processing Platform',
        'inline_css': sample_css,
        'linked_css': '',
        'meta_description': 'Online payment processing for internet businesses. Stripe is a suite of payment APIs.'
    }


def mock_analyze(colors: list[str], fonts: list[str]) -> dict:
    """Mock analysis when Claude API is unavailable."""
    return {
        "brand_colors": {
            "primary": colors[0] if colors else None,
            "secondary": colors[1] if len(colors) > 1 else None,
            "accent": colors[2] if len(colors) > 2 else None,
            "background": colors[3] if len(colors) > 3 else None,
            "text": colors[4] if len(colors) > 4 else None
        },
        "all_colors": colors,
        "fonts": {
            "primary": fonts[0] if fonts else "sans-serif",
            "fallback": "sans-serif"
        },
        "style": {
            "overall": "minimal",
            "mood": "professional"
        },
        "confidence": 0.5,
        "note": "Mock analysis - run with Claude API for accurate results"
    }


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python extract_design.py <URL>")
        print("       python extract_design.py --test")
        print("       python extract_design.py --test --mock")
        print("Example: python extract_design.py https://stripe.com")
        sys.exit(1)

    use_mock = "--mock" in sys.argv

    # Test mode for environments with proxy restrictions
    if "--test" in sys.argv:
        print("🧪 Running in TEST mode with sample data...")
        url = "https://stripe.com (sample)"
        page_data = get_sample_data()
    else:
        url = sys.argv[1]
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

    if sys.argv[1] != "--test":
        print(f"🌐 Fetching {url}...")
        try:
            page_data = fetch_page_data(url)
        except Exception as e:
            print(f"ERROR: Failed to fetch page: {e}")
            sys.exit(1)

    print(f"   Title: {page_data['title']}")

    # Extract colors from CSS
    all_css = page_data['inline_css'] + page_data['linked_css']
    print(f"📝 Analyzing CSS ({len(all_css)} chars)...")

    colors = extract_colors_from_css(all_css)
    fonts = extract_fonts_from_css(all_css)

    print(f"   Found {len(colors)} unique colors")
    print(f"   Found {len(fonts)} fonts")

    if not colors:
        print("WARNING: No colors found in CSS. Using fallback analysis.")
        colors = ["#FFFFFF", "#000000", "#333333"]

    if use_mock:
        print("🎨 Using mock analysis (no API call)...")
        tokens = mock_analyze(colors, fonts)
    else:
        print("🎨 Analyzing design with Claude...")
        tokens = analyze_with_claude(page_data, colors, fonts, url)

    # Pretty print result
    print("\n" + "="*60)
    print("DESIGN TOKENS")
    print("="*60)
    print(json.dumps(tokens, indent=2))

    # Save result
    result = {
        "url": url,
        "title": page_data['title'],
        "raw_colors": colors,
        "raw_fonts": fonts,
        "tokens": tokens
    }

    result_path = Path(__file__).parent / "last_result.json"
    result_path.write_text(json.dumps(result, indent=2))
    print(f"\n💾 Saved to {result_path}")

    return tokens


if __name__ == "__main__":
    main()
