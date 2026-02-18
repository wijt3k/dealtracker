"""
DealTracker Scraper
Scrapes retour/outlet deals from:
1. Stekkerstore (Shopify JSON API)
2. MediaMarkt Outlet (OpenCart)
3. Bol.com Breezy Retourkansjes
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
import hashlib
from datetime import datetime

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'nl-NL,nl;q=0.9,en;q=0.8',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
}


def make_id(url, title):
    """Create a stable numeric ID from URL + title."""
    key = f"{url}{title}".encode('utf-8')
    return int(hashlib.md5(key).hexdigest()[:8], 16)


def parse_price(text):
    """Parse Dutch price strings like '€ 89,99' or '89.99' to float."""
    if not text:
        return None
    # Remove currency symbols and whitespace
    text = re.sub(r'[€$\s]', '', text)
    # Handle Dutch format: dots as thousands sep, comma as decimal
    # e.g. "1.299,99" → "1299.99"
    if ',' in text and '.' in text:
        text = text.replace('.', '').replace(',', '.')
    elif ',' in text:
        text = text.replace(',', '.')
    numbers = re.findall(r'\d+\.?\d*', text)
    return float(numbers[0]) if numbers else None


def guess_category(title):
    """Simple keyword-based category detection."""
    title_lower = title.lower()
    if any(k in title_lower for k in ['iphone', 'samsung galaxy', 'smartphone', 'gsm', 'telefon']):
        return 'smartphones'
    if any(k in title_lower for k in ['laptop', 'macbook', 'notebook', 'chromebook']):
        return 'laptops'
    if any(k in title_lower for k in ['ipad', 'tablet', 'e-reader', 'kindle']):
        return 'tablets'
    if any(k in title_lower for k in ['airpods', 'koptelefoon', 'headset', 'speaker', 'audio', 'oordopjes', 'soundbar']):
        return 'audio'
    if any(k in title_lower for k in ['playstation', 'xbox', 'nintendo', 'gaming', 'game', 'controller']):
        return 'gaming'
    if any(k in title_lower for k in ['stofzuiger', 'wasmachine', 'droger', 'koelkast', 'espresso', 'koffie', 'airfryer', 'magnetron', 'vaatwasser']):
        return 'huishouden'
    if any(k in title_lower for k in ['watch', 'smartwatch', 'fitbit', 'garmin']):
        return 'wearables'
    if any(k in title_lower for k in ['tv ', 'televisie', 'monitor', 'beamer']):
        return 'tv'
    return 'elektronica'


def guess_icon(category):
    icons = {
        'smartphones': '📱',
        'laptops': '💻',
        'tablets': '📱',
        'audio': '🎧',
        'gaming': '🎮',
        'huishouden': '🏠',
        'wearables': '⌚',
        'tv': '📺',
        'elektronica': '⚡',
    }
    return icons.get(category, '📦')


# ─────────────────────────────────────────────
# 1. STEKKERSTORE (Shopify JSON API)
# ─────────────────────────────────────────────
def scrape_stekkerstore():
    """
    Stekkerstore is a Shopify store. Shopify exposes a /products.json
    endpoint for any collection — no auth needed.
    """
    deals = []

    # Try multiple possible collection slugs
    base_urls = [
        'https://stekkerstore.nl/collections/tweedekans/products.json',
        'https://stekkerstore.nl/collections/refurbished/products.json',
        'https://stekkerstore.nl/collections/outlet/products.json',
        'https://stekkerstore.nl/collections/alle-producten/products.json',
    ]

    for base_url in base_urls:
        page = 1
        found_any = False

        while True:
            url = f"{base_url}?limit=250&page={page}"
            try:
                r = requests.get(url, headers=HEADERS, timeout=15)
                if r.status_code != 200:
                    break

                data = r.json()
                products = data.get('products', [])

                if not products:
                    break

                found_any = True

                for product in products:
                    try:
                        title = product.get('title', '').strip()
                        handle = product.get('handle', '')
                        link = f"https://stekkerstore.nl/products/{handle}"

                        variants = product.get('variants', [])
                        if not variants:
                            continue

                        variant = variants[0]
                        current_price = float(variant.get('price', 0) or 0)
                        compare_price = float(variant.get('compare_at_price') or 0)

                        # Only include if there's a meaningful discount
                        if current_price <= 0:
                            continue

                        if compare_price <= 0 or compare_price <= current_price:
                            compare_price = current_price

                        discount = round(((compare_price - current_price) / compare_price) * 100) if compare_price > current_price else 0

                        images = product.get('images', [])
                        image = images[0].get('src', '') if images else ''

                        available = any(v.get('available', False) for v in variants)
                        category = guess_category(title)

                        deals.append({
                            'id': make_id(link, title),
                            'title': title,
                            'currentPrice': round(current_price, 2),
                            'originalPrice': round(compare_price, 2),
                            'discount': discount,
                            'url': link,
                            'image': image,
                            'source': 'stekkerstore',
                            'sourceName': 'Stekkerstore',
                            'sourceLogo': '🔌',
                            'condition': 'Tweedekans',
                            'stock': 'Op voorraad' if available else 'Uitverkocht',
                            'badge': 'TWEEDEKANS',
                            'category': category,
                            'icon': guess_icon(category),
                            'scraped_at': datetime.now().isoformat(),
                        })

                    except Exception as e:
                        print(f"  Stekkerstore product error: {e}")
                        continue

                if len(products) < 250:
                    break
                page += 1
                time.sleep(1)

            except Exception as e:
                print(f"  Stekkerstore error ({url}): {e}")
                break

        if found_any:
            print(f"  ✓ Found {len(deals)} Stekkerstore deals from {base_url}")
            break

    return deals


# ─────────────────────────────────────────────
# 2. MEDIAMARKT OUTLET (OpenCart)
# ─────────────────────────────────────────────
def scrape_mediamarkt_outlet(max_pages=5):
    """
    MediaMarkt Outlet runs on OpenCart. Products are server-side rendered.
    URL pattern: /index.php?route=product/search&sort=p.date_added&order=DESC
    """
    deals = []
    seen_titles = set()

    for page_num in range(0, max_pages):
        start = page_num * 100
        url = (
            f"https://outlet.mediamarkt.nl/index.php"
            f"?route=product/search&search=&sort=p.date_added&order=DESC&limit=100&start={start}"
        )

        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                break

            soup = BeautifulSoup(r.text, 'lxml')

            # OpenCart product containers
            products = soup.select('.product-layout')
            if not products:
                products = soup.select('.product-thumb')

            if not products:
                print(f"  No products found on MM page {page_num + 1}, stopping.")
                break

            for product in products:
                try:
                    # Title + link
                    title_el = (
                        product.select_one('.caption h4 a') or
                        product.select_one('h4 a') or
                        product.select_one('.name a')
                    )
                    if not title_el:
                        continue

                    title = title_el.text.strip()

                    # Deduplicate (page sometimes shows items twice)
                    if title in seen_titles:
                        continue
                    seen_titles.add(title)

                    link = title_el.get('href', '')
                    if link and not link.startswith('http'):
                        link = 'https://outlet.mediamarkt.nl' + link

                    # Image
                    img_el = product.select_one('.image img')
                    image = ''
                    if img_el:
                        image = img_el.get('src') or img_el.get('data-src') or ''
                        if image and not image.startswith('http'):
                            image = 'https://outlet.mediamarkt.nl' + image

                    # Prices — OpenCart standard classes
                    price_old_el = product.select_one('.price-old')
                    price_new_el = (
                        product.select_one('.price-new') or
                        product.select_one('.price')
                    )
                    discount_el = product.select_one('.price-tax')

                    # Some MM Outlet items show discount in price-tax span
                    discount_text = discount_el.text.strip() if discount_el else ''
                    scraped_discount = None
                    if '%' in discount_text:
                        m = re.search(r'(\d+)%', discount_text)
                        if m:
                            scraped_discount = int(m.group(1))

                    original_price = parse_price(price_old_el.text if price_old_el else '')
                    current_price = parse_price(price_new_el.text if price_new_el else '')

                    if not current_price:
                        continue

                    if not original_price:
                        if scraped_discount and scraped_discount > 0:
                            original_price = round(current_price / (1 - scraped_discount / 100), 2)
                        else:
                            original_price = current_price

                    discount = scraped_discount if scraped_discount is not None else (
                        round(((original_price - current_price) / original_price) * 100)
                        if original_price > current_price else 0
                    )

                    category = guess_category(title)

                    deals.append({
                        'id': make_id(link, title),
                        'title': title,
                        'currentPrice': round(current_price, 2),
                        'originalPrice': round(original_price, 2),
                        'discount': discount,
                        'url': link,
                        'image': image,
                        'source': 'mediamarkt',
                        'sourceName': 'MediaMarkt Outlet',
                        'sourceLogo': '🔴',
                        'condition': 'Outlet',
                        'stock': 'Op voorraad',
                        'badge': 'OUTLET',
                        'category': category,
                        'icon': guess_icon(category),
                        'scraped_at': datetime.now().isoformat(),
                    })

                except Exception as e:
                    print(f"  MM product error: {e}")
                    continue

            print(f"  MM page {page_num + 1}: {len(products)} items")
            time.sleep(2)

        except Exception as e:
            print(f"  MediaMarkt error page {page_num}: {e}")
            break

    return deals


# ─────────────────────────────────────────────
# 3. BOL.COM BREEZY RETOURKANSJES
# ─────────────────────────────────────────────
def scrape_bol_breezy(max_pages=4):
    """
    Breezy Retourkansjes is a third-party seller on Bol.com.
    URL: /nl/nl/w/alle-artikelen-breezy-retourkansjes/916223/

    Price structure on listing page:
    - .promo-price = Breezy's actual (retour) selling price
    - .price--old or [data-test="reference-price"] = original new price
    - "Retourdeal voor X" badge also indicates original price
    """
    deals = []
    seen_ids = set()

    for page in range(1, max_pages + 1):
        url = (
            f"https://www.bol.com/nl/nl/w/alle-artikelen-breezy-retourkansjes/916223/"
            f"?sort=1&page={page}"
        )

        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code != 200:
                print(f"  Bol.com returned {r.status_code} on page {page}")
                break

            soup = BeautifulSoup(r.text, 'lxml')

            # Bol.com product items — try multiple selectors
            products = (
                soup.select('[data-test="product-item"]') or
                soup.select('.product-item--row') or
                soup.select('.js_product_list_item') or
                soup.select('[data-item-id]')
            )

            if not products:
                print(f"  No products on Bol page {page}, stopping.")
                break

            for product in products:
                try:
                    # Title
                    title_el = (
                        product.select_one('[data-test="product-title"]') or
                        product.select_one('.product-title') or
                        product.select_one('a[data-test="product-title-link"]') or
                        product.select_one('h3') or
                        product.select_one('h4')
                    )
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)

                    # Link
                    link_el = (
                        product.select_one('a[data-test="product-title-link"]') or
                        product.select_one('a.product-title') or
                        product.select_one('[data-test="product-title"]').find_parent('a') if product.select_one('[data-test="product-title"]') else None or
                        product.select_one('a')
                    )
                    link = ''
                    if link_el:
                        link = link_el.get('href', '')
                        if link and not link.startswith('http'):
                            link = 'https://www.bol.com' + link

                    # Deduplicate
                    deal_id = make_id(link, title)
                    if deal_id in seen_ids:
                        continue
                    seen_ids.add(deal_id)

                    # Image
                    img_el = product.select_one('[data-test="product-image"] img') or product.select_one('img')
                    image = ''
                    if img_el:
                        image = img_el.get('src') or img_el.get('data-src') or ''

                    # Prices — Breezy retour price is the "promo" price
                    # The reference/original price may be in price--old
                    price_el = (
                        product.select_one('[data-test="price-value"]') or
                        product.select_one('.promo-price') or
                        product.select_one('.price-block__highlight') or
                        product.select_one('[class*="price"]')
                    )
                    ref_price_el = (
                        product.select_one('[data-test="reference-price"]') or
                        product.select_one('.price--old') or
                        product.select_one('.price-block__old-price') or
                        product.select_one('[class*="price-old"]') or
                        product.select_one('[class*="was"]')
                    )

                    current_price = parse_price(price_el.get_text() if price_el else '')
                    original_price = parse_price(ref_price_el.get_text() if ref_price_el else '')

                    if not current_price:
                        continue

                    # Check for "Retourdeal voor X" text — this is the actual deal price
                    full_text = product.get_text()
                    retourdeal_match = re.search(r'[Rr]etourdeal\s+voor\s+([\d.,]+)', full_text)
                    if retourdeal_match:
                        retourdeal_price = parse_price(retourdeal_match.group(1))
                        if retourdeal_price and retourdeal_price < current_price:
                            # current_price on listing = new RRP, retourdeal_price = Breezy's price
                            original_price = current_price
                            current_price = retourdeal_price

                    if not original_price or original_price <= current_price:
                        original_price = current_price

                    discount = round(((original_price - current_price) / original_price) * 100) if original_price > current_price else 0

                    # Condition: "Retourdeal" items are returned goods
                    condition = 'Retour' if retourdeal_match else 'Gebruikt/Retour'
                    badge = 'RETOUR' if retourdeal_match else 'DEAL'

                    category = guess_category(title)

                    deals.append({
                        'id': deal_id,
                        'title': title,
                        'currentPrice': round(current_price, 2),
                        'originalPrice': round(original_price, 2),
                        'discount': discount,
                        'url': link,
                        'image': image,
                        'source': 'bol',
                        'sourceName': 'Breezy Retourkansjes',
                        'sourceLogo': '🛒',
                        'condition': condition,
                        'stock': 'Op voorraad',
                        'badge': badge,
                        'category': category,
                        'icon': guess_icon(category),
                        'scraped_at': datetime.now().isoformat(),
                    })

                except Exception as e:
                    print(f"  Bol product error: {e}")
                    continue

            print(f"  Bol page {page}: {len(products)} items")
            time.sleep(3)  # Be polite — Bol.com rate-limits aggressively

        except Exception as e:
            print(f"  Bol.com error page {page}: {e}")
            break

    return deals


# ─────────────────────────────────────────────
# DEAL SCORING (for sorting)
# ─────────────────────────────────────────────
def calculate_score(deal):
    """
    Score deals to sort best ones first.
    Factors: discount %, absolute saving, price tier.
    """
    discount = deal.get('discount', 0)
    current = deal.get('currentPrice', 0)
    original = deal.get('originalPrice', 0)
    saving = original - current

    score = discount * 2          # % discount is primary factor
    score += min(saving / 10, 20) # Absolute saving (capped at 20 pts)

    # Boost high-value electronics (more interesting deals)
    if current > 500:
        score += 8
    elif current > 200:
        score += 5
    elif current > 100:
        score += 3

    # Slight boost for Stekkerstore (they tend to have better retour quality)
    if deal.get('source') == 'stekkerstore':
        score += 2

    return score


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("=" * 50)
    print("🕷️  DealTracker Scraper")
    print(f"    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    all_deals = []

    # --- Stekkerstore ---
    print("\n[1/3] Scraping Stekkerstore...")
    stekker_deals = scrape_stekkerstore()
    all_deals.extend(stekker_deals)
    print(f"  → {len(stekker_deals)} deals")
    time.sleep(2)

    # --- MediaMarkt Outlet ---
    print("\n[2/3] Scraping MediaMarkt Outlet...")
    mm_deals = scrape_mediamarkt_outlet(max_pages=5)
    all_deals.extend(mm_deals)
    print(f"  → {len(mm_deals)} deals")
    time.sleep(2)

    # --- Bol.com Breezy ---
    print("\n[3/3] Scraping Bol.com Breezy Retourkansjes...")
    bol_deals = scrape_bol_breezy(max_pages=4)
    all_deals.extend(bol_deals)
    print(f"  → {len(bol_deals)} deals")

    # --- Filter & sort ---
    print(f"\n📊 Raw total: {len(all_deals)} deals")

    # Keep only deals with a real discount, and filter out sold-out items
    filtered = [
        d for d in all_deals
        if d.get('discount', 0) > 0
        and d.get('stock') != 'Uitverkocht'
    ]
    print(f"📊 After filtering (discount > 0): {len(filtered)} deals")

    # Sort by score
    filtered.sort(key=calculate_score, reverse=True)

    # Deduplicate by ID
    seen_ids = set()
    unique_deals = []
    for deal in filtered:
        if deal['id'] not in seen_ids:
            seen_ids.add(deal['id'])
            unique_deals.append(deal)

    print(f"✅ Final unique deals: {len(unique_deals)}")

    # Save
    output = {
        'updated_at': datetime.now().isoformat(),
        'total': len(unique_deals),
        'deals': unique_deals,
    }

    with open('deals.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n💾 Saved to deals.json")
    print("=" * 50)


if __name__ == '__main__':
    main()
