/**
 * DealTracker — Shared category-page logic
 * Each category page only needs to define: SLUG, CAT_NAME, CAT_ICON, INTRO_TEXT
 * Then include this file.
 */

const CAT_ICONS = {laptops:'💻',smartphones:'📱',audio:'🎧',gaming:'🎮',tv:'📺',tablets:'📟',wearables:'⌚',camera:'📷',huishouden:'🏠'};
const OUTLET_LABELS = ['Outlet','Retour','Tweedekans','Buitenkansje','Refurbished'];

// ── HTML escaping ────────────────────────────────────────────
function escapeHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Mobile menu ──────────────────────────────────────────────
function toggleMobileMenu() {
  document.getElementById('nav-hamburger').classList.toggle('open');
  document.getElementById('nav-mobile-menu').classList.toggle('open');
}
document.addEventListener('click', e => {
  const menu = document.getElementById('nav-mobile-menu');
  const btn  = document.getElementById('nav-hamburger');
  if (menu?.classList.contains('open') && !menu.contains(e.target) && !btn.contains(e.target)) {
    menu.classList.remove('open');
    btn.classList.remove('open');
  }
});

// ── Scoring ──────────────────────────────────────────────────
function dealScore(d) {
  const k = d.discount_percent || 0;
  const besparing = d.original_price && d.price ? (d.original_price - d.price) : 0;
  return besparing * 0.7 + k * 0.5 + (d.tweakers_price ? 25 : 0);
}

// ── Freshness label ──────────────────────────────────────────
function freshnessLabel(d) {
  const ts = d.first_seen || d.found_at || d.scraped_at;
  if (!ts) return '';
  try {
    const diffH = (Date.now() - new Date(ts).getTime()) / 3600000;
    if (diffH < 2)  return '<span class="deal-freshness today">🟢 Zojuist toegevoegd</span>';
    if (diffH < 24) return '<span class="deal-freshness today">🟢 Vandaag toegevoegd</span>';
    if (diffH < 48) return '<span class="deal-freshness yesterday">Gisteren</span>';
    const d2 = Math.floor(diffH / 24);
    if (d2 < 7) return `<span class="deal-freshness">${d2} dagen geleden</span>`;
  } catch {}
  return '';
}

// ── Card rendering ───────────────────────────────────────────
function renderCard(d) {
  const disc = d.discount_percent || 0;
  const besparing = d.original_price && d.price ? (d.original_price - d.price) : 0;
  const isVerified = !!(d.tweakers_price && d.tweakers_price > d.price);
  const isNew = d.first_seen && (Date.now() - new Date(d.first_seen).getTime()) < 86400000;
  const conditionIsOutlet = d.condition && OUTLET_LABELS.some(l => d.condition.includes(l));
  const isOutlet = !d.original_price;

  let badge = '';
  if (isNew)       badge = '<span class="badge badge-new">NIEUW</span>';
  else if (isVerified) badge = '<span class="badge badge-verified">✓ Geverifieerd</span>';
  else if (disc > 0)   badge = `<span class="badge badge-disc">−${disc}%</span>`;
  else if (isOutlet || conditionIsOutlet) badge = '<span class="badge badge-outlet">Outlet</span>';

  const icon     = CAT_ICONS[d.category] || '⚡';
  const safeId   = (d.id || '').replace(/'/g, '\\x27');
  const safeUrl  = (d.url || '').replace(/'/g, '%27');
  const safeTitle = escapeHtml(d.title || '');

  const besparingHtml = besparing > 0 ? `<span class="saving">−€${Math.round(besparing)}</span>` : '';
  const tweakersHtml = isVerified
    ? `<div class="tweakers-row">✓ Marktprijs €${d.tweakers_price.toFixed(0)} · bespaar €${(d.tweakers_price - d.price).toFixed(0)}</div>`
    : '';

  return `
  <div class="deal-card${isVerified ? ' verified' : ''}" onclick="viewDetail('${safeId}')">
    ${badge}
    <div class="deal-img-wrap">
      ${d.image ? `<img src="${d.image}" alt="${safeTitle.substring(0,60)}" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">` : ''}
      <div class="deal-img-placeholder" style="${d.image ? 'display:none' : ''}">${icon}</div>
    </div>
    <div class="deal-body">
      <div class="deal-source">${d.source || ''}</div>
      <div class="deal-title">${safeTitle}</div>
      ${freshnessLabel(d)}
      <div class="deal-price-row">
        <span class="price-now">€${(d.price || 0).toFixed(2)}</span>
        ${d.original_price ? `<span class="price-was">€${d.original_price.toFixed(0)}</span>` : '<span class="no-orig-label">outlet / retourprijs</span>'}
        ${besparingHtml}
      </div>
      ${tweakersHtml}
      <a class="deal-btn" href="${d.url || '#'}" target="_blank" rel="nofollow noopener" onclick="event.stopPropagation();trackClick(d)">Bekijk deal →</a>
    </div>
    ${isVerified ? '<div class="verified-strip"></div>' : ''}
  </div>`;
}

// ── Navigation helpers ───────────────────────────────────────
function viewDetail(id) {
  window.location.href = './deal.html?id=' + id;
}

function trackClick(deal) {
  if (typeof gtag === 'undefined') return;
  gtag('event', 'deal_click', {
    deal_source: deal?.source || '',
    deal_title: (deal?.title || '').substring(0, 100),
    deal_price: deal?.price || 0,
    deal_discount: deal?.discount_percent || 0,
    deal_category: typeof SLUG !== 'undefined' ? SLUG : '',
    deal_verified: !!(deal?.tweakers_price),
    currency: 'EUR',
    value: deal?.price || 0,
  });
}

// ── JSON-LD schema ───────────────────────────────────────────
function updateItemListSchema(deals) {
  const name = (typeof CAT_NAME !== 'undefined' ? CAT_NAME : 'Deal') + ' Deals';
  const items = deals.slice(0, 10).map((d, i) => ({
    "@type": "ListItem",
    "position": i + 1,
    "name": d.title || '',
    "url": d.url || '',
    "item": {
      "@type": "Product",
      "name": d.title || '',
      "offers": {
        "@type": "Offer",
        "price": d.price || 0,
        "priceCurrency": "EUR",
        "availability": "https://schema.org/InStock",
        "url": d.url || ''
      }
    }
  }));
  const el = document.getElementById('itemlist-schema');
  if (el) el.textContent = JSON.stringify({
    "@context": "https://schema.org",
    "@type": "ItemList",
    "name": name,
    "itemListElement": items
  });
}

// ── Skeleton cards HTML ──────────────────────────────────────
function skeletonHTML(count) {
  let s = '';
  for (let i = 0; i < (count || 12); i++) {
    s += `<div style="background:var(--card);border:1px solid var(--border);border-radius:12px;overflow:hidden">
      <div class="skel" style="height:130px;border-radius:0"></div>
      <div style="padding:.75rem .8rem;display:flex;flex-direction:column;gap:.5rem">
        <div class="skel" style="height:12px;width:60%"></div>
        <div class="skel" style="height:14px"></div>
        <div class="skel" style="height:12px;width:80%"></div>
      </div>
    </div>`;
  }
  return s;
}

// ── Boot ─────────────────────────────────────────────────────
async function boot() {
  const slug = typeof SLUG !== 'undefined' ? SLUG : '';
  const catName = typeof CAT_NAME !== 'undefined' ? CAT_NAME : slug;

  try {
    const res  = await fetch('./deals.json?t=' + Date.now());
    const data = await res.json();
    const all  = data.deals || [];
    const cat  = all.filter(d => d.category === slug).sort((a, b) => dealScore(b) - dealScore(a));
    const grid = document.getElementById('deals-grid');

    if (!cat.length) {
      grid.innerHTML = `<div class="empty-state"><h2>Geen ${catName} deals gevonden</h2><p>Probeer het later — deals worden dagelijks bijgewerkt.</p></div>`;
      document.getElementById('page-sub').textContent = 'Geen deals gevonden';
      return;
    }

    const top = cat.slice(0, 24);
    grid.innerHTML = top.map(d => renderCard(d)).join('');
    if (cat.length > 24) {
      document.getElementById('more-cta').style.display = 'block';
      const moreLink = document.querySelector('#more-cta .btn-more');
      if (moreLink) moreLink.href = `./deals.html?categorie=${slug}`;
    }

    document.getElementById('page-sub').textContent = `${cat.length} ${catName} deals · dagelijks bijgewerkt`;
    updateItemListSchema(top);
  } catch (e) {
    document.getElementById('page-sub').textContent = 'Deals laden mislukt.';
    console.warn(e);
  }
}

// Auto-start when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot);
} else {
  boot();
}
