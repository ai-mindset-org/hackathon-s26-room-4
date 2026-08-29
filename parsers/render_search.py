"""Поиск по товару — страница инструмента в общей теме сайта кухни.

Дайджест отвечает на «что изменилось со вчера». Справочник — на «что у меня
вообще есть». Эта страница отвечает на вопрос, который закупщик задаёт первым:
**вбил товар — где сегодня дешевле и кому звонить.**

Тема берётся из `core/theme.py` целиком, своего не заводим: страница должна
выглядеть частью сайта, а не приклеенной сбоку.
"""

from __future__ import annotations

import glob
import json
from pathlib import Path

from core.theme import CSS, FONTS
from parsers.catalog import build_per_kg
from parsers.matching import CUT, STATE, VIEW, WEIGHTS

EXTRA = """
.tabs{display:flex;gap:6px;border-bottom:1px solid var(--line);margin-bottom:26px}
.tab{appearance:none;background:none;border:0;border-bottom:2px solid transparent;
padding:11px 18px 13px;font:600 15px Inter,sans-serif;color:var(--dim);cursor:pointer}
.tab[aria-selected=true]{color:var(--ink);border-bottom-color:var(--accent)}
.tab:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.q{width:100%;padding:17px 20px;font:17px Inter,sans-serif;color:var(--ink);
background:var(--card);border:1px solid var(--line);border-radius:12px}
.q:focus{outline:none;border-color:var(--ink);box-shadow:0 0 0 3px rgba(0,0,0,.06)}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 30px}
.chip{appearance:none;background:var(--card);border:1px solid var(--line);
border-radius:999px;padding:7px 15px;font:500 14px Inter,sans-serif;
color:var(--dim);cursor:pointer;transition:all .15s ease}
.chip:hover{border-color:var(--ink);color:var(--ink)}
.hero-best{border:1px solid var(--line);border-radius:16px;padding:26px 28px;
margin-bottom:26px;position:relative;overflow:hidden;background:var(--card)}
.hero-best::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;
background:var(--grad)}
.hero-best .lbl{font-size:13px;color:var(--dim);font-weight:600;
letter-spacing:.04em;text-transform:uppercase}
.hero-best .val{font-family:"Inter Tight",Inter,sans-serif;font-weight:800;
font-size:clamp(34px,5vw,48px);line-height:1.05;letter-spacing:-.02em;margin:10px 0 6px}
.hero-best .who{font-size:17px}.hero-best .who b{font-weight:600}
.hero-best .meta{color:var(--dim);font-size:14px;margin-top:8px}
h3.sec{font-family:"Inter Tight",Inter,sans-serif;font-weight:700;font-size:15px;
letter-spacing:.02em;margin:34px 0 12px;color:var(--dim)}
table.t{width:100%;border-collapse:collapse;font-size:15px}
table.t td{padding:14px 14px 14px 0;border-bottom:1px solid var(--line);vertical-align:top}
table.t td.num{text-align:right;padding-right:0;white-space:nowrap;font-weight:600;
font-variant-numeric:tabular-nums}
.tg{display:inline-block;padding:3px 11px;border-radius:999px;font-size:12px;
font-weight:600;white-space:nowrap}
.tg.sup{background:#ecfdf5;color:var(--green)}
.tg.ref{border:1px solid var(--line);color:var(--dim)}
.tel{color:var(--accent);font-weight:600}
.dim{color:var(--dim);font-size:14px}
.empty{color:var(--dim);padding:34px 0;font-size:17px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:640px){.two{grid-template-columns:1fr}}
.verdict{border:1px solid var(--line);border-radius:16px;padding:24px 28px;
margin:20px 0;background:var(--card)}
.verdict .v{font-family:"Inter Tight",Inter,sans-serif;font-weight:800;
font-size:28px;letter-spacing:-.01em}
.v.same{color:var(--green)}.v.diff{color:var(--red)}.v.ask{color:var(--amber)}
.bars{margin-top:20px}
.bar{display:grid;grid-template-columns:130px 1fr 48px;gap:14px;align-items:center;
margin-bottom:10px;font-size:14px}
.bar .track{height:8px;background:var(--line);border-radius:999px;overflow:hidden}
.bar .fill{height:8px;background:var(--grad);border-radius:999px}
.bar .n{text-align:right;font-variant-numeric:tabular-nums;font-weight:600}
"""


def collect(dept="departments/myaso/data") -> dict:
    snaps = [json.loads(Path(p).read_text(encoding="utf-8"))
             for p in sorted(glob.glob(f"{dept}/*.json"))]
    data = build_per_kg(snaps)
    offers = []
    for row in data["rows"]:
        for o in row["offers"]:
            offers.append({"canon": row["title"], "p": round(o["price"]),
                           "shop": o["shop"], "t": o["title"][:100],
                           "src": o["source"], "basis": o.get("basis", "")})
        for b in row["benchmarks"]:
            offers.append({"canon": row["title"], "p": round(b["price"]),
                           "shop": b["source"], "t": b["title"][:100],
                           "src": b["source"], "bench": 1})
    for snap in snaps:
        if snap.get("source_status") != "ok":
            continue
        for item in snap.get("items", {}).values():
            if item.get("price_status") != "listed" or item.get("price") is None:
                continue
            offers.append({"canon": "", "p": round(float(item["price"])),
                           "shop": item.get("shop") or snap["source"],
                           "t": (item.get("title") or "")[:100],
                           "src": snap["source"], "basis": "как у источника"})
    return {"offers": offers,
            "view": {k: list(v) for k, v in VIEW.items()},
            "cut": {k: list(v) for k, v in CUT.items()},
            "state": {k: list(v) for k, v in STATE.items()},
            "weights": WEIGHTS}


BODY = """
<nav><a class="brand" href="./index.html">🍽 КУХНЯ</a>
<span class="links"><a href="./index.html">Отделы</a>
<a href="./dept-myaso.html">Дайджест мяса</a>
<a href="./digest.html">Общий дайджест</a></span></nav>

<h1>Где сегодня дешевле</h1>
<p class="lede">Вбейте товар — увидите цены всех поставщиков, кому звонить и
как это соотносится с рынком.</p>

<div class="tabs" role="tablist">
  <button class="tab" role="tab" aria-selected="true" data-t="find">Найти товар</button>
  <button class="tab" role="tab" aria-selected="false" data-t="check">Проверить сопоставление</button>
</div>

<section id="find">
  <input type="text" class="q" id="q" autocomplete="off"
   placeholder="Куриная грудка, лосось филе, треска, говядина…">
  <div class="chips" id="chips"></div>
  <div id="res"></div>
</section>

<section id="check" hidden>
  <p class="dim" style="margin:0 0 16px">Два названия — и видно, считает ли
  инструмент их одним товаром и почему. Разный вид животного блокирует
  совпадение сразу: курица и яйцо не склеятся ни при какой уверенности.</p>
  <div class="two">
    <input type="text" class="q" id="a" value="Цыплята отборные">
    <input type="text" class="q" id="b" value="Яйца куриные С1">
  </div>
  <div class="chips" id="pairs"></div>
  <div id="out"></div>
</section>

<p class="dim" id="foot" style="margin-top:56px;padding-top:22px;
border-top:1px solid var(--line)"></p>
"""

SCRIPT = r"""
const D=JSON.parse(document.getElementById('D').textContent);
const fold=s=>(s||'').toLowerCase().replace(/ё/g,'е').replace(/\s+/g,' ');
const NOISE=['продукция','доп информация','информация','вес упаковки','размерный ряд',
'качество','поставка','напрямую','производства','хранение','месяцев','в наличии','цена','руб'];
function clean(s){let l=fold(s);NOISE.forEach(w=>l=l.split(w).join(' '));
 return l.replace(/[^\wа-я ]/g,' ').replace(/\s+/g,' ').trim()}
function find(s,t){const l=' '+fold(s)+' ';for(const k in t){if(t[k].some(v=>l.includes(v)))return k}return ''}
function feats(t){return{view:find(t,D.view),cut:find(t,D.cut),state:find(t,D.state),title:clean(t)}}
function ratio(a,b){if(!a||!b)return 0;const A=a.split(' '),B=new Set(b.split(' '));
 let m=0;A.forEach(w=>{if(B.has(w))m++});return 2*m/(A.length+B.size)}
function score(x,y){const fa=feats(x),fb=feats(y);
 if(fa.view&&fb.view&&fa.view!==fb.view)
   return{s:0,parts:{view:0,cut:0,state:0,title:0},fa,fb,blocked:'вид'};
 const p={};['view','cut','state'].forEach(f=>{
   p[f]=(!fa[f]&&!fb[f])?0.5:(!fa[f]||!fb[f])?0.35:(fa[f]===fb[f]?1:0)});
 p.title=ratio(fa.title,fb.title);
 return{s:Object.keys(D.weights).reduce((a,k)=>a+p[k]*D.weights[k],0),parts:p,fa,fb,blocked:''}}
const money=n=>n.toLocaleString('ru-RU');
const esc=s=>String(s).replace(/[<>&]/g,c=>({'<':'&lt;','>':'&gt;','&':'&amp;'}[c]));
const canons=[...new Set(D.offers.map(o=>o.canon).filter(Boolean))].slice(0,10);
document.getElementById('chips').innerHTML=canons
 .map(c=>`<button class=chip data-c="${esc(c)}">${esc(c)}</button>`).join('');
function render(q){const res=document.getElementById('res');
 if(!q.trim()){res.innerHTML='<p class=empty>Введите название товара или выберите из списка.</p>';return}
 const hits=D.offers.map(o=>({o,s:Math.max(score(q,o.t).s,o.canon?score(q,o.canon).s:0)}))
  .filter(h=>h.s>=0.5).sort((a,b)=>b.s-a.s||a.o.p-b.o.p);
 if(!hits.length){res.innerHTML=`<p class=empty>По запросу «${esc(q)}» не нашлось ни у одного из источников. Это честный ответ, а не пустая страница.</p>`;return}
 const sup=hits.filter(h=>!h.o.bench),ben=hits.filter(h=>h.o.bench),best=sup[0];
 let h='';
 if(best){h+=`<div class=hero-best><span class=lbl>Дешевле всего сегодня</span>
  <div class=val>${money(best.o.p)} ₽<span style="font-size:.42em;font-weight:600"> /кг</span></div>
  <div class=who>у <b>${esc(best.o.shop)}</b></div>
  <div class=meta>${esc(best.o.t)}${best.o.basis?' · '+esc(best.o.basis):''}</div></div>`}
 h+='<h3 class=sec>Предложения поставщиков</h3><table class=t>';
 sup.slice(0,10).forEach(({o})=>{const tel=(o.shop.match(/\+7[\d()\- ]+/)||[''])[0];
  h+=`<tr><td>${esc(o.t)}<br><span class=dim>${esc(o.shop.replace(tel,''))} ${tel?`<span class=tel>${esc(tel)}</span>`:''}</span></td>
  <td><span class="tg sup">поставщик</span></td><td class=num>${money(o.p)} ₽</td></tr>`});
 h+='</table>';
 if(ben.length){h+='<h3 class=sec>Для сравнения — цены рынка</h3><table class=t>';
  ben.slice(0,6).forEach(({o})=>{h+=`<tr><td class=dim>${esc(o.t)}<br><span class=dim>${esc(o.src)}</span></td>
   <td><span class="tg ref">не продаёт</span></td><td class="num dim">${money(o.p)} ₽</td></tr>`});
  h+='</table>'}
 else h+='<p class=dim style="margin-top:18px">Справочной цены по этому товару нет — Росстат и Еврокомиссия дают только крупные категории.</p>';
 res.innerHTML=h}
const PAIRS=[['Цыплята отборные','Яйца куриные С1'],['Говядина Рибай','Говядина лопатка'],
['Куриная грудка СМ','Филе грудки цыпленка-бройлера'],['Лосось филе','Форель филе'],
['Треска тушка','Тушка трески Тихоокеанская мороженая']];
document.getElementById('pairs').innerHTML=PAIRS
 .map((p,i)=>`<button class=chip data-p="${i}">${esc(p[0])} ↔ ${esc(p[1])}</button>`).join('');
function check(){const a=document.getElementById('a').value,b=document.getElementById('b').value;
 const r=score(a,b);
 const v=r.s>=0.85?['same','Один и тот же товар','склеиваем автоматически']
  :r.s>=0.6?['ask','Похоже, но не уверены','уходит на подтверждение человеку']
  :['diff','Разные товары','не склеиваем'];
 const n={view:'вид',cut:'отруб',state:'обработка',title:'название'};
 let h=`<div class=verdict><div class="v ${v[0]}">${v[1]} · ${r.s.toFixed(2)}</div>
  <p class=dim style="margin:8px 0 0">${v[2]}${r.blocked?` — заблокировано по признаку «${r.blocked}»: <b>${esc(r.fa.view||'—')}</b> против <b>${esc(r.fb.view||'—')}</b>`:''}</p><div class=bars>`;
 Object.keys(D.weights).forEach(k=>{h+=`<div class=bar><span class=dim>${n[k]} · вес ${D.weights[k]}</span>
  <span class=track><span class=fill style="width:${Math.round(r.parts[k]*100)}%"></span></span>
  <span class=n>${r.parts[k].toFixed(2)}</span></div>`});
 h+=`</div></div><table class=t>
  <tr><td class=dim>признаки первого</td><td>вид <b>${esc(r.fa.view||'—')}</b> · отруб <b>${esc(r.fa.cut||'—')}</b> · обработка <b>${esc(r.fa.state||'—')}</b></td></tr>
  <tr><td class=dim>признаки второго</td><td>вид <b>${esc(r.fb.view||'—')}</b> · отруб <b>${esc(r.fb.cut||'—')}</b> · обработка <b>${esc(r.fb.state||'—')}</b></td></tr></table>`;
 document.getElementById('out').innerHTML=h}
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{
 document.querySelectorAll('.tab').forEach(x=>x.setAttribute('aria-selected',x===t));
 document.getElementById('find').hidden=t.dataset.t!=='find';
 document.getElementById('check').hidden=t.dataset.t!=='check'});
document.getElementById('q').addEventListener('input',e=>render(e.target.value));
document.getElementById('chips').onclick=e=>{if(e.target.dataset.c){
 document.getElementById('q').value=e.target.dataset.c;render(e.target.dataset.c)}};
document.getElementById('pairs').onclick=e=>{const i=e.target.dataset.p;
 if(i!==undefined){document.getElementById('a').value=PAIRS[i][0];
 document.getElementById('b').value=PAIRS[i][1];check()}};
['a','b'].forEach(id=>document.getElementById(id).addEventListener('input',check));
document.getElementById('foot').textContent=
 `В индексе ${D.offers.length} предложений. Цены приведены к килограмму там, где в названии есть вес. Справочные источники — Росстат, Еврокомиссия, розничный потолок Москвы — не продают и в подбор не идут.`;
render('');check();
"""


def render(dept="departments/myaso/data") -> str:
    data = collect(dept)
    return ("<!doctype html><html lang=ru><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'>"
            "<title>Где дешевле · Кухня</title>" + FONTS +
            f"<style>{CSS}{EXTRA}</style><canvas id=fx></canvas>"
            f"<div class=page>{BODY}</div>"
            f"<script id=D type='application/json'>"
            f"{json.dumps(data, ensure_ascii=False)}</script>"
            f"<script>{SCRIPT}</script></html>")


if __name__ == "__main__":
    import sys
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    html = render()
    Path("site").mkdir(exist_ok=True)
    Path("site/search.html").write_text(html, encoding="utf-8")
    print(f"собрано: site/search.html ({len(html)} байт)")
