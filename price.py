import requests
from bs4 import BeautifulSoup
from woocommerce import API
import time
import re

# ================= تنظیمات (اینجا رو پر کن) =================
SITE_URL = "https://copygame.ir" 
CONSUMER_KEY = "ck_727bf4c39057093e5db814e9b32b23d5bace0a2b"
CONSUMER_SECRET = "cs_4586f7c1f482f25aff48aabadc16c997579986ba"

SOURCE_PRICE_SELECTOR = ".btn" 
# ============================================================

wcapi = API(
    url=SITE_URL,
    consumer_key=CONSUMER_KEY,
    consumer_secret=CONSUMER_SECRET,
    version="wc/v3",
    timeout=60
)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def clean_price(price_text):
    """تبدیل متن به عدد خالص"""
    if not price_text: return None
    digits = re.sub(r'[^\d]', '', str(price_text))
    if digits:
        return int(digits)
    return None

def fetch_source_data(url):
    """
    این تابع هم قیمت رو برمیگردونه هم وضعیت موجودی رو
    خروجی: (price, is_in_stock)
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            element = soup.select_one(SOURCE_PRICE_SELECTOR)
            
            if element:
                raw_text = element.get_text(strip=True)
                
                # 1. چک کردن کلمات کلیدی ناموجود بودن
                # لیست کلماتی که اگر در سایت حریف دیدیم یعنی کالا نیست
                out_of_stock_keywords = ['ناموجود', 'تمام شد', 'تماس بگیرید', 'unavailable', 'out of stock']
                
                for keyword in out_of_stock_keywords:
                    if keyword in raw_text:
                        return (None, False) # قیمت هیچی، موجودی: خیر

                # 2. چک کردن قیمت
                price = clean_price(raw_text)
                if price:
                    return (price, True) # قیمت داره، موجودی: بله
            else:
                print(f"Warning: Selector not found in {url}")
                
    except Exception as e:
        print(f"Error fetching {url}: {e}")
    
    return (None, None) # وضعیت نامشخص

def main():
    print("--- STARTING SMART SYNC (Price + Stock) ---")
    page = 1
    
    while True:
        try:
            products = wcapi.get("products", params={"per_page": 20, "page": page}).json()
        except Exception as e:
            print(f"Error connecting to WooCommerce: {e}")
            break

        if not products:
            break

        for product in products:
            p_id = product['id']
            p_name = product['name']
            
            source_url = None
            for meta in product['meta_data']:
                if meta['key'] == 'source_url':
                    source_url = meta['value']
                    break
            
            if source_url:
                print(f"Checking: {p_name}...", end=" ")
                
                # دریافت قیمت و وضعیت موجودی جدید
                new_price, is_in_stock = fetch_source_data(source_url)
                
                # دیتا برای آپدیت
                update_data = {}
                needs_update = False
                
                # --- سناریوی ۱: کالا موجود است ---
                if is_in_stock == True and new_price and new_price > 10000:
                    current_price = int(product['regular_price']) if product['regular_price'] else 0
                    current_status = product['stock_status'] # instock یا outofstock
                    
                    # اگر قیمت عوض شده بود
                    if new_price != current_price:
                        update_data["regular_price"] = str(new_price)
                        print(f"[Price Change: {current_price} -> {new_price}]", end=" ")
                        needs_update = True
                    
                    # اگر قبلاً ناموجود بود، الان موجودش کن
                    if current_status != 'instock':
                        update_data["stock_status"] = "instock"
                        print("[Status: Now In Stock]", end=" ")
                        needs_update = True

                # --- سناریوی ۲: کالا ناموجود است ---
                elif is_in_stock == False:
                    current_status = product['stock_status']
                    
                    # اگر قبلاً موجود بود، الان ناموجودش کن
                    if current_status != 'outofstock':
                        update_data["stock_status"] = "outofstock"
                        print("[Status: Now Out of Stock]", end=" ")
                        needs_update = True
                
                # --- انجام آپدیت ---
                if needs_update:
                    wcapi.put(f"products/{p_id}", update_data)
                    print("-> UPDATED ✅")
                else:
                    print("-> No Change")
            
            time.sleep(1)

        page += 1

    print("--- SYNC COMPLETE ---")

if __name__ == "__main__":
    main()
