// Runs on Cloudflare Pages next to the static site (build.py copies it to site/_worker.js).
// It serves the site's files and handles one extra address, /api/subscribe, which adds
// an email sign-up to Sender. The Sender key is never in this file: it is read from the
// Pages secret SENDER_API_TOKEN (Settings > Variables and Secrets).

const GROUPS = __GROUPS__; // filled in by build.py from "_sender_groups" in checkout.json
const DOWNLOADS = __DOWNLOADS__; // filled in by build.py from "_downloads" in checkout.json
const FROM = { email: "trey@tarrywithme.com", name: "Trey Walters" };

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

const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// Emails the download link for a free resource. Returns true when Sender accepted it.
async function sendDownload(env, email, item, link) {
  const title = esc(item.title);
  const html = `<div style="font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:1.6;color:#0d2a2a;max-width:560px;margin:0 auto;padding:24px">
<p>Hi,</p>
<p>Thank you for asking for <strong>${title}</strong>. Your free copy is ready.</p>
<p style="margin:28px 0"><a href="${link}" style="background:#1f3989;color:#ffffff;text-decoration:none;padding:14px 26px;border-radius:4px;font-weight:bold;display:inline-block">Download your copy</a></p>
<p>If the button doesn't work, copy this link into your browser:<br><a href="${link}">${link}</a></p>
<p>I pray it helps you. You'll also hear from me now and then with encouragement and new resources.</p>
<p>Trey Walters<br>The Restoration Movement</p>
</div>`;
  const text = `Hi,\n\nThank you for asking for ${item.title}. Your free copy is ready:\n${link}\n\nI pray it helps you.\n\nTrey Walters\nThe Restoration Movement`;
  const res = await fetch("https://api.sender.net/v2/message/send", {
    method: "POST",
    headers: {
      authorization: `Bearer ${env.SENDER_API_TOKEN}`,
      "content-type": "application/json",
      accept: "application/json",
    },
    body: JSON.stringify({ from: FROM, to: { email }, subject: `Your free copy: ${item.title}`, html, text }),
  });
  if (!res.ok) console.log("sender send error", res.status, (await res.text()).slice(0, 300));
  return res.ok;
}

async function subscribe(request, env) {
  const wantsJson = (request.headers.get("accept") || "").includes("application/json");
  const reply = (status, ok, message, link) => {
    if (wantsJson) return json(status, link ? { ok, message, link } : { ok, message });
    const more = link ? ` <a href="${link}">Download it here</a>.` : "";
    return page(status, ok ? "You're in" : "That didn't work", message + more);
  };

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
  const item = DOWNLOADS[tag];
  if (item) {
    const link = `${new URL(request.url).origin}/downloads/${item.file}`;
    if (await sendDownload(env, email, item, link)) {
      return reply(200, true, "Thank you. Your download is on its way to your inbox.");
    }
    // The email could not be sent, so hand the file over directly instead of leaving them waiting.
    return reply(200, true, "Thank you. Your download is ready.", link);
  }
  if (GROUPS[tag] && tag !== "newsletter") {
    return reply(200, true, "Thank you. Your copy will be emailed to you soon.");
  }
  return reply(200, true, "Thank you. You're on the list.");
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
