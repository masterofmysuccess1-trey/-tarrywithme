# tarrywithme.com

The website for The Restoration Movement (Trey Walters).

- `site/` is the finished website. This is the folder the hosting service publishes.
- `build.py` regenerates `site/` from the content in `_src/`, the styles in `style.css`
  and the payment links in `checkout.json`. Run `python3 build.py`.
- `checkout.json` holds the Stripe Payment Link for each paid product and the
  email sign-up address. Edit it, rebuild, and the buttons update.
