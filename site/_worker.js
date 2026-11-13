// Runs on Cloudflare Pages next to the static site (build.py copies it to site/_worker.js).
// It serves the site's files and handles one extra address, /api/subscribe, which adds
// an email sign-up to Sender. The Sender key is never in this file: it is read from the
// Pages secret SENDER_API_TOKEN (Settings > Variables and Secrets).

const GROUPS = {
  "newsletter": "dJ2A0P",
  "free-chapter": "aK2BJY",
  "anger-is-costing-you-more-than-you-think-master-your-emotions-and-take-back-control-of-your-life": "dL2DKA",
  "identifying-red-flags-in-dating": "aM2gL5",
  "the-covenant-breaker-prayers-and-psalms-to-break-marine-covenants-and-get-free-from-porn-masturbation-and-sexual-dreams": "dN2jMp"
}; // filled in by build.py from "_sender_groups" in checkout.json

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

function json(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
}

function page(status, heading, text) {
  const html = `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${heading}</title><link rel="stylesheet" href="/style.css">
<main class="sec narrow"><div class="wrap center"><h1>${heading}</h1><p>${text}</p>
<p><a class="btn" href="/">Back to the site</a></p></div></main>`;
  return new Response(html, { status, headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" } });
}

async function subscribe(request, env) {
  const wantsJson = (request.headers.get("accept") || "").includes("application/json");
  const reply = (status, ok, message) =>
    wantsJson ? json(status, { ok, message }) : page(status, ok ? "You're in" : "That didn't work", message);

  let data;
  try {
    data = await request.formData();
  } catch {
    return reply(400, false, "Please enter your email address and try again.");
  }
  const email = String(data.get("email") || "").trim().toLowerCase();
  const tag = String(data.get("tag") || "newsletter");

  // "website" is a hidden box real visitors never see; only automated spam fills it in.
  if (data.get("website")) return reply(200, true, "Thank you. Check your inbox.");
  if (!EMAIL.test(email) || email.length > 254) {
    return reply(400, false, "That email address doesn't look right. Please check it and try again.");
  }
  if (!env.SENDER_API_TOKEN) {
    return reply(503, false, "Sign-up isn't switched on yet. Please try again soon.");
  }

  const groups = [...new Set([GROUPS.newsletter, GROUPS[tag]].filter(Boolean))];
  const res = await fetch("https://api.sender.net/v2/subscribers", {
    method: "POST",
    headers: {
      authorization: `Bearer ${env.SENDER_API_TOKEN}`,
      "content-type": "application/json",
      accept: "application/json",
    },
    body: JSON.stringify({ email, groups, trigger_automation: true }),
  });
  if (!res.ok) {
    console.log("sender error", res.status, (await res.text()).slice(0, 300));
    return reply(502, false, "Something went wrong on our side. Please try again in a moment.");
  }
  const free = tag !== "newsletter" && tag !== "footer" && GROUPS[tag];
  return reply(200, true, free ? "Thank you. Your download is on its way to your inbox." : "Thank you. You're on the list.");
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/api/subscribe") {
      if (request.method !== "POST") return json(405, { ok: false, message: "Use POST." });
      return subscribe(request, env);
    }
    return env.ASSETS.fetch(request);
  },
};
