#!/usr/bin/env python3
"""Builds the static tarrywithme.com site into ./site from the content in ./_src.

Usage:  python3 build.py            (clean URLs, for real hosting)
        python3 build.py --preview  (links end in .html, for opening files directly)
"""
import hashlib, html, io, json, os, re, shutil, subprocess, sys
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "_src")
OUT = os.path.join(ROOT, "site")
CACHE = os.path.join(SRC, "img-cache")
ARTIFACT = "--artifact" in sys.argv
PREVIEW = "--preview" in sys.argv or ARTIFACT
if ARTIFACT:
    OUT = os.path.join(ROOT, "preview")
OLD_HOSTS = ("https://www.tarrywithme.com", "https://treywalters.podia.com")

pages = json.load(open(os.path.join(SRC, "pages.json")))
posts_meta = json.load(open(os.path.join(SRC, "posts.json")))
checkout = json.load(open(os.path.join(ROOT, "checkout.json")))

SITE_NAME = "Tarry With Me"
TAGLINE = "Helping You Rise from the Valley"
# Free-consultation booking link, set in checkout.json under "_booking_url". Left empty, the link is not shown.
BOOKING_URL = checkout.get("_booking_url") or ""
SOCIALS = [("Facebook", "https://web.facebook.com/trey.walters.2025"), ("Instagram", "https://www.instagram.com/masterofmysuccess"),
           ("TikTok", "https://www.tiktok.com/@trey.walters")]
# Product names as they read in Podia after the November 2026 clean-up.
NAME_FIX = {
    "OVERCOMING SEXUAL SIN": "Overcoming Sexual Sin",
    "The impossible prayer life": "The Impossible Prayer Life",
    "THE CONTROL TRAP: How To Recognize And Escape  A Jezebel Spirit At Home-Work-Church":
        "The Control Trap: How To Recognize And Escape A Jezebel Spirit At Home, Work And Church",
    "Anger Is Costing You More Than You Think MASTER YOUR EMOTIONS, AND TAKE BACK CONTROL OF YOUR LIFE":
        "Anger Is Costing You More Than You Think: Master Your Emotions And Take Back Control Of Your Life",
}
# Swap an old-site picture (by cache key) for a better one already in the cache.
IMG_SWAP = {
    "a67c186f65be": "9fab99a0a0f3",  # "The Restoration Movement" banner on Services -> Trey at his book table
}
# Real photos for the coaching products, which only had the logo as their picture.
PRODUCT_PHOTO = {
    "author-coaching": "cache:2cdd10032106",  # Trey with an author holding her finished book
    "mentorship": "cache:6519ca134280",       # Trey speaking
}
# Order of the books on the home page; the bundle leads because it is the best value.
BOOK_ORDER = ["freedom-bundle", "over-coming-sexual-sin", "water-spirits-the-hidden-force-behind-sexual-immorality",
              "the-impossible-prayer-life", "the-control-trap-how-to-recognize-and-escape-a-jezebel-spirit-at-home-work-church",
              "the-value-of-the-woman", "kingdom-income-how-i-went-from-homeless-to-building-wealth-god-s-way"]
FEATURED_ON = ["Sheena Power Talk", "The Dayelight Show", "Wise Worthy Woman (Best 100FM)",
               "Geared To Live Talk Show", "The Prophets Marketplace Podcast"]


PLACEHOLDERS = {"Text section", "You can add more detail in this subtitle", "Banner"}


def fixname(n):
    return NAME_FIX.get(n, n)


def brandfix(s):
    return re.sub(r"(?i)\bthe restoration movement\b", SITE_NAME, s or "")
NAV = [("Books", "#books"), ("My Book", "my-book"), ("Services", "services"),
       ("Blog", "blog"), ("Contact", "contact")]
# Podia's four sample posts are not Trey's writing; leave them behind.
SKIP_POSTS = {"blog-design-elements", "blog-post-checklist", "video-template", "podcast-template"}
# Buttons on the old site that still pointed at Podia placeholder addresses.
BUTTON_FIX = {"Request Mentoring": "mentorship", "Request Mentorship or Coaching": "mentorship",
              "Speaking Engagements": "contact", "Invite Trey to Speak": "contact"}

e = html.escape
depth = 0  # folder depth of the page being rendered


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


POST_SLUGS = {}
for p in posts_meta:
    old = p["button"]["url"].split("/")[-1]
    if old not in SKIP_POSTS:
        POST_SLUGS[old] = slugify(p["title"]) or old


def href(target):
    """Turn an old-site URL or internal path into a link that works on the new site."""
    if not target:
        return ""
    t = target.strip()
    for h in OLD_HOSTS:
        if t.startswith(h):
            t = t[len(h):] or "/"
    if t.startswith(("http", "mailto:", "tel:")):
        return t
    anchor = ""
    if "#" in t:
        t, anchor = t.split("#", 1)
        anchor = "#" + anchor
    t = t.strip("/")
    if t == "about":
        t = "my-book"
    if t.startswith("blog/"):
        t = "blog/" + POST_SLUGS.get(t[5:], t[5:])
    prefix = "../" * depth
    if t in ("", "homepage"):
        base = (prefix + "index.html") if PREVIEW else (prefix or "./")
    else:
        base = prefix + t + (".html" if PREVIEW else "")
    return base + anchor


# ---------- images ----------
os.makedirs(CACHE, exist_ok=True)
_img = {}


def img(url, width=1200):
    """Download (once), shrink and store an image; returns its path on the new site."""
    if not url or "podia.com/assets/graphics" in url:
        return None
    if url.startswith("//"):
        url = "https:" + url
    key = url[6:] if url.startswith("cache:") else hashlib.sha1(url.encode()).hexdigest()[:12]
    key = IMG_SWAP.get(key, key)
    name = f"{key}-{width}.jpg"
    dest = os.path.join(OUT, "img", name)
    if (url, width) not in _img:
        raw = os.path.join(CACHE, key)
        if not os.path.exists(raw) and not url.startswith("cache:"):
            subprocess.run(["curl", "-sSL", "-m", "60", "-A", "Mozilla/5.0", "-o", raw, url], check=True)
        try:
            im = Image.open(raw)
            if im.format == "SVG" or im.width < 2:
                raise ValueError("not a photo")
            if im.mode in ("RGBA", "LA", "P"):
                im = im.convert("RGBA")
                bg = Image.new("RGB", im.size, (255, 255, 255))
                bg.paste(im, mask=im.split()[-1])
                im = bg
            else:
                im = im.convert("RGB")
            if im.width > width:
                im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            im.save(dest, "JPEG", quality=82, optimize=True, progressive=True)
            _img[(url, width)] = (name, im.width, im.height)
        except Exception as ex:
            print("  ! image failed:", url[:70], ex)
            _img[(url, width)] = None
    r = _img[(url, width)]
    return None if r is None else ("../" * depth + "img/" + r[0], r[1], r[2])


def img_tag(url, alt="", width=1200, cls="", eager=False):
    r = img(url, width)
    if not r:
        return ""
    src, w, h = r
    return (f'<img src="{src}" alt="{e(alt or "")}" width="{w}" height="{h}"'
            f'{"" if eager else " loading=lazy"}{f" class={cls}" if cls else ""}>')


# ---------- rich text ----------
def rich(s):
    if not s:
        return ""
    s = brandfix(s)
    s = re.sub(r'\sclass="[^"]*"', "", s)
    s = re.sub(r'\sstyle="[^"]*"', "", s)
    s = re.sub(r'href="([^"]*)"', lambda m: f'href="{href(html.unescape(m.group(1)))}"', s)

    def swap(m):
        r = img(html.unescape(m.group(1)), 1100)
        return f'<img src="{r[0]}" alt="" width="{r[1]}" height="{r[2]}" loading="lazy">' if r else ""
    return re.sub(r'<img[^>]*src="([^"]*)"[^>]*>', swap, s)


def plain(s):
    return "".join(f"<p>{e(x.strip())}</p>" for x in (s or "").split("\n") if x.strip())


# ---------- section helpers ----------
def colors(p):
    v = ((p.get("theme") or {}).get("colors") or {}).get("values") or {}
    m = {"--bg": "sectionBackground", "--head": "heading2", "--text": "paragraphText",
         "--btn": "buttonBackground", "--btn-text": "buttonLabel", "--card": "cardBackground",
         "--card-text": "cardParagraphText", "--card-head": "cardHeading2", "--sub": "subtitle"}
    out = []
    for var, k in m.items():
        if v.get(k):
            c = v[k]
            out.append(f"{var}:{c[:7] if len(c) == 9 else c}")
    # Podia's teal default button clashes with the navy and gold brand; use navy.
    return ";".join(out).replace("--btn:#158C78", "--btn:#1f3989")


def button(b, cls="btn"):
    if not b or not (b.get("text") or "").strip():
        return ""
    text = b["text"].strip()
    url = b.get("url") or ""
    if text in BUTTON_FIX:
        url = "/" + BUTTON_FIX[text]
    if not url or url == "/" or "podia.com" in url or "example.com" in url:
        return ""
    ext = url.startswith("http") and not url.startswith(OLD_HOSTS)
    return f'<a class="{cls}" href="{e(href(url))}"{" target=_blank rel=noopener" if ext else ""}>{e(text)}</a>'


def heads(p, lvl=None, pre="preheading", head="heading", sub="subheading"):
    lvl = lvl or (p.get("headingLevel") if p.get("headingLevel") in ("1", "2", "3") else "2")
    o = ""
    p = {k: (brandfix(v) if isinstance(v, str) else v) for k, v in p.items()}
    for k in (pre, head, sub):  # Podia's unfilled template words
        if (p.get(k) or "").strip() in PLACEHOLDERS:
            p[k] = ""
    if p.get(pre):
        o += f'<p class="pre">{e(p[pre].strip())}</p>'
    if p.get(head):
        o += f'<h{lvl}>{e(p[head].strip())}</h{lvl}>'
    if p.get(sub):
        o += f'<p class="sub">{e(p[sub].strip())}</p>'
    return o


def section_header(p):
    h = p.get("header") or {}
    o = heads(h, "2", "pretitle", "title", "subtitle")
    return f'<div class="sec-head">{o}</div>' if o else ""


def wrap(p, inner, cls=""):
    return f'<section class="sec {cls}" style="{colors(p)}"><div class="wrap">{inner}</div></section>'


def items(d):
    vals = list(d.values()) if isinstance(d, dict) else list(d or [])
    return sorted(vals, key=lambda x: x.get("position") or 0)


def buttons(p):
    b = button(p.get("button")) + button(p.get("button2"), "btn ghost")
    sub = f'<p class="btn-sub">{e(p["buttonSubtext"])}</p>' if p.get("buttonSubtext") else ""
    return f'<div class="btns">{b}</div>{sub}' if b else ""


# ---------- section renderers ----------
def r_image(p, first=False):
    side = "left" if (p.get("mediaPlacement") or "").startswith("left") else "right"
    pic = img_tag(p.get("image"), p.get("imageAltText"), 1100, eager=first)
    body = f'<div class="copy">{heads(p, "1" if first else None)}{rich(p.get("text"))}{buttons(p)}</div>'
    if not pic:
        return wrap(p, body, "narrow lead" if first else "narrow")
    if first:
        return (f'<section class="sec lead"><div class="wrap"><div class="split {side}">'
                f'<div class="media framed">{pic}</div>{body}</div></div></section>')
    return wrap(p, f'<div class="split {side}"><div class="media">{pic}</div>{body}</div>')


def r_text(p, first=False):
    al = "center" if p.get("textAlignment") == "center" else "left"
    return wrap(p, f'<div class="copy {al}">{heads(p)}{rich(p.get("text"))}{buttons(p)}</div>', "narrow")


def r_cta(p, first=False):
    return wrap(p, f'<div class="copy center">{heads(p)}{buttons(p)}</div>', "narrow")


def product_slug(pr):
    return pr["buttons"]["primary"]["url"].rstrip("/").split("/")[-1]


def product_card(pr, badge=""):
    name = fixname(pr["names"].get("external") or pr["names"]["primary"])
    price = " · ".join(pr.get("prices", {}).values())
    if price in ("Free email delivery", "Free"):
        price = "Free"
    url = href(pr["buttons"]["primary"]["url"])
    photo = PRODUCT_PHOTO.get(product_slug(pr))
    if photo:
        pic = img_tag(photo, name, 700)
        price = price.replace("6 monthly payments of $300", "$300/mo for 6 months")
    else:
        pic = img_tag(pr["images"].get("external") or pr["images"].get("primary"), name, 600)
    badge_html = f'<span class="badge">{e(badge)}</span>' if badge else ""
    desc = (pr["descriptions"].get("external") or pr["descriptions"].get("primary") or "").split("\n")[0]
    if len(desc) > 150:
        desc = desc[:147].rsplit(" ", 1)[0] + "…"
    tag = pr["metadata"].get("type", "")
    tag = "1-on-1 coaching" if tag.lower().startswith("coaching") else tag
    more = "Learn more" if photo else ("Get it free" if price == "Free" else "See the book")
    return (f'<a class="card product{" has-photo" if photo else ""}{" featured" if badge else ""}" href="{e(url)}">'
            f'<div class="cover{" photo-fill" if photo else ""}">{badge_html}{pic}</div>'
            f'<div class="card-body"><p class="tag">{e(tag)}</p>'
            f'<h3>{e(name)}</h3><p class="desc">{e(desc)}</p>'
            f'<p class="price">{e(price)}<span class="more">{more} →</span></p></div></a>')


def r_products(p, first=False):
    prods = [x for x in items(p["products"]) if x.get("visible", True)]
    coaching = [x for x in prods if product_slug(x) in PRODUCT_PHOTO]
    free = [x for x in prods if not x.get("priceCents") and x not in coaching]
    books = [x for x in prods if x not in coaching and x not in free]
    order = {k: i for i, k in enumerate(BOOK_ORDER)}
    books.sort(key=lambda x: order.get(product_slug(x), 99))
    book_cards = "".join(product_card(x, "Best value" if product_slug(x) == "freedom-bundle" else "") for x in books)
    free_cards = "".join(product_card(x) for x in free)
    coach_cards = "".join(product_card(x) for x in coaching)
    consult = (f'<p class="center consult">Not sure which is right for you? <a href="{e(BOOKING_URL)}" target="_blank" '
               f'rel="noopener">Book a free consultation</a></p>') if BOOKING_URL else ""
    return (f'<section class="sec" id="books"><div class="wrap">{section_header(p)}'
            f'<div class="grid g3">{book_cards}</div></div></section>'
            f'<section class="sec tint" id="free"><div class="wrap"><div class="sec-head"><p class="pre">Start here</p>'
            f'<h2>Free Resources</h2><p class="sub">Not ready to buy? Start with one of these, sent straight to your inbox.</p></div>'
            f'<div class="grid g3">{free_cards}</div></div></section>'
            f'<section class="sec dark" id="work-with-trey"><div class="wrap"><div class="sec-head"><p class="pre">Go further, faster</p>'
            f'<h2>Work With Trey 1-on-1</h2><p class="sub">Books give you the steps. Coaching walks them with you, week after week.</p></div>'
            f'<div class="grid g2 coach">{coach_cards}</div>{consult}</div></section>')


def r_bundle(p, first=False):
    cards = "".join(product_card(x) for x in p.get("products") or [])
    return wrap(p, f'<div class="sec-head"><h2>What’s included</h2></div><div class="grid g3">{cards}</div>')


SOCIAL = {"facebook": "Facebook", "instagram": "Instagram", "tiktok": "TikTok", "youtube": "YouTube"}


def r_bio(p, first=False):
    pic = img_tag(p.get("avatar"), "Trey Walters", 700)
    soc = "".join(f'<a href="{e(s["value"])}" target="_blank" rel="noopener">{SOCIAL.get(s["service"], s["service"].title())}</a>'
                  for s in items(p.get("socialLinks") or {}))
    body = (f'<div class="copy">{heads(p, "2", "preheadline", "headline", "subheadline")}'
            f'{rich(p.get("description"))}<p class="social">{soc}</p></div>')
    return wrap(p, f'<div class="split left bio"><div class="media">{pic}</div>{body}</div>')


def r_grid(p, first=False):
    cols = items(p["columns"])
    cards = ""
    for c in cols:
        pic = img_tag(c.get("image"), c.get("imageAltText"), 700)
        txt = heads(c, "3") + rich(c.get("text")) + buttons(c)
        if pic and not txt:
            cards += f'<div class="photo">{pic}</div>'
        else:
            cards += f'<div class="card pad">{pic}{txt}</div>'
    n = min(len(cols), 4)
    return wrap(p, f'{section_header(p)}<div class="grid g{n}">{cards}</div>')


def r_testimonials(p, first=False):
    cards = ""
    for t in items(p["testimonials"]):
        per = t["person"]
        av = img_tag(per.get("avatar"), per.get("name"), 160, "avatar") or \
            f'<span class="avatar initial">{e((per.get("name") or "?")[:1])}</span>'
        label = f'<p class="tlabel">{e(t["website"]["label"])}</p>' if (t.get("website") or {}).get("label") else ""
        cards += (f'<figure class="card pad quote">{label}<blockquote>{rich(t["text"])}</blockquote>'
                  f'<figcaption>{av}<span>{e(per.get("name") or "")}</span></figcaption></figure>')
    n = min(len(items(p["testimonials"])), 3) or 1
    return wrap(p, f'{section_header(p)}<div class="grid g{n}">{cards}</div>')


def signup_form(btn="Subscribe", tag="newsletter"):
    action = checkout.get("_email_form_action") or ""
    if PREVIEW:
        action = ""  # previews are plain files with nothing behind them to receive a sign-up
    note = "" if action else '<p class="form-note">Sign-up will be connected to the new email service before launch.</p>'
    return (f'<form class="signup" method="post" action="{e(action)}" data-tag="{e(tag)}">'
            f'<input type="hidden" name="tag" value="{e(tag)}">'
            f'<input type="text" name="website" tabindex="-1" autocomplete="off" aria-hidden="true" class="hp">'
            f'<input type="email" name="email" placeholder="Your email address" aria-label="Email address" required>'
            f'<button class="btn" type="submit">{e(btn)}</button></form>{note}')


def r_newsletter(p, first=False):
    btn = (p.get("button") or {}).get("text") or "Subscribe"
    return wrap(p, f'<div class="copy center">{heads(p)}{rich(p.get("text"))}{signup_form(btn)}</div>', "narrow")


def r_links(p, first=False):
    cards = ""
    for l in items(p["links"]):
        ext = l["url"].startswith("http") and not l["url"].startswith(OLD_HOSTS)
        cards += (f'<a class="card pad link" href="{e(href(l["url"]))}"{" target=_blank rel=noopener" if ext else ""}>'
                  f'<h3>{e(l["heading"])}</h3><p>{e(l.get("text") or "")}</p></a>')
    return wrap(p, f'{section_header(p)}<div class="grid g4">{cards}</div>')


def r_faq(p, first=False):
    qs = "".join(f'<details><summary>{e(q["question"])}</summary>{rich(q["answer"])}</details>'
                 for q in items(p["questions"]))
    return wrap(p, f'{section_header(p)}<div class="faq">{qs}</div>', "narrow")


def buy_button(path, label):
    c = checkout.get(path) or {}
    kind = c.get("kind")
    if kind == "email":
        return signup_form(label, path)
    url = c.get("url") or f"https://www.tarrywithme.com/{path}"
    return f'<a class="btn big" href="{e(url)}">{e(label)}</a>'


def r_banner(p, first=False, path=""):
    name = fixname(p["names"].get("external") or p["names"]["primary"])
    custom = p.get("heading") and p["heading"] != "Banner"
    price = " · ".join(p.get("prices", {}).values())
    text = rich(p["text"].get("external")) or plain(p["text"].get("primary"))
    pic = (img_tag(PRODUCT_PHOTO.get(path), name, 900, eager=True)
           or img_tag(p["images"].get("external"), name, 900, eager=True)
           or img_tag(p["images"].get("primary"), name, 900, eager=True))
    label = (p.get("buttons", {}).get("checkout") or {}).get("text") or "Buy now"
    top = heads(p, "1") if custom else f"<h1>{e(name)}</h1>"
    meta = p.get("metadata", {})
    kind = (meta.get("type") or "").lower()
    tag = ("Ebook · Instant download" if kind == "download" else "1-on-1 coaching" if kind.startswith("coaching")
           else " · ".join(x for x in (meta.get("type"), meta.get("includedItems")) if x))
    sub = f'<p class="btn-sub">{e(p["buttonSubtext"])}</p>' if p.get("buttonSubtext") else ""
    body = (f'<div class="copy"><p class="pre">{e(tag)}</p>{top}{text}'
            f'<p class="price big">{e(price)}</p>{buy_button(path, label)}{sub}</div>')
    return wrap(p, f'<div class="split right"><div class="media cover-lg">{pic}</div>{body}</div>', "hero")


def r_toc(p, first=False):
    rows = ""
    for s in p.get("sections") or []:
        for b in s.get("blocks") or []:
            title = re.sub(r"\s*\(\d+\)(?=\.\w+$)", "", b["title"]).replace("_", " ")
            rows += f'<li><span>{e(title)}</span><span class="muted">{e(b.get("filesize") or "")}</span></li>'
    return wrap(p, f'<div class="sec-head left"><h2>What you get</h2></div><ul class="toc">{rows}</ul>', "narrow") if rows else ""


def r_membership(p, first=False):
    return wrap(p, '<div class="copy center"><p class="pre">Community</p><h1>The Tarry With Me Community</h1>'
                   '<p>A space where we walk through the process together, until healing comes, growth comes, '
                   'recovery comes, and advancement follows.</p>'
                   '<div class="btns"><a class="btn big" href="https://www.tarrywithme.com/p/join">Join the community</a></div></div>',
                "narrow hero")


RENDER = {"Image": r_image, "Text": r_text, "CallToAction": r_cta, "Products": r_products, "Bio": r_bio,
          "Grid": r_grid, "Testimonials": r_testimonials, "Newsletter": r_newsletter, "Links": r_links,
          "Faq": r_faq, "ProductTableOfContents": r_toc, "BundleTableOfContents": r_bundle,
          "MembershipBanner": r_membership}


FORM_JS = """<script>
document.querySelectorAll("form.signup").forEach(function (f) {
  var action = f.getAttribute("action");
  function say(text) {
    var n = f.nextElementSibling && f.nextElementSibling.classList.contains("form-note") ? f.nextElementSibling : f.parentNode.insertBefore(document.createElement("p"), f.nextSibling);
    n.className = "form-note shown";
    n.setAttribute("role", "status");
    n.textContent = text;
  }
  f.addEventListener("submit", function (ev) {
    ev.preventDefault();
    if (!action) { say("Sign-up is not connected yet. It will be linked to the new email service before launch."); return; }
    var btn = f.querySelector("button");
    btn.disabled = true;
    fetch(action, { method: "POST", body: new FormData(f), headers: { Accept: "application/json" } })
      .then(function (r) { return r.json(); })
      .then(function (d) { say(d.message); if (d.ok) f.reset(); })
      .catch(function () { say("Something went wrong. Please check your connection and try again."); })
      .then(function () { btn.disabled = false; });
  });
});
</script>"""


# ---------- page shell ----------
def shell(title, desc, body, path):
    nav = "".join(f'<a href="{e(href("/" + t) if not t.startswith("#") else href("/") + t)}">{e(n)}</a>' for n, t in NAV)
    canon = "https://www.tarrywithme.com/" + ("" if path == "index" else path)
    year_line = "© Trey Walters. All rights reserved."
    social = "".join(f'<a href="{e(u)}" target="_blank" rel="noopener">{e(n)}</a>' for n, u in SOCIALS)
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc or '')}">
<link rel="canonical" href="{e(canon)}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc or '')}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{e(SITE_NAME)}">
<meta property="og:image" content="https://www.tarrywithme.com/assets/og.jpg">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{'../' * depth}assets/icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Chivo:wght@700;800;900&family=Cinzel:wght@600;700&family=Livvic:ital,wght@0,400;0,600;1,400&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{'../' * depth}style.css">
</head>
<body>
<header class="top">
  <div class="wrap bar">
    <a class="brand" href="{e(href('/'))}"><img src="{'../' * depth}assets/icon.png" alt="" width="44" height="44"><span>{e(SITE_NAME)}</span></a>
    <input type="checkbox" id="menu" class="menu-toggle" aria-label="Open menu">
    <label for="menu" class="menu-btn" aria-hidden="true"><span></span><span></span><span></span></label>
    <nav>{nav}<a class="btn small" href="{e(href('/services'))}">Work With Trey</a></nav>
  </div>
</header>
<main>
{body}
</main>
<footer class="foot">
  <div class="wrap foot-grid">
    <div><img class="foot-logo" src="{'../' * depth}assets/logo-gold.png" alt="{e(SITE_NAME)}: {e(TAGLINE)}" width="240" height="116">
      <p>Faith-based books, mentorship and coaching from bestselling author Trey Walters.</p>
      <p class="foot-social">{social}</p><p class="small">{year_line}</p></div>
    <nav><a href="{e(href('/'))}">Home</a>{nav}</nav>
    <div><p class="foot-h">Join my email list</p>{signup_form('Subscribe', 'footer')}</div>
  </div>
</footer>
{FORM_JS}
</body>
</html>
"""
    if ARTIFACT and path == "index":
        css = open(os.path.join(ROOT, "style.css")).read()
        inner = page.split("<body>", 1)[1].split("</body>", 1)[0]
        fonts = re.search(r'<link href="https://fonts.googleapis[^>]*>', page).group(0)
        return (f'<title>Tarry With Me Site</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n'
                f'{fonts}\n<style>\n{css}</style>\n{inner}')
    return page


def write(path, content):
    full = os.path.join(OUT, path + ".html")
    os.makedirs(os.path.dirname(full), exist_ok=True)
    open(full, "w").write(content)


# ---------- build ----------
if os.path.exists(OUT):
    shutil.rmtree(OUT)
os.makedirs(OUT)
shutil.copy(os.path.join(ROOT, "style.css"), os.path.join(OUT, "style.css"))
shutil.copytree(os.path.join(ROOT, "assets"), os.path.join(OUT, "assets"))

for key, pg in pages.items():
    if key == "blog":
        continue
    path = "index" if key == "home" else key
    depth = 0
    body, first = "", True
    for c in pg["comps"]:
        n = c["c"].split("/")[-1]
        if n == "ProductBanner":
            body += r_banner(c["p"], True, key)
            first = False
        elif n in RENDER:
            body += RENDER[n](c["p"], first)
            first = False
    title = brandfix(fixname(pg["title"] or SITE_NAME))
    if path != "index" and SITE_NAME not in title and "Trey Walters" not in title:
        title += " | " + SITE_NAME
    if path == "index":
        body = body.replace("Break Free From Lust.", '<span class="hl">Break Free From Lust.</span>', 1)
        strip = "".join(f"<li>{e(x)}</li>" for x in FEATURED_ON)
        cut = body.find("</section>") + len("</section>")
        body = (body[:cut] + f'<section class="featured-strip"><div class="wrap"><p>As featured on</p><ul>{strip}</ul></div></section>'
                + body[cut:])
    write(path, shell(title, pg.get("meta"), body, path))

# blog
from bs4 import BeautifulSoup  # noqa: E402

cards, redirects = "", []
for p in posts_meta:
    old = p["button"]["url"].split("/")[-1]
    if old in SKIP_POSTS:
        continue
    slug = POST_SLUGS[old]
    soup = BeautifulSoup(open(os.path.join(SRC, "posts", old + ".html")).read(), "html.parser")
    content = ""
    for d in soup.select("[data-react-component]"):
        if d["data-react-component"].endswith("BlogPostContent"):
            content = json.loads(d["data-props"])["body"]
    depth = 1
    body = (f'<section class="sec narrow post"><div class="wrap"><p class="pre"><a href="{href("/blog")}">← All posts</a></p>'
            f'<h1>{e(p["title"])}</h1><p class="muted">{e(p["author"])} · {e(p["date"])}, 2026</p>'
            f'<div class="prose">{rich(content)}</div></div></section>')
    text = BeautifulSoup(content, "html.parser").get_text(" ", strip=True)
    excerpt = text[:155].rsplit(" ", 1)[0] + "…" if len(text) > 155 else text
    write("blog/" + slug, shell(f'{p["title"]} | Trey Walters', excerpt, body, "blog/" + slug))
    depth = 0
    first_img = re.search(r'<img[^>]*src="([^"]*)"', content)
    pic = img_tag(html.unescape(first_img.group(1)), p["title"], 700) if first_img else ""
    cards += (f'<a class="card product" href="{href("/blog/" + old)}"><div class="cover wide">{pic}</div>'
              f'<div class="card-body"><p class="tag">{e(p["date"])}, 2026</p><h3>{e(p["title"])}</h3>'
              f'<p class="desc">{e(excerpt)}</p></div></a>')
    redirects.append(f"/blog/{old} /blog/{slug} 301")

depth = 0
write("blog", shell("Blog | Trey Walters", "Teaching and encouragement from Trey Walters.",
                    f'<section class="sec"><div class="wrap"><div class="sec-head"><h1>Blog</h1>'
                    f'<p class="sub">Teaching and encouragement from Trey</p></div><div class="grid g3">{cards}</div></div></section>',
                    "blog"))

redirects += ["/about /my-book 301", "/homepage / 301"]
if not PREVIEW:
    # The sign-up handler that runs on Cloudflare Pages beside the static files.
    worker = open(os.path.join(ROOT, "worker.js")).read()
    worker = worker.replace("__GROUPS__", json.dumps(checkout.get("_sender_groups") or {}, indent=2))
    open(os.path.join(OUT, "_worker.js"), "w").write(worker)
open(os.path.join(OUT, "_redirects"), "w").write("\n".join(redirects) + "\n")
n = sum(len(f) for _, _, f in os.walk(OUT))
size = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(OUT) for f in fs)
print(f"built {n} files, {size / 1e6:.1f} MB -> {OUT}")
