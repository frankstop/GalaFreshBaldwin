from __future__ import annotations

from pathlib import Path
import shutil

from .analysis import build_daily_summary, build_weekly_summary
from .catalog_history import build_catalog_history
from .storage import write_json


STYLE = """
:root{color-scheme:light dark;--bg:#f5f7f2;--ink:#172217;--card:#fff;--accent:#276749;--muted:#5c685e;--border:#d9e1d7}*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 system-ui,sans-serif}header,main,footer{max-width:1100px;margin:auto;padding:1rem}
nav{display:flex;gap:1rem;flex-wrap:wrap}a{color:var(--accent)}.hero{padding:2rem 1rem}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:1rem}
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:1rem}.metric{font-size:1.8rem;font-weight:700}.muted{color:var(--muted)}
table{width:100%;border-collapse:collapse;background:var(--card)}th,td{text-align:left;padding:.6rem;border-bottom:1px solid var(--border)}input{width:100%;padding:.75rem;font:inherit}
.healthy{color:#18713c;font-weight:700}.gap{color:#8a4b08}@media(prefers-color-scheme:dark){:root{--bg:#101510;--ink:#edf5ed;--card:#172017;--border:#344034;--muted:#aab5aa}}
"""

COMMON_NAV = '<nav aria-label="Research reports"><a href="index.html">Overview</a><a href="daily-report.html">Daily</a><a href="weekly-report.html">Weekly</a><a href="catalog-history.html">Catalog history</a><a href="METHODOLOGY.html">Methodology</a></nav>'


def _page(title: str, body: str, script: str = "") -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><link rel="stylesheet" href="assets/site.css"></head><body><header>{COMMON_NAV}</header><main>{body}</main><footer><p>Independent, unaffiliated research. Source: <a href="https://www.shopgalafresh.com/">Gala Fresh public storefront</a>. Online values are not asserted as physical shelf prices.</p></footer>{script}</body></html>"""


def _summary_script(source: str, weekly: bool = False) -> str:
    keys = "['latest_catalog_size','median_catalog_size','median_valid_price_percentage','price_increases','price_decreases','additions','returns','missing_products']" if weekly else "['catalog_size','valid_price_percentage','median_regular_price','products_with_promotions']"
    target = "data" if weekly else "data.latest"
    return f"""<script>fetch('{source}').then(r=>r.json()).then(data=>{{const source={target};const labels={{catalog_size:'Catalog products',valid_price_percentage:'Valid prices %',median_regular_price:'Median regular price',products_with_promotions:'Products promoted',latest_catalog_size:'Latest catalog',median_catalog_size:'Median catalog',median_valid_price_percentage:'Median valid prices %',price_increases:'Price increases',price_decreases:'Price decreases',additions:'Additions',returns:'Returns',missing_products:'Missing observations'}};document.querySelector('#status').textContent=data.status;document.querySelector('#metrics').innerHTML={keys}.map(k=>`<section class="card"><div class="metric">${{source[k]??'—'}}</div><div>${{labels[k]}}</div></section>`).join('');document.querySelector('#raw').href='{source}';}}).catch(e=>document.querySelector('#status').textContent='Report data unavailable');</script>"""


def _daily_script() -> str:
    return """<script>const esc=s=>String(s??'—').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));const priceRows=rows=>rows.slice(0,25).map(x=>`<tr><td>${esc(x.name)}</td><td>${esc(x.previous_regular_price)}</td><td>${esc(x.current_regular_price)}</td><td>${esc(x.change_percentage)}%</td></tr>`).join('')||'<tr><td colspan="4">None reported</td></tr>';fetch('data/daily-summary.json').then(r=>r.json()).then(d=>{status.textContent=d.status;const x=d.latest;metrics.innerHTML=[['Catalog products',x.catalog_size],['Valid prices %',x.valid_price_percentage],['Promoted products',x.products_with_promotions],['Prior overlap %',d.comparison?.prior_overlap_percentage??'—']].map(([k,v])=>`<section class="card"><div class="metric">${esc(v)}</div><div>${k}</div></section>`).join('');increases.innerHTML=priceRows(d.price_increases);decreases.innerHTML=priceRows(d.price_decreases);assortment.textContent=d.comparison?`${d.comparison.additions} additions; ${d.comparison.returns} returns; ${d.comparison.missing_products} missing observations`:'Comparisons begin with the second healthy snapshot.';promotions.textContent=`${d.promotion_changes.active} active; ${d.promotion_changes.start_count} starts; ${d.promotion_changes.end_count} ends; ${d.promotion_changes.change_count} changes`;anomalies.textContent=`${d.anomalies.length} conservative flags`;}).catch(()=>status.textContent='Report data unavailable')</script>"""


def _weekly_script() -> str:
    return """<script>const esc=s=>String(s??'—').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));fetch('data/weekly-summary.json').then(r=>r.json()).then(d=>{status.textContent=d.status;metrics.innerHTML=[['Latest catalog',d.latest_catalog_size],['Median catalog',d.median_catalog_size],['Median valid prices %',d.median_valid_price_percentage],['Snapshot days',d.snapshot_days]].map(([k,v])=>`<section class="card"><div class="metric">${esc(v)}</div><div>${k}</div></section>`).join('');totals.textContent=`${d.price_increases} price increases; ${d.price_decreases} decreases; ${d.additions} additions; ${d.returns} returns; ${d.missing_products} missing observations`;history.innerHTML=d.daily_history.map(x=>`<tr><td>${esc(x.snapshot_date)}</td><td>${esc(x.catalog_size)}</td><td>${esc(x.valid_price_percentage)}%</td><td>${esc(x.products_with_promotions)}</td></tr>`).join('')||'<tr><td colspan="4">Awaiting baseline</td></tr>';}).catch(()=>status.textContent='Report data unavailable')</script>"""


def build_reports(snapshot_dir: Path, docs_dir: Path) -> tuple[dict, dict]:
    data_dir = docs_dir / "data"
    assets = docs_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    daily = build_daily_summary(snapshot_dir)
    weekly = build_weekly_summary(daily)
    write_json(data_dir / "daily-summary.json", daily)
    write_json(data_dir / "weekly-summary.json", weekly)
    history_dir = data_dir / "catalog-history"
    if history_dir.exists():
        shutil.rmtree(history_dir)
    build_catalog_history(snapshot_dir, history_dir)
    (assets / "site.css").write_text(STYLE.strip() + "\n", encoding="utf-8")
    overview = '<section class="hero"><h1>Gala Fresh Baldwin catalog research</h1><p>Daily, transparent history of the anonymously visible public online catalog.</p><p>Pipeline: <span id="status" class="healthy">Loading…</span></p></section><section id="metrics" class="grid" aria-live="polite"></section><p><a id="raw" href="data/daily-summary.json">Machine-readable daily contract</a></p>'
    (docs_dir / "index.html").write_text(_page("Gala Fresh Baldwin Research", overview, _summary_script("data/daily-summary.json")), encoding="utf-8")
    daily_body = '<h1>Daily report</h1><p>Latest daily changes, with missing observations preserved as gaps.</p><p>Status: <span id="status">Loading…</span></p><section id="metrics" class="grid"></section><h2>Assortment</h2><p id="assortment"></p><h2>Promotions</h2><p id="promotions"></p><h2>Anomalies</h2><p id="anomalies"></p><h2>Regular-price increases</h2><table><thead><tr><th>Product</th><th>Previous</th><th>Current</th><th>Change</th></tr></thead><tbody id="increases"></tbody></table><h2>Regular-price decreases</h2><table><thead><tr><th>Product</th><th>Previous</th><th>Current</th><th>Change</th></tr></thead><tbody id="decreases"></tbody></table><p><a href="data/daily-summary.json">Daily JSON contract</a></p>'
    (docs_dir / "daily-report.html").write_text(_page("Daily report", daily_body, _daily_script()), encoding="utf-8")
    weekly_body = '<h1>Weekly report</h1><p>A less noisy seven-snapshot research readout.</p><p>Status: <span id="status">Loading…</span></p><section id="metrics" class="grid"></section><p id="totals"></p><table><thead><tr><th>Date</th><th>Catalog</th><th>Valid prices</th><th>Promoted products</th></tr></thead><tbody id="history"></tbody></table><p><a href="data/weekly-summary.json">Weekly JSON contract</a></p>'
    (docs_dir / "weekly-report.html").write_text(_page("Weekly report", weekly_body, _weekly_script()), encoding="utf-8")
    history_script = """<script>const esc=s=>String(s??'—').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));let index;fetch('data/catalog-history/index.json').then(r=>r.json()).then(x=>{index=x;render('')});function render(q){q=q.toLowerCase();const rows=index.items.filter(x=>(x.name+' '+(x.brand||'')+' '+x.product_key).toLowerCase().includes(q)).slice(0,100);document.querySelector('#results').innerHTML=rows.map(x=>`<tr><td><button data-shard="${esc(x.shard)}" data-key="${esc(x.product_key)}">${esc(x.name)}</button></td><td>${esc(x.brand)}</td><td>${esc(x.product_key)}</td></tr>`).join('')}document.querySelector('#search').addEventListener('input',e=>render(e.target.value));document.querySelector('#results').addEventListener('click',async e=>{if(e.target.tagName!=='BUTTON')return;const x=e.target;const data=await fetch(`data/catalog-history/${x.dataset.shard}.json`).then(r=>r.json());const item=data.items.find(i=>i.product_key===x.dataset.key);document.querySelector('#detail').innerHTML=`<h2>${esc(item.name)}</h2><table><thead><tr><th>Date</th><th>Regular price</th><th>Promotions</th></tr></thead><tbody>${item.observations.map(o=>`<tr><td>${esc(o.date)}</td><td class="${o.catalog?'':'gap'}">${esc(o.catalog?(o.catalog.regular_price??'missing'):'gap')}</td><td>${esc(o.promotions.map(p=>p.description||p.promotion_id).join('; ')||'—')}</td></tr>`).join('')}</tbody></table>`});</script>"""
    history_body = '<h1>Catalog history</h1><label for="search">Search products</label><input id="search" type="search" placeholder="Name, brand, or product key"><table><thead><tr><th>Product</th><th>Brand</th><th>Stable key</th></tr></thead><tbody id="results"></tbody></table><section id="detail" aria-live="polite"></section>'
    (docs_dir / "catalog-history.html").write_text(_page("Catalog history", history_body, history_script), encoding="utf-8")
    methodology_md = docs_dir / "METHODOLOGY.md"
    if methodology_md.exists():
        paragraphs = methodology_md.read_text(encoding="utf-8").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html = "<h1>Methodology</h1><pre style=\"white-space:pre-wrap;font:inherit\">" + paragraphs + "</pre>"
        (docs_dir / "METHODOLOGY.html").write_text(_page("Methodology", html), encoding="utf-8")
    (docs_dir / ".nojekyll").write_text("", encoding="utf-8")
    return daily, weekly
