import os
import base64
import json
import requests
import streamlit as st
from google import genai
from PIL import Image
from io import BytesIO
from serpapi import GoogleSearch
import tempfile
from gradio_client import Client, file as gr_file
from dotenv import load_dotenv
import time

load_dotenv()

import time

PERFECTCORP_API_KEY = os.environ.get("PERFECTCORP_API_KEY", "")
PERFECTCORP_BASE_URL = "https://yce-api-01.makeupar.com"

def perfectcorp_headers():
    if not PERFECTCORP_API_KEY:
        raise RuntimeError("Missing PERFECTCORP_API_KEY in environment variables.")
    return {
        "Authorization": f"Bearer {PERFECTCORP_API_KEY}",
        "Content-Type": "application/json",
    }

def create_perfectcorp_tryon_task(person_url: str, outfit_url: str) -> str:
    payload = {
        "src_file_url": person_url,
        "ref_file_url": outfit_url,
        "garment_category": "full_body",   # try "auto" if needed
        "change_shoes": True,
        "filter_multi_person": "normal",
    }

    resp = requests.post(
        f"{PERFECTCORP_BASE_URL}/s2s/v2.0/task/cloth-v4",
        headers=perfectcorp_headers(),
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["data"]["task_id"]

def poll_perfectcorp_tryon_result(task_id: str, timeout_s: int = 180, interval_s: int = 5) -> str:
    end_time = time.time() + timeout_s

    while time.time() < end_time:
        resp = requests.get(
            f"{PERFECTCORP_BASE_URL}/s2s/v2.0/task/cloth-v4/{task_id}",
            headers=perfectcorp_headers(),
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        status = data.get("task_status")

        if status == "success":
            return data["results"]["url"]

        if status == "error":
            raise RuntimeError(data.get("error") or "Perfect Corp try-on failed")

        time.sleep(interval_s)

    raise TimeoutError("Perfect Corp try-on timed out")

# ======================================================
# ENV
# ======================================================


# ======================================================
# CONFIG
# ======================================================

SERP_API_KEY = os.getenv("SERP_API_KEY")
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CLOUDFLARE_WORKER_URL = "https://ai-fashion-worker.amoghkrishana.workers.dev"
HF_TOKEN = os.environ.get("HF_TOKEN", "")


# ======================================================
# PAGE SETUP
# ======================================================

st.set_page_config(
    page_title="AI Fashion Assistant",
    page_icon="👗",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ======================================================
# CSS
# ======================================================

def load_css():
    css_path = "assets/style.css"
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()

# ======================================================
# SESSION STATE
# ======================================================

if "generated_ready" not in st.session_state:
    st.session_state.generated_ready = False

if "show_tryon_dialog" not in st.session_state:
    st.session_state.show_tryon_dialog = False

if "tryon_result_url" not in st.session_state:
    st.session_state.tryon_result_url = None

if "tryon_result_image" not in st.session_state:
    st.session_state.tryon_result_image = None

# ======================================================
# HELPERS
# ======================================================

def upload_to_imgbb(image: Image.Image) -> str:
    buffered = BytesIO()
    image.save(buffered, format="PNG")

    image_b64 = base64.b64encode(buffered.getvalue()).decode()

    response = requests.post(
        "https://api.imgbb.com/1/upload",
        data={
            "key": IMGBB_API_KEY,
            "image": image_b64,
        },
        timeout=60
    )
    response.raise_for_status()
    return response.json()["data"]["url"]


def google_lens_search(image_url: str) -> dict:
    params = {
        "engine": "google_lens",
        "url": image_url,
        "hl": "en",
        "country": "in",
        "api_key": SERP_API_KEY,
    }

    response = requests.get(
        "https://serpapi.com/search",
        params=params,
        timeout=60
    )
    response.raise_for_status()
    return response.json()


def get_numeric_price(product: dict):
    price = product.get("price")
    if not isinstance(price, dict):
        return None

    currency = str(price.get("currency", "")).upper()
    if currency not in ["₹", "INR"]:
        return None

    value = price.get("extracted_value")
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def search_site(product, site):
    params = {
        "engine": "google",
        "q": f"site:{site} {product}",
        "api_key": SERP_API_KEY,
        "gl": "in",
        "hl": "en",
    }

    search = GoogleSearch(params)
    results = search.get_dict()
    return results.get("organic_results", [])


client = genai.Client(api_key=GEMINI_API_KEY)

# ======================================================
# TRY-ON DIALOG
# ======================================================



@st.dialog("Try On This Look", width="small")
def try_on_dialog():
    st.markdown("### Upload your photo")
    st.caption("Upload a clear full-body or upper-body photo for best results.")

    user_photo = st.file_uploader(
        "Upload your photo",
        type=["jpg", "jpeg", "png"],
        label_visibility="collapsed",
        key="tryon_user_upload"
    )

    if user_photo is not None:
        user_image = Image.open(user_photo).convert("RGB")
        st.image(user_image, caption="Your Photo", use_container_width=True)

    with st.expander("Sample images", expanded=False):
        c1, c2 = st.columns(2)
        example_files = [
            "assets/examples/sample1.png",
            "assets/examples/sample2.png",
        ]
        for col, path in zip([c1, c2], example_files):
            with col:
                if os.path.exists(path):
                    st.image(path, use_container_width=True)
                else:
                    st.info("Sample missing")

    st.markdown("### Main outfit preview")
    st.image(
        st.session_state.images[0],
        caption="Main Outfit",
        use_container_width=True
    )
    b1, b2 = st.columns(2)

    with b1:
        if st.button("Cancel", use_container_width=True, key="tryon_cancel"):
            st.session_state.show_tryon_dialog = False
            st.session_state.tryon_result_url = None
            st.session_state.tryon_result_image = None
            st.rerun()

    with b2:
        if st.button("Run Try-On", use_container_width=True, key="tryon_run"):
            if user_photo is None:
                st.warning("Please upload your photo first.")
            else:
                with st.spinner("Creating virtual try-on..."):
                    try:
                        person_image = Image.open(user_photo).convert("RGB")
                        outfit_image = st.session_state.images[0].convert("RGB")

                        person_url = upload_to_imgbb(person_image)
                        outfit_url = upload_to_imgbb(outfit_image)

                        task_id = create_perfectcorp_tryon_task(person_url, outfit_url)
                        result_url = poll_perfectcorp_tryon_result(task_id)

                        st.session_state.tryon_result_url = result_url
                        st.session_state.tryon_result_image = None
                    except Exception as e:
                        st.error("Try-on failed.")
                        st.exception(e)

    if st.session_state.tryon_result_url:
        st.markdown("### Virtual Try-On Result")
        st.image(
            st.session_state.tryon_result_url,
            caption="Virtual Try-On Result",
            use_container_width=True
        )
        try:
            img_bytes = requests.get(st.session_state.tryon_result_url, timeout=60).content
            st.download_button(
                "⬇ Download Try-On Result",
                data=img_bytes,
                file_name="tryon_result.png",
                mime="image/png",
                use_container_width=True
            )
        except Exception:
            st.caption("Download unavailable for this result URL.")


# ======================================================
# HERO
# ======================================================

st.markdown("""
<div class="hero">
    <div class="hero-content">
        <h1><span style="color:#e60023;">👗</span> AI Fashion Assistant</h1>
        <p>Design • Visualize • Compare • Shop</p>
    </div>
</div>
""", unsafe_allow_html=True)

# ======================================================
# INPUT CARD
# ======================================================

st.markdown("""
<div class="card">
    <h2 style="text-align:center;">👤 User Preferences</h2>
    <p style="text-align:center;color:#666;">
        Describe your dream outfit and let AI create a premium fashion concept.
    </p>
</div>
""", unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    gender = st.selectbox("👤 Gender", ["Male", "Female", "Unisex"])

with col2:
    style = st.selectbox(
        "✨ Fashion Style",
        ["Streetwear", "Casual", "Luxury", "Minimal", "Formal", "Sportswear", "Anime", "Vintage"]
    )

budget_pref = st.select_slider(
    "💰 Budget Preference",
    options=["₹1000", "₹2000", "₹3000", "₹5000", "₹10000+"],
    value="₹3000"
)

prompt = st.text_area(
    "📝 Describe Your Dream Outfit",
    height=180,
    placeholder="Example: Design a black oversized hoodie with anime and cargo pants."
)

generate = st.button("✨ Generate Premium Outfit", use_container_width=True)

# ======================================================
# GENERATE
# ======================================================

if generate:
    if prompt.strip() == "":
        st.warning("Please describe your outfit.")
        st.stop()

    progress = st.progress(0)
    status = st.empty()

    status.info("🧠 Understanding your fashion idea...")
    progress.progress(15)

    response = client.models.generate_content(
        model="models/gemini-3.5-flash-lite",
        contents=f"""
You are an expert AI Fashion Designer.

Return ONLY valid JSON.
Do NOT return markdown.
Do NOT return explanation.

JSON format:
{{
  "outfit_name": "",
  "outfit_description": "",
  "top_wear": "",
  "bottom_wear": "",
  "footwear": "",
  "colors": "",
  "alternate_color": "",
  "accessories": "",
  "reason": "",
  "estimated_budget": "₹2,500–₹3,500",
  "best_occasion": "",
  "best_season": "",
  "style_rating": ""
}}

User Prompt:
{prompt}

Gender:
{gender}

Fashion Style:
{style}

Budget Preference:
{budget_pref}

Important:
- Accessories must match the outfit style, colors, and theme.
- Keep accessories short and practical, so they can be generated as a separate image.
"""
    )

    try:
        data = json.loads(response.text)
        status.info("🎨 Designing premium outfit...")
        progress.progress(35)
    except Exception:
        st.error("Gemini returned invalid JSON.")
        st.code(response.text)
        st.stop()

    outfit_name = data.get("outfit_name", "")
    description = data.get("outfit_description", "")
    top = data.get("top_wear", "")
    bottom = data.get("bottom_wear", "")
    footwear = data.get("footwear", "")
    colors = data.get("colors", "")
    alternate_color = data.get("alternate_color", "")
    accessories = data.get("accessories", "")
    budget = data.get("estimated_budget", "")
    occasion = data.get("best_occasion", "")
    season = data.get("best_season", "")
    rating = data.get("style_rating", "")
    reason = data.get("reason", "")

    outfit_prompt = f"""
Premium clothing product photography.

Create only the main outfit.

Gender: {gender}
Top: {top}
Bottom: {bottom}
Footwear: {footwear}
Outfit Colors: {colors}

Rules:
- Show only top, bottom, and footwear.
- Do NOT show accessories in this image.
- Plain white background.
- No human.
- No model.
- No mannequin.
- Ultra realistic.
- Fashion catalog photography.
- Highly detailed.
- Professional e-commerce product photo.
- 4K.
"""

    accessory_prompt = f"""
Premium fashion accessory product photography.

Create only the matching accessories for this outfit.

Gender: {gender}
Style: {style}
Outfit Colors: {colors}
Accessories: {accessories}

Rules:
- Accessories must match the outfit style and color palette.
- Keep accessories coordinated with the outfit.
- Plain white background.
- Flay lay.
- No human.
- No model.
- No mannequin.
- Ultra realistic.
- Fashion catalog photography.
- Highly detailed.
- Professional e-commerce product photo.
- 4K.
"""

    status.info("🖼 Rendering AI fashion images...")
    progress.progress(60)

    images = []

    with st.spinner("Generating AI outfit image..."):
        for current_prompt in [outfit_prompt, accessory_prompt]:
            payload = {"prompt": current_prompt}

            try:
                response = requests.post(
                    CLOUDFLARE_WORKER_URL,
                    json=payload,
                    timeout=180
                )

                if response.status_code != 200:
                    st.error("Cloudflare Worker Error")
                    st.code(response.text)
                    st.stop()

                result = response.json()

                if "image" not in result:
                    st.error("No image returned from Cloudflare.")
                    st.write(result)
                    st.stop()

                image_bytes = base64.b64decode(result["image"])
                img = Image.open(BytesIO(image_bytes)).convert("RGB")
                images.append(img)
                progress.progress(80)

            except Exception as e:
                st.error("Image generation failed.")
                st.exception(e)
                st.stop()

    if len(images) != 2:
        st.error("Unable to generate two outfit designs.")
        st.stop()

    image_url = upload_to_imgbb(images[0])

    status.info("🔍 Searching similar fashion products...")
    progress.progress(90)

    lens_results = google_lens_search(image_url)
    progress.progress(100)

    st.session_state.generated_ready = True
    st.session_state.images = images
    st.session_state.outfit_name = outfit_name
    st.session_state.description = description
    st.session_state.top = top
    st.session_state.bottom = bottom
    st.session_state.footwear = footwear
    st.session_state.colors = colors
    st.session_state.alternate_color = alternate_color
    st.session_state.accessories = accessories
    st.session_state.budget = budget
    st.session_state.occasion = occasion
    st.session_state.season = season
    st.session_state.rating = rating
    st.session_state.reason = reason
    st.session_state.lens_results = lens_results

    st.success("✅ Outfit Generated Successfully!")
    progress.empty()

# ======================================================
# RENDER RESULTS
# ======================================================

if st.session_state.generated_ready:
    st.divider()

    st.markdown("""
    <div class="card">
        <h2 style="text-align:center;">
            🎨 AI Generated Designs
        </h2>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <style>
    .outfit-wrap{
        position: relative;
    }
    .tryon-badge {
        position: absolute;
        top: 14px;
        left: 14px;
        z-index: 20;
        width: fit-content;
    }
    .tryon-badge button {
        background: rgba(255,255,255,.98) !important;
        color: #111 !important;
        border: none !important;
        border-radius: 2px !important;
        font-size: 9px !important;
        font-weight: 800 !important;
        padding: 0.18rem 0.42rem !important;
        min-height: 22px !important;
        box-shadow: 0 3px 10px rgba(0,0,0,.15) !important;
    }
    </style>
    """, unsafe_allow_html=True)

    left_col, right_col = st.columns([4.8, 4.8], gap="large")

    with left_col:
        st.markdown('<div class="outfit-wrap">', unsafe_allow_html=True)

        st.image(
            st.session_state.images[0],
            caption=f"Main Outfit • {st.session_state.colors}",
            use_container_width=True
        )

        st.markdown('<div class="tryon-badge">', unsafe_allow_html=True)
        if st.button("✦ TRY ON THIS LOOK", key="tryon_btn"):
            st.session_state.show_tryon_dialog = True
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

    with right_col:
        st.image(
            st.session_state.images[1],
            caption=f"Matching Accessories • {st.session_state.accessories}",
            use_container_width=True
        )

    if st.session_state.show_tryon_dialog:
        try_on_dialog()

    col1, col2 = st.columns(2)

    with col1:
        buffer = BytesIO()
        st.session_state.images[0].save(buffer, format="PNG")
        st.download_button(
            "⬇ Download Original",
            buffer.getvalue(),
            "original_design.png",
            "image/png",
            use_container_width=True
        )

    with col2:
        buffer2 = BytesIO()
        st.session_state.images[1].save(buffer2, format="PNG")
        st.download_button(
            "⬇ Download Accessories",
            buffer2.getvalue(),
            "accessories.png",
            "image/png",
            use_container_width=True
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("---")

    st.subheader("👗 Outfit Name")
    st.write(st.session_state.outfit_name)

    st.subheader("🎨 Color Palette")
    st.write(st.session_state.colors)

    st.subheader("💰 Estimated Budget")
    st.success(st.session_state.budget)

    st.subheader("⭐ Style Rating")
    st.info(st.session_state.rating)

    st.subheader("🎉 Best Occasion")
    st.write(st.session_state.occasion)

    st.subheader("🌤 Best Season")
    st.write(st.session_state.season)

    st.divider()

    st.subheader("👕 Top Wear")
    st.write(st.session_state.top)

    st.subheader("👖 Bottom Wear")
    st.write(st.session_state.bottom)

    st.subheader("👟 Footwear")
    st.write(st.session_state.footwear)

    st.subheader("⌚ Accessories")
    st.write(st.session_state.accessories)

    with st.expander("📖 Outfit Description"):
        st.write(st.session_state.description)

    with st.expander("💡 Why This Outfit Suits You"):
        st.write(st.session_state.reason)

    st.subheader("🛒 Similar Products Found")

    visual_matches = st.session_state.lens_results.get("visual_matches", [])

    priced_products = []
    unpriced_products = []

    for product in visual_matches[:8]:
        numeric_price = get_numeric_price(product)
        product = product.copy()
        product["numeric_price"] = numeric_price

        if numeric_price is not None:
            priced_products.append(product)
        else:
            unpriced_products.append(product)

    st.divider()

    priced_products.sort(key=lambda product: product["numeric_price"])
    sorted_products = priced_products + unpriced_products

    if not sorted_products:
        st.warning("No relevant products found.")
    else:
        for index, product in enumerate(sorted_products[:8], start=1):
            with st.container(border=True):
                product_image = product.get("thumbnail") or product.get("image")

                if product_image:
                    st.image(product_image, width=220)
                else:
                    st.info("Product image unavailable")

                st.markdown(f"### {index}. {product.get('title', 'Product')}")

                if product.get("source"):
                    st.write(f"🏪 **{product['source']}**")

                numeric_price = product.get("numeric_price")

                if numeric_price is not None:
                    st.markdown(
                        f"""
                        <div class="price-tag">
                            ₹{numeric_price:,.0f}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                else:
                    st.caption("Price unavailable")

                if product.get("rating"):
                    st.write(
                        f"⭐ {product['rating']} ({product.get('reviews', 0)} reviews)"
                    )

                if product.get("link"):
                    st.link_button(
                        "🛒 View Product",
                        product["link"],
                        use_container_width=True
                    )

    st.success("✅ Your AI Fashion Design is Ready!")
    st.balloons()