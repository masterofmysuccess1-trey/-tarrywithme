# tarrywithme.com

The website for The Restoration Movement (Trey Walters).

- `site/` is the finished website. This is the folder the hosting service publishes.
- `build.py` regenerates `site/` from the content in `_src/`, the styles in `style.css`
  and the payment links in `checkout.json`. Run `python3 build.py`.
- `checkout.json` holds the Stripe Payment Link for each paid product and the
  email sign-up address. Edit it, rebuild, and the buttons update.

## Email sign-ups

The sign-up boxes post to `/api/subscribe`, which `worker.js` handles on Cloudflare Pages
(`build.py` copies it to `site/_worker.js`). It adds the person to Sender, in the groups
listed under `_sender_groups` in `checkout.json`. The Sender key is not in this repository:
set it in the Pages project as a secret named `SENDER_API_TOKEN`. Until that secret exists,
the boxes reply "Sign-up isn't switched on yet".
