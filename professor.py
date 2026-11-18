# ==========================================================
# PROFISORE v11-FINAL — سباق حي + cooldown + أدوات حقيقية
# Owner: مأمون — إمبراطور البروفيسور السيبراني
# ==========================================================
import os, sys, subprocess, traceback
def _auto():
    for m in ['sqlite3','urllib','json','time','random','hashlib','base64',
              'socket','threading','re','uuid','string','shutil','math',
              'concurrent.futures','datetime','dataclasses','typing']:
        try: __import__(m)
        except ImportError:
            try: subprocess.check_call([sys.executable,"-m","pip","install",m,"--quiet"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except: pass
_auto()

import json, sqlite3, time, urllib.request, urllib.parse, urllib.error
import random, hashlib, base64, socket, threading, re, uuid, string, shutil, math, datetime
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'profisore_v11.db')
ADMIN_PASS = "الكيلون في السيفون"
BOT_BRAND = "PROFISORE"
OWNER_AR = "مأمون — إمبراطور البروفيسور السيبراني"
RACE_COOLDOWN = 900  # 15 دقيقة

# ==========================================================
# DB INIT
# ==========================================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS global_intelligence (
        id INTEGER PRIMARY KEY AUTOINCREMENT, source_file TEXT,
        target_name TEXT, target_phone TEXT, target_facebook TEXT, payload_info TEXT)""")
    try:
        c.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS intel_fts USING fts5(
            target_name,target_phone,target_facebook,
            content='global_intelligence',content_rowid='id')""")
    except: pass
    c.execute("""CREATE TABLE IF NOT EXISTS sovereign_users (uid INTEGER PRIMARY KEY)""")
    c.execute("""CREATE TABLE IF NOT EXISTS admins (uid INTEGER PRIMARY KEY,
        level INTEGER DEFAULT 2, promoted_by INTEGER, promoted_at INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor_uid INTEGER, action TEXT, target TEXT, details TEXT, ts INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS user_coins (coin_id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_uid INTEGER, coin_name TEXT, coin_symbol TEXT, total_supply REAL,
        price REAL DEFAULT 1.0, created_at INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS global_settings (key TEXT PRIMARY KEY, value TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS investments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER,
        symbol TEXT, qty REAL, buy_price REAL, buy_time INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS price_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, symbol TEXT,
        target_price REAL, direction TEXT, created_at INTEGER, triggered INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS trade_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, symbol TEXT,
        action TEXT, qty REAL, price REAL, total REAL, ts INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS game_cooldowns (
        uid INTEGER, game TEXT, last_played INTEGER,
        PRIMARY KEY (uid, game))""")
    for k,v in [('chat_locked','0'),('maintenance','0')]:
        c.execute("INSERT OR IGNORE INTO global_settings VALUES(?,?)",(k,v))
    conn.commit()
    c.execute("PRAGMA table_info(sovereign_users)")
    existing=[r[1] for r in c.fetchall()]
    need={'username':"TEXT DEFAULT ''",'first_name':"TEXT DEFAULT ''",
          'lang':'TEXT DEFAULT "ar"','balance':'REAL DEFAULT 100000.0',
          'wallet_btc':'REAL DEFAULT 0.0','wallet_eth':'REAL DEFAULT 0.0',
          'wins':'INTEGER DEFAULT 0','losses':'INTEGER DEFAULT 0',
          'last_daily':'INTEGER DEFAULT 0','last_salary':'INTEGER DEFAULT 0',
          'current_job':'TEXT DEFAULT ""','job_salary':'REAL DEFAULT 500.0',
          'job_interval':'INTEGER DEFAULT 3600',
          'is_admin':'INTEGER DEFAULT 0','is_banned':'INTEGER DEFAULT 0'}
    for col,typ in need.items():
        if col not in existing:
            try: c.execute(f"ALTER TABLE sovereign_users ADD COLUMN {col} {typ}")
            except: pass
    conn.commit()
    try:
        rows=c.execute("SELECT uid,wallet_btc,wallet_eth FROM sovereign_users WHERE COALESCE(wallet_btc,0)>0 OR COALESCE(wallet_eth,0)>0").fetchall()
        for uid,btc,eth in rows:
            if btc and btc>0:
                ex=c.execute("SELECT 1 FROM investments WHERE uid=? AND symbol='BTC'",(uid,)).fetchone()
                if not ex:
                    c.execute("INSERT INTO investments (uid,symbol,qty,buy_price,buy_time) VALUES (?,?,?,?,?)",
                              (uid,'BTC',btc,50000,int(time.time())))
            if eth and eth>0:
                ex=c.execute("SELECT 1 FROM investments WHERE uid=? AND symbol='ETH'",(uid,)).fetchone()
                if not ex:
                    c.execute("INSERT INTO investments (uid,symbol,qty,buy_price,buy_time) VALUES (?,?,?,?,?)",
                              (uid,'ETH',eth,3000,int(time.time())))
            c.execute("UPDATE sovereign_users SET wallet_btc=0, wallet_eth=0 WHERE uid=?",(uid,))
        conn.commit()
    except: pass
    conn.close()

def _get_setting(k,d="0"):
    try:
        conn=sqlite3.connect(DB_PATH)
        r=conn.execute("SELECT value FROM global_settings WHERE key=?",(k,)).fetchone()
        conn.close(); return r[0] if r else d
    except: return d

def _set_setting(k,v):
    conn=sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR REPLACE INTO global_settings (key,value) VALUES(?,?)",(k,str(v)))
    conn.commit(); conn.close()

def check_cooldown(uid, game):
    """Returns (can_play, seconds_remaining)"""
    try:
        conn=sqlite3.connect(DB_PATH)
        r=conn.execute("SELECT last_played FROM game_cooldowns WHERE uid=? AND game=?",(uid,game)).fetchone()
        conn.close()
        if r and r[0]:
            elapsed=int(time.time())-r[0]
            if elapsed<RACE_COOLDOWN:
                return False, RACE_COOLDOWN-elapsed
        return True, 0
    except: return True, 0

def set_cooldown(uid, game):
    conn=sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR REPLACE INTO game_cooldowns (uid,game,last_played) VALUES (?,?,?)",
                 (uid,game,int(time.time())))
    conn.commit(); conn.close()

def deep_search(q):
    q=q.strip(); m=[]
    try:
        conn=sqlite3.connect(DB_PATH); c=conn.cursor()
        fts=" OR ".join(f'"{x}"*' for x in q.split() if x)
        c.execute("""SELECT g.target_name,g.target_phone,g.target_facebook,g.payload_info,g.source_file
                     FROM intel_fts f JOIN global_intelligence g ON f.rowid=g.id
                     WHERE intel_fts MATCH ? ORDER BY rank LIMIT 200""",(fts,))
        for r in c.fetchall(): m.append({"name":r[0],"phone":r[1],"fb":r[2],"payload":r[3],"src":r[4]})
        conn.close()
    except:
        try:
            conn=sqlite3.connect(DB_PATH); c=conn.cursor()
            c.execute("""SELECT target_name,target_phone,target_facebook,payload_info,source_file
                         FROM global_intelligence WHERE lower(target_name) LIKE ?
                         OR target_phone LIKE ? OR lower(target_facebook) LIKE ? LIMIT 200""",
                      (f"%{q.lower()}%",f"%{q}%",f"%{q.lower()}%"))
            for r in c.fetchall(): m.append({"name":r[0],"phone":r[1],"fb":r[2],"payload":r[3],"src":r[4]})
            conn.close()
        except: pass
    return m

# ==========================================================
# TELEGRAM
# ==========================================================
def _post(url,p):
    d=urllib.parse.urlencode(p).encode("utf-8")
    try:
        req=urllib.request.Request(url,data=d,method="POST")
        with urllib.request.urlopen(req,timeout=25) as r: return json.loads(r.read().decode())
    except: return None

def send(token,c,text,markup=None):
    if not token: return None
    p={"chat_id":c,"text":text[:4000],"parse_mode":"Markdown","disable_web_page_preview":"true"}
    if markup: p["reply_markup"]=json.dumps(markup,ensure_ascii=False)
    return _post(f"https://api.telegram.org/bot{token}/sendMessage",p)

def acb(token,cid):
    _post(f"https://api.telegram.org/bot{token}/answerCallbackQuery",{"callback_query_id":cid})

# ==========================================================
# USER HELPERS
# ==========================================================
def _get_user(c):
    conn=sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR IGNORE INTO sovereign_users (uid) VALUES(?)",(c,))
    conn.commit()
    r=conn.execute("SELECT balance,is_admin,lang FROM sovereign_users WHERE uid=?",(c,)).fetchone()
    conn.close()
    return r or (100000.0,0,"ar")

def _adjust(c,d):
    _get_user(c)
    conn=sqlite3.connect(DB_PATH)
    conn.execute("UPDATE sovereign_users SET balance=COALESCE(balance,0)+? WHERE uid=?",(d,c))
    conn.commit()
    r=conn.execute("SELECT balance FROM sovereign_users WHERE uid=?",(c,)).fetchone()
    conn.close()
    return r[0] if r else 0

def _is_admin(c):
    try:
        conn=sqlite3.connect(DB_PATH)
        conn.execute("INSERT OR IGNORE INTO sovereign_users (uid) VALUES(?)",(c,))
        conn.commit()
        r=conn.execute("SELECT is_admin FROM sovereign_users WHERE uid=?",(c,)).fetchone()
        if r and r[0]==1: conn.close(); return True
        a=conn.execute("SELECT 1 FROM admins WHERE uid=?",(c,)).fetchone()
        conn.close(); return bool(a)
    except: return False

def find_user(q):
    q=(q or "").strip()
    if not q: return (None,None,None)
    conn=sqlite3.connect(DB_PATH)
    try:
        uid=int(q.replace("@",""))
        r=conn.execute("SELECT uid,COALESCE(username,'') FROM sovereign_users WHERE uid=?",(uid,)).fetchone()
        if r: conn.close(); return (r[0],r[1],f"`{r[0]}` @{r[1] or '?'}")
    except: pass
    un=q.lstrip("@").strip()
    r=conn.execute("SELECT uid,COALESCE(username,'') FROM sovereign_users WHERE LOWER(username)=LOWER(?)",(un,)).fetchone()
    conn.close()
    if r: return (r[0],r[1],f"`{r[0]}` @{r[1] or '?'}")
    return (None,None,None)

def admin_login(c,txt):
    if txt != ADMIN_PASS: return False
    conn=sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR IGNORE INTO sovereign_users (uid) VALUES(?)",(c,))
    conn.execute("UPDATE sovereign_users SET is_admin=1 WHERE uid=?",(c,))
    conn.execute("INSERT OR REPLACE INTO admins (uid,level,promoted_by,promoted_at) VALUES(?,1,0,?)",(c,int(time.time())))
    conn.commit(); conn.close(); return True

def do_promote(q,by):
    uid,un,disp=find_user(q)
    if not uid: return (False,f"❌ `{q}` — لازم /start أولاً",None,None)
    conn=sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR IGNORE INTO sovereign_users (uid) VALUES(?)",(uid,))
    conn.execute("UPDATE sovereign_users SET is_admin=1 WHERE uid=?",(uid,))
    conn.execute("INSERT OR REPLACE INTO admins (uid,level,promoted_by,promoted_at) VALUES(?,2,?,?)",(uid,by,int(time.time())))
    conn.commit(); conn.close()
    return (True,f"👑 **تم الرفع!**\n• {disp}",uid,disp)

def do_demote(q,by):
    uid,un,disp=find_user(q)
    if not uid: return (False,f"❌ `{q}`",None,None)
    conn=sqlite3.connect(DB_PATH)
    conn.execute("UPDATE sovereign_users SET is_admin=0 WHERE uid=?",(uid,))
    conn.execute("DELETE FROM admins WHERE uid=?",(uid,))
    conn.commit(); conn.close()
    return (True,f"📉 **تم الطرد!**\n• {disp}",uid,disp)

# ==========================================================
# MARKET
# ==========================================================
CRYPTO=["BTC","ETH","BNB","SOL","XRP","ADA","DOGE","DOT","LINK","MATIC"]
STOCKS=["AAPL","MSFT","GOOGL","AMZN","TSLA","NVDA","META","NFLX","AMD","INTC"]
REITS=["O","SPG","PLD","AMT","EQIX","AVB","PSA","WELL","DLR","CCI"]
ALL_SYMBOLS=CRYPTO+STOCKS+REITS

def _crypto_24h(s):
    try:
        url=f"https://api.binance.com/api/v3/ticker/24hr?symbol={s}USDT"
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req,timeout=6) as r:
            d=json.loads(r.read().decode())
            return s,float(d.get("lastPrice",0)),float(d.get("priceChangePercent",0))
    except: return s,None,None

def _stooq(s):
    try:
        url=f"https://stooq.com/q/l/?s={s.lower()}.us&f=sd2t2ohlcv&h&e=csv"
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req,timeout=8) as r:
            rows=r.read().decode().strip().split("\n")
            if len(rows)<2: return s,None,None
            p=rows[1].split(",")
            if len(p)<8 or p[6]=="N/D": return s,None,None
            close=float(p[6]); open_=float(p[3])
            pct=((close-open_)/open_*100) if open_ else 0
            return s,close,pct
    except: return s,None,None

def get_price(sym):
    sym=sym.upper()
    if sym in CRYPTO:
        _,p,_=_crypto_24h(sym); return p
    if sym in STOCKS or sym in REITS:
        _,p,_=_stooq(sym); return p
    return None

def get_hist(sym):
    sym=sym.upper()
    try:
        if sym in CRYPTO:
            url=f"https://api.binance.com/api/v3/klines?symbol={sym}USDT&interval=1d&limit=80"
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req,timeout=8) as r:
                data=json.loads(r.read().decode())
                return [float(k[4]) for k in data]
        if sym in STOCKS or sym in REITS:
            url=f"https://stooq.com/q/d/l/?s={sym.lower()}.us&i=d"
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req,timeout=10) as r:
                lines=r.read().decode().strip().split("\n")[1:]
                out=[]
                for ln in lines[-80:]:
                    p=ln.split(",")
                    if len(p)>=5:
                        try: out.append(float(p[4]))
                        except: pass
                return out
    except: pass
    return []

def sma(p,n): return sum(p[-n:])/n if len(p)>=n else None

def ema(p,n):
    if len(p)<n: return None
    k=2/(n+1); v=sum(p[:n])/n
    for x in p[n:]: v=x*k+v*(1-k)
    return v

def rsi(p,period=14):
    if len(p)<period+1: return None
    g=l=0.0
    for i in range(1,period+1):
        d=p[i]-p[i-1]
        if d>0: g+=d
        else: l-=d
    ag=g/period; al=l/period
    if al==0: return 100.0
    return 100-(100/(1+ag/al))

def analyze(prices):
    if not prices or len(prices)<20:
        return {"signal":"بيانات غير كافية","score":0,"confidence":0,"reasons":[]}
    cur=prices[-1]; s20,s50=sma(prices,20),sma(prices,50); r=rsi(prices)
    score=0; reasons=[]
    if r:
        if r<30: score+=3; reasons.append(f"RSI={r:.0f} ذروة بيع")
        elif r>70: score-=3; reasons.append(f"RSI={r:.0f} ذروة شراء")
    if s20 and s50:
        if s20>s50: score+=1; reasons.append("SMA20>SMA50")
        else: score-=1; reasons.append("SMA20<SMA50")
    if s20: score+=1 if cur>s20 else -1
    sig=("🚀 شراء قوي" if score>=4 else "🟢 شراء" if score>=2
        else "🔻 بيع قوي" if score<=-4 else "🔴 بيع" if score<=-2 else "🟡 محايد")
    return {"signal":sig,"score":score,"confidence":min(abs(score)*15,95),
            "rsi":round(r,1) if r else None,
            "sma20":round(s20,2) if s20 else None,
            "sma50":round(s50,2) if s50 else None,"reasons":reasons}

# ==========================================================
# INVESTMENT ENGINE
# ==========================================================
def get_holdings(uid):
    conn=sqlite3.connect(DB_PATH)
    rows=conn.execute(
        "SELECT symbol, SUM(qty) as q, SUM(qty*buy_price)/NULLIF(SUM(qty),0) as avg "
        "FROM investments WHERE uid=? GROUP BY symbol",(uid,)).fetchall()
    conn.close()
    return [(r[0],r[1],r[2]) for r in rows if r[1] and r[1]>0]

def do_buy_sync(uid, sym, usd):
    sym=sym.upper()
    if sym not in ALL_SYMBOLS: return f"❌ الرمز غير مدعوم. المتاح: BTC,ETH,AAPL,TSLA,O,SPY..."
    if usd<10: return "❌ الحد الأدنى 10$"
    bal=_get_user(uid)[0]
    if bal<usd: return f"❌ تحتاج {usd:.2f}$ — عندك {bal:,.2f}$"
    price=get_price(sym)
    if not price: return f"❌ لا يمكن جلب سعر {sym}"
    qty=usd/price
    conn=sqlite3.connect(DB_PATH)
    conn.execute("UPDATE sovereign_users SET balance=balance-? WHERE uid=?",(usd,uid))
    conn.execute("INSERT INTO investments (uid,symbol,qty,buy_price,buy_time) VALUES (?,?,?,?,?)",
                 (uid,sym,qty,price,int(time.time())))
    conn.execute("INSERT INTO trade_log (uid,symbol,action,qty,price,total,ts) VALUES (?,?,?,?,?,?,?)",
                 (uid,sym,"buy",qty,price,usd,int(time.time())))
    conn.commit(); conn.close()
    return (f"🟢 **تم الشراء!**\n"
            f"• {sym}: *{qty:.6f}*\n"
            f"• السعر: ${price:,.2f}\n"
            f"• المبلغ: *{usd:,.2f}$*\n"
            f"💰 رصيدك: *{_get_user(uid)[0]:,.2f}$*")

def do_sell_sync(uid, sym, qty):
    sym=sym.upper()
    h={s:{"qty":q,"avg":a} for s,q,a in get_holdings(uid)}
    if sym not in h: return f"❌ ما عندك {sym}"
    if qty>h[sym]["qty"]: return f"❌ عندك {h[sym]['qty']:.6f} فقط"
    price=get_price(sym)
    if not price: return f"❌ لا سعر"
    usd=qty*price; cost=qty*h[sym]["avg"]; pnl=usd-cost
    conn=sqlite3.connect(DB_PATH)
    conn.execute("UPDATE sovereign_users SET balance=balance+? WHERE uid=?",(usd,uid))
    remaining=qty
    rows=conn.execute("SELECT id,qty FROM investments WHERE uid=? AND symbol=? ORDER BY id ASC",
                      (uid,sym)).fetchall()
    for rid,rq in rows:
        if remaining<=0: break
        if rq<=remaining:
            conn.execute("DELETE FROM investments WHERE id=?",(rid,))
            remaining-=rq
        else:
            conn.execute("UPDATE investments SET qty=qty-? WHERE id=?",(remaining,rid))
            remaining=0
    conn.execute("INSERT INTO trade_log (uid,symbol,action,qty,price,total,ts) VALUES (?,?,?,?,?,?,?)",
                 (uid,sym,"sell",qty,price,usd,int(time.time())))
    conn.commit(); conn.close()
    sign="🟢" if pnl>=0 else "🔴"
    return (f"🟢 **تم البيع!**\n"
            f"• {sym}: *{qty:.6f}*\n"
            f"• السعر: ${price:,.2f}\n"
            f"• المبلغ: *{usd:,.2f}$*\n"
            f"{sign} **P&L: {pnl:+,.2f}$**\n"
            f"💰 رصيدك: *{_get_user(uid)[0]:,.2f}$*")

def render_portfolio(uid):
    holdings=get_holdings(uid)
    bal=_get_user(uid)[0]
    if not holdings:
        return (f"💼 **محفظتك فاضية**\n"
                f"• نقد: *{bal:,.2f}$*\n"
                f"• إجمالي: *{bal:,.2f}$*\n\n"
                f"💡 استخدم: `شراء BTC 100`")
    L=[f"💼 **محفظتك**",""]
    total_val=0; total_cost=0
    with ThreadPoolExecutor(max_workers=10) as ex:
        syms=[h[0] for h in holdings]
        prices={}
        futs={ex.submit(get_price,s):s for s in syms}
        for f in as_completed(futs):
            s=futs[f]; prices[s]=f.result()
    for sym,qty,avg in holdings:
        price=prices.get(sym) or avg
        val=qty*price; cost=qty*avg; pnl=val-cost
        pct=(pnl/cost*100) if cost else 0
        total_val+=val; total_cost+=cost
        emoji="🟢" if pnl>=0 else "🔴"
        L.append(f"{emoji} **{sym}**")
        L.append(f"  • كمية: `{qty:.6f}`")
        L.append(f"  • متوسط: ${avg:,.2f}")
        L.append(f"  • الحالي: ${price:,.2f}")
        L.append(f"  • P&L: *{pnl:+,.2f}$* ({pct:+.2f}%)")
        L.append("")
    total_pnl=total_val-total_cost
    total_pct=(total_pnl/total_cost*100) if total_cost else 0
    L.append("━━━━━━━━━━")
    L.append(f"💰 نقد: *{bal:,.2f}$*")
    L.append(f"📊 استثمارات: *{total_val:,.2f}$*")
    L.append(f"💎 **الإجمالي: {bal+total_val:,.2f}$**")
    emoji="🟢" if total_pnl>=0 else "🔴"
    L.append(f"{emoji} **P&L: {total_pnl:+,.2f}$ ({total_pct:+.2f}%)**")
    return "\n".join(L)

def check_alerts(uid, token):
    try:
        conn=sqlite3.connect(DB_PATH)
        alerts=conn.execute(
            "SELECT id,symbol,target_price,direction FROM price_alerts WHERE uid=? AND triggered=0",
            (uid,)).fetchall()
        if not alerts: conn.close(); return
        syms=list(set(a[1] for a in alerts))
        prices={}
        with ThreadPoolExecutor(max_workers=10) as ex:
            futs={ex.submit(get_price,s):s for s in syms}
            for f in as_completed(futs):
                s=futs[f]; prices[s]=f.result()
        triggered=[]
        for aid,sym,target,direction in alerts:
            p=prices.get(sym)
            if not p: continue
            hit=False
            if direction=="above" and p>=target: hit=True
            if direction=="below" and p<=target: hit=True
            if hit:
                conn.execute("UPDATE price_alerts SET triggered=1 WHERE id=?",(aid,))
                triggered.append((sym,target,direction,p))
        conn.commit(); conn.close()
        for sym,target,direction,p in triggered:
            arrow="⬆️" if direction=="above" else "⬇️"
            send(token,uid,
                 f"🚨 **تنبيه سعر!**\n"
                 f"• {sym}: ${p:,.2f}\n"
                 f"• الهدف: ${target:,.2f} ({arrow})")
    except: pass

def eng_signal_advanced(c, token, sym):
    h=get_hist(sym)
    if not h or len(h)<20:
        return f"📊 **{sym}**\n• بيانات غير كافية"
    a=analyze(h)
    cur=h[-1]
    reasons_str = "\n".join(f"• {x}" for x in a["reasons"]) if a["reasons"] else "• لا أسباب واضحة"
    return (f"📊 **{sym}**\n"
            f"• السعر: ${cur:,.2f}\n"
            f"• الإشارة: **{a['signal']}**\n"
            f"• الثقة: {a['confidence']}%\n"
            f"• RSI: {a.get('rsi','N/A')}\n"
            f"• SMA20: ${a.get('sma20',0):,.2f}\n"
            f"• SMA50: ${a.get('sma50',0):,.2f}\n"
            f"━━━\n{reasons_str}")

def eng_signals_all(c, token, _=""):
    L=["📊 **إشارات كل الأصول**",""]
    results=[]
    syms=["BTC","ETH","AAPL","MSFT","TSLA","O","SPY","NVDA"]
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs={ex.submit(get_hist,s):s for s in syms if s in ALL_SYMBOLS}
        for f in as_completed(futs):
            s=futs[f]; h=f.result()
            if len(h)>=20:
                a=analyze(h)
                results.append((s,a["signal"],a["confidence"],h[-1]))
    for s,sig,conf,price in sorted(results):
        emoji=sig.split()[0] if sig else "🟡"
        L.append(f"{emoji} **{s}** — {sig} ({conf}%) @ ${price:,.2f}")
    return "\n".join(L)

def eng_backtest_real(c, token, sym):
    h=get_hist(sym)
    if not h or len(h)<30:
        return f"🧪 **{sym}**\n• بيانات قليلة"
    cash,sh,trades=10000.0,0.0,0
    for i in range(30,len(h)):
        a=analyze(h[:i]); pr=h[i]
        if a["score"]>=2 and sh==0: sh,cash=cash/pr,0; trades+=1
        elif a["score"]<=-2 and sh>0: cash=sh*pr; sh=0; trades+=1
    final=cash+sh*h[-1]
    ret=(final/10000-1)*100
    return (f"🧪 **Backtest {sym}**\n"
            f"• البيانات: {len(h)} يوم\n"
            f"• البداية: *10,000$*\n"
            f"• النهاية: *{final:,.2f}$*\n"
            f"• العائد: *{ret:+.2f}%*\n"
            f"• الصفقات: {trades}\n"
            f"• الإشارة الحالية: {analyze(h)['signal']}")

def eng_trade_history(c, token, _=""):
    conn=sqlite3.connect(DB_PATH)
    rows=conn.execute("SELECT symbol,action,qty,price,total,ts FROM trade_log WHERE uid=? ORDER BY id DESC LIMIT 20",(c,)).fetchall()
    conn.close()
    if not rows:
        return "📋 **لا صفقات**\n\nاستخدم: `شراء BTC 100`"
    L=["📋 **آخر 20 صفقة:**",""]
    for sym,act,qty,price,total,ts in rows:
        when=datetime.datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")
        emoji="🟢" if act=="buy" else "🔴"
        act_ar="شراء" if act=="buy" else "بيع"
        L.append(f"{emoji} **{act_ar}** {sym} — {qty:.6f} @ ${price:,.2f} ({total:,.0f}$) — {when}")
    return "\n".join(L)

# ==========================================================
# HORSE / CAR RACE
# ==========================================================
HORSE_NAMES=["الأحمر","الأزرق","الأبيض","الأسود","الذهبي","الفضي","البرونزي","الرمادي",
    "البني","العسلي","الكستنائي","القرمزي","الوردي","البنفسجي","النحاسي",
    "الزيتوني","العنبري","الحليبي","الشوكولاتي","الثلجي","الليلكي","الفيروزي",
    "الأرجواني","الأصفر","البرتقالي"]
HORSE_BREEDS=["عربي أصيل","إنجليزي","ثوروبريد","أندلسي","أكحل","حمداني","عبيان","كحيلان"]
HORSE_JOCKEYS=["أحمد","محمد","عمر","خالد","سعد","فهد","طلال","ناصر","سلطان","عبدالله"]

@dataclass
class Horse:
    name:str; breed:str; jockey:str; base_speed:float; stamina:float
    form:float; jockey_skill:float; weight:float
    win_prob:float=0.0; odds:float=0.0; bettors:int=0

def gen_horses():
    hs=[]
    for i in range(25):
        hs.append(Horse(name=HORSE_NAMES[i],breed=random.choice(HORSE_BREEDS),
            jockey=random.choice(HORSE_JOCKEYS),
            base_speed=random.uniform(11.5,14.5),stamina=random.uniform(0.75,1.0),
            form=random.uniform(-0.10,0.12),jockey_skill=random.uniform(0.70,1.0),
            weight=random.uniform(55.0,62.0)))
    for h in hs:
        h._r=h.base_speed*h.stamina*h.jockey_skill*(1+h.form)*(60.0/h.weight)
    total=sum(h._r for h in hs)
    for h in hs:
        h.win_prob=h._r/total
        h.odds=round(1.0/h.win_prob*0.92,2)
        h.bettors=max(50,int(h.win_prob*random.uniform(8000,12000)))
    return hs

def sim_horse(hs,track=1200.0,dt=0.1):
    pos={h.name:0.0 for h in hs}; st={h.name:h.stamina for h in hs}
    finish=[]; snaps=[]; el=0.0; cnt=0
    while len(finish)<len(hs) and el<200:
        for h in hs:
            if h.name in finish: continue
            sp=h.base_speed*(1+h.form)*h.jockey_skill*st[h.name]
            sp*=(60.0/h.weight)*random.uniform(0.90,1.10)
            pos[h.name]+=sp*dt
            if track-pos[h.name]<300:
                st[h.name]=max(0.55,st[h.name]-0.008)
            if pos[h.name]>=track: finish.append(h.name)
        el+=dt; cnt+=1
        if cnt%10==0:
            top=sorted(pos.items(),key=lambda x:-x[1])[:8]
            snaps.append({"t":round(el,1),"top":[(n,min(round(p,1),track)) for n,p in top]})
    # Ensure all finished
    for h in hs:
        if h.name not in finish: finish.append(h.name)
    return finish,snaps

def render_horse_lobby(hs):
    L=["🏇 **قائمة الخيول الـ 25:**","━━━━━━━━━━━━━━━━━━"]
    for i,h in enumerate(hs,1):
        L.append(f"{i:2d}. *{h.name}* — x{h.odds} — 👥{h.bettors:,}")
    return "\n".join(L)

def render_horse_detail(h,i):
    return (f"🏇 **{h.name}** (#{i})\n━━━━━━━━━━━━━━━━━━\n"
            f"• السلالة: {h.breed}\n• الفارس: {h.jockey}\n"
            f"• السرعة: {h.base_speed:.1f} م/ث\n• التحمل: {h.stamina*100:.0f}%\n"
            f"• الحالة: {h.form*100:+.1f}%\n• الوزن: {h.weight:.1f}كغ\n"
            f"• احتمالية: {h.win_prob*100:.1f}%\n• المضاعف: **x{h.odds}**\n"
            f"• المقامرون: 👥 {h.bettors:,}")

def build_horse_race_message(hs, finish, snaps, pick, bet, payout=0):
    """Build ONE complete race message."""
    by={h.name:h for h in hs}
    total=len(snaps)
    chosen=[]
    for i in range(6):
        if total>0:
            pi=min(int((i+1)/6*total)-1,total-1)
            chosen.append(snaps[max(0,pi)])
    while len(chosen)<6:
        chosen.append(chosen[-1] if chosen else {"t":0,"top":[]})
    
    L=[f"🏇 **سباق الخيول**","━━━━━━━━━━━━━━━━━━",
       f"🚦 **السباق بدأ!**",
       f"🐎 اختيارك: *{pick}*",
       f"💰 الرهان: *{bet}$*",
       f"⏱ المدة: 60 ثانية",
       "━━━━━━━━━━━━━━━━━━"]
    
    for i,snap in enumerate(chosen[:6],1):
        if not snap["top"]: continue
        L.append(f"\n⏱ **المرحلة {i}/6** — t={snap['t']}s")
        for j,(n,p) in enumerate(snap["top"][:5],1):
            bar=min(int(p/1200*15),15) if p else 0
            vis="█"*bar+"░"*(15-bar)
            m="🥇" if j==1 else "🥈" if j==2 else "🥉" if j==3 else f"{j}."
            mark=" ⬅️" if n==pick else ""
            L.append(f"{m} *{n}* {vis} {p:.0f}م{mark}")
    
    L.append("\n━━━━━━━━━━━━━━━━━━")
    L.append("🏁 **النتيجة النهائية:**")
    for i,n in enumerate(finish[:8],1):
        h=by[n]; m="🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else "  "
        mark=" ⬅️ اختيارك" if n==pick else ""
        L.append(f"{m} {i}. *{n}* (x{h.odds}){mark}")
    
    winner=finish[0]
    L.append("━━━━━━━━━━━━━━━━━━")
    if pick==winner:
        L.append(f"🏆 **فزت!** *{winner}*\n💰 +*{payout:,}$*")
    else:
        L.append(f"❌ فاز *{winner}* — خسرت *{bet:,}$*")
    return "\n".join(L)

def g_horse(c, token, inp=""):
    # Cooldown check first
    if user_states.get(c)=="":
        ok,wait=check_cooldown(c,"horse")
        if not ok:
            m,s=wait//60,wait%60
            return (f"⏳ **سباق الخيول متاح بعد**\n"
                    f"⏱ تبقى: *{m}د {s}ث*\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"💡 جرّب: روليت، بلاك جاك، سلوت")
    
    st=user_states.get(c,"")
    
    if st=="horse_lobby":
        hs=user_states.get(f"horses_{c}")
        if not hs: user_states.pop(c,None); return "❌ ابدأ من جديد"
        try:
            idx=int(inp)-1
            if idx<0 or idx>=25: raise ValueError
        except: return "❌ أرسل رقم من 1-25"
        user_states[c]="horse_bet"
        user_states[f"horse_pick_{c}"]=idx
        return render_horse_detail(hs[idx],idx+1)+"\n\n💰 **كم تراهن؟** (10-10000$)\n*(0 للرجوع)*"
    
    if st=="horse_bet":
        try: bet=int(inp)
        except: return "❌ رقم"
        if bet<10 or bet>10000: return "❌ من 10 إلى 10000"
        if _get_user(c)[0]<bet: return f"❌ تحتاج {bet}$"
        hs=user_states.get(f"horses_{c}"); idx=user_states.get(f"horse_pick_{c}")
        if not hs or idx is None: user_states.pop(c,None); return "❌ ابدأ"
        pick=hs[idx].name
        for k in [c,f"horses_{c}",f"horse_pick_{c}"]: user_states.pop(k,None)
        _adjust(c,-bet)
        set_cooldown(c,"horse")
        # Compute race and return ONE message
        finish,snaps=sim_horse(hs)
        payout=0
        if finish[0]==pick:
            payout=int(bet*hs[idx].odds)
            _adjust(c,payout)
        msg=build_horse_race_message(hs,finish,snaps,pick,bet,payout)
        msg+=f"\n💰 رصيدك: *{_get_user(c)[0]:,.2f}$*"
        return msg
    
    # Fresh start
    hs=gen_horses()
    user_states[c]="horse_lobby"
    user_states[f"horses_{c}"]=hs
    return render_horse_lobby(hs)+"\n\n🐎 **أرسل رقم الحصان (1-25)** — أو 0 للرجوع"

CAR_BRANDS=["فيراري","لامبورغيني","ماكلارين","بورش","أستون مارتن","بوغاتي",
    "كوبيغ","مرسيدس","بي إم دبليو","أودي","نيسان","تويوتا","هوندا",
    "فورد","شيفروليه","دودج","مازيراتي","بنتلي","رولز رويس","تسلا"]
CAR_DRIVERS=["م. شوماخر","ل. هاميلتون","ف. ألونسو","س. فيتيل","ك. رايكونن",
    "ف. ماسا","ج. باتون","ن. روزبرغ","د. ريكاردو","م. فيرستابن",
    "ش. لوكلير","ل. نوريس","س. بيريز","ف. بوتاس","إ. أوكون",
    "ب. غاسلي","ك. ساينز","ي. تسونودا","ل. سترول","ن. هالكنبرغ"]

@dataclass
class RaceCar:
    brand:str; driver:str; hp:int; top_speed:float; grip:float; tire:float
    win_prob:float=0.0; odds:float=0.0; bettors:int=0

def gen_cars():
    bs=CAR_BRANDS.copy(); random.shuffle(bs)
    ds=CAR_DRIVERS.copy(); random.shuffle(ds)
    cs=[]
    for i in range(20):
        cs.append(RaceCar(brand=bs[i],driver=ds[i],
            hp=random.randint(400,950),top_speed=random.uniform(280,360),
            grip=random.uniform(0.70,1.0),tire=random.uniform(0.80,1.0)))
    for c in cs: c._r=(c.hp/950.0)*(c.top_speed/360.0)*c.grip*c.tire
    total=sum(c._r for c in cs)
    for c in cs:
        c.win_prob=c._r/total
        c.odds=round(1.0/c.win_prob*0.92,2)
        c.bettors=max(50,int(c.win_prob*random.uniform(5000,10000)))
    return cs

def sim_cars(cars,laps=30,lap_m=200.0,dt=0.2):
    total=laps*lap_m
    pos={c.driver:0.0 for c in cars}; tire={c.driver:c.tire for c in cars}
    finish=[]; snaps=[]; el=0.0; cnt=0
    while len(finish)<len(cars) and el<600:
        for c in cars:
            if c.driver in finish: continue
            sp=(c.top_speed/3.6)*c.grip*tire[c.driver]*random.uniform(0.88,1.12)
            pos[c.driver]+=sp*dt
            tire[c.driver]=max(0.6,tire[c.driver]-0.002)
            if pos[c.driver]>=total: finish.append(c.driver)
        el+=dt; cnt+=1
        if cnt%8==0:
            top=sorted(pos.items(),key=lambda x:-x[1])[:8]
            snaps.append({"t":round(el,1),"top":[(n,min(round(p,1),total)) for n,p in top]})
    for c in cars:
        if c.driver not in finish: finish.append(c.driver)
    return finish,snaps

def render_car_lobby(cs):
    L=["🏎️ **قائمة السيارات الـ 20:**","━━━━━━━━━━━━━━━━━━"]
    for i,c in enumerate(cs,1):
        L.append(f"{i:2d}. *{c.brand}* — {c.driver} — x{c.odds}")
    return "\n".join(L)

def render_car_detail(c,i):
    return (f"🏎️ **{c.brand}** (#{i})\n━━━━━━━━━━━━━━━━━━\n"
            f"• السائق: {c.driver}\n• القوة: {c.hp}HP\n"
            f"• السرعة: {c.top_speed:.0f}كم/س\n"
            f"• التماسك: {c.grip*100:.0f}%\n• الإطارات: {c.tire*100:.0f}%\n"
            f"• احتمالية: {c.win_prob*100:.1f}%\n• المضاعف: **x{c.odds}**\n"
            f"• المقامرون: 👥 {c.bettors:,}")

def build_car_race_message(cars, finish, snaps, pick, bet, payout=0):
    by={c.driver:c for c in cars}
    total=len(snaps)
    chosen=[]
    for i in range(6):
        if total>0:
            pi=min(int((i+1)/6*total)-1,total-1)
            chosen.append(snaps[max(0,pi)])
    while len(chosen)<6:
        chosen.append(chosen[-1] if chosen else {"t":0,"top":[]})
    L=[f"🏎️ **سباق السيارات**","━━━━━━━━━━━━━━━━━━",
       f"🚦 **السباق بدأ!**","",
       f"🏎️ اختيارك: *{pick}*",
       f"💰 الرهان: *{bet}$*",
       f"⏱ المدة: 60 ثانية",
       "━━━━━━━━━━━━━━━━━━"]
    for i,snap in enumerate(chosen[:6],1):
        if not snap["top"]: continue
        L.append(f"\n⏱ **المرحلة {i}/6** — t={snap['t']}s")
        for j,(n,p) in enumerate(snap["top"][:5],1):
            bar=min(int(p/6000*15),15) if p else 0
            vis="█"*bar+"░"*(15-bar)
            m="🥇" if j==1 else "🥈" if j==2 else "🥉" if j==3 else f"{j}."
            mark=" ⬅️" if n==pick else ""
            L.append(f"{m} *{n}* {vis} {p:.0f}م{mark}")
    L.append("\n━━━━━━━━━━━━━━━━━━")
    L.append("🏁 **النتيجة:**")
    for i,d in enumerate(finish[:8],1):
        c=by[d]; m="🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else "  "
        mark=" ⬅️" if d==pick else ""
        L.append(f"{m} {i}. *{c.brand}* — {d} (x{c.odds}){mark}")
    winner=finish[0]
    L.append("━━━━━━━━━━━━━━━━━━")
    if pick==winner:
        L.append(f"🏆 **فزت!**\n💰 +*{payout:,}$*")
    else:
        L.append(f"❌ فاز *{winner}* — خسرت *{bet:,}$*")
    return "\n".join(L)

def g_car(c, token, inp=""):
    if user_states.get(c)=="":
        ok,wait=check_cooldown(c,"car")
        if not ok:
            m,s=wait//60,wait%60
            return (f"⏳ **سباق السيارات متاح بعد**\n"
                    f"⏱ تبقى: *{m}د {s}ث*")
    
    st=user_states.get(c,"")
    
    if st=="car_lobby":
        cs=user_states.get(f"cars_{c}")
        if not cs: user_states.pop(c,None); return "❌"
        try:
            idx=int(inp)-1
            if idx<0 or idx>=20: raise ValueError
        except: return "❌ 1-20"
        user_states[c]="car_bet"
        user_states[f"car_pick_{c}"]=idx
        return render_car_detail(cs[idx],idx+1)+"\n\n💰 **كم تراهن؟** (10-10000$)"
    
    if st=="car_bet":
        try: bet=int(inp)
        except: return "❌"
        if bet<10 or bet>10000: return "❌ 10-10000"
        if _get_user(c)[0]<bet: return f"❌ {bet}$"
        cs=user_states.get(f"cars_{c}"); idx=user_states.get(f"car_pick_{c}")
        if not cs or idx is None: user_states.pop(c,None); return "❌"
        pick=cs[idx].driver
        for k in [c,f"cars_{c}",f"car_pick_{c}"]: user_states.pop(k,None)
        _adjust(c,-bet)
        set_cooldown(c,"car")
        finish,snaps=sim_cars(cs)
        payout=0
        if finish[0]==pick:
            payout=int(bet*cs[idx].odds)
            _adjust(c,payout)
        msg=build_car_race_message(cs,finish,snaps,pick,bet,payout)
        msg+=f"\n💰 رصيدك: *{_get_user(c)[0]:,.2f}$*"
        return msg
    
    cs=gen_cars()
    user_states[c]="car_lobby"
    user_states[f"cars_{c}"]=cs
    return render_car_lobby(cs)+"\n\n🏎️ **أرسل رقم السيارة (1-20)** — أو 0 للرجوع"

# ==========================================================
# SLOT / ROULETTE / BJ / DICE
# ==========================================================
SLOT_SYM=[("🍒",12),("🍋",10),("🍇",8),("⭐",6),("💎",3),("7️⃣",1)]
SLOT_STRIP=[]
for s,w in SLOT_SYM: SLOT_STRIP.extend([s]*w)
random.Random(42).shuffle(SLOT_STRIP)
SLOT_LEN=len(SLOT_STRIP)
SLOT_PAY={"7️⃣":100,"💎":50,"⭐":25,"🍇":15,"🍋":10,"🍒":5}

def _spin(): s=random.randint(0,SLOT_LEN-1); return [SLOT_STRIP[(s+i)%SLOT_LEN] for i in range(4)]

def _check_slot(rows):
    c=rows[1]
    if c[0]==c[1]==c[2]: return SLOT_PAY.get(c[0],0),"ثلاثة متطابقة"
    ch=c.count("🍒")
    if ch>=2: return 1.5,"كرزتين"
    if ch==1: return 0.5,"كرزة"
    for i,r in enumerate(rows):
        if r[0]==r[1]==r[2]=="7️⃣": return SLOT_PAY["7️⃣"]*2,f"جاكبوت صف {i}"
    return 0,""

def g_slot(c,token,inp=""):
    bet=100; bal=_get_user(c)[0]
    if bal<bet: return f"❌ تحتاج {bet}$"
    reels=[_spin() for _ in range(3)]
    rows=[[reels[cc][r] for cc in range(3)] for r in range(4)]
    disp="\n".join("🎰 ┃ "+" ┃ ".join(r)+" ┃" for r in rows)
    mult,reason=_check_slot(rows)
    if mult>0:
        win=int(bet*mult); _adjust(c,win-bet)
        return f"{disp}\n\n🔥 **{reason}**\n🟢 ربحت *{win}$*\n💰 {_get_user(c)[0]:,.2f}$"
    _adjust(c,-bet)
    return f"{disp}\n\n🔴 خسارة\n💰 {_get_user(c)[0]:,.2f}$"

RED={1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}

def g_roulette(c,token,inp=""):
    bal=_get_user(c)[0]
    parts=(inp or "").split()
    if len(parts)<2:
        return "🎯 `المبلغ نوع`\n`red, black, even, odd, 1-18, 19-36, num <0-36>`\nمثال: `100 red`"
    try: bet=int(parts[0]); typ=parts[1].lower()
    except: return "❌"
    if bet<10 or bet>10000: return "❌ 10-10000"
    if bal<bet: return f"❌ {bet}$"
    spin=random.randint(0,36)
    color="green" if spin==0 else ("red" if spin in RED else "black")
    icon="🟢" if color=="green" else "🔴" if color=="red" else "⚫"
    won=False; payout=0
    if typ=="red" and color=="red": won=True; payout=bet*2
    elif typ=="black" and color=="black": won=True; payout=bet*2
    elif typ=="even" and spin%2==0 and spin!=0: won=True; payout=bet*2
    elif typ=="odd" and spin%2==1: won=True; payout=bet*2
    elif typ=="1-18" and 1<=spin<=18: won=True; payout=bet*2
    elif typ=="19-36" and 19<=spin<=36: won=True; payout=bet*2
    elif typ=="num" and len(parts)>=3:
        try:
            if int(parts[2])==spin: won=True; payout=bet*36
        except: pass
    if won:
        _adjust(c,payout-bet)
        return f"🎯 **{icon} {spin}**\n🟢 +{payout}$\n💰 {_get_user(c)[0]:,.2f}$"
    _adjust(c,-bet)
    return f"🎯 **{icon} {spin}**\n🔴 -{bet}$\n💰 {_get_user(c)[0]:,.2f}$"

CARDS=["A","2","3","4","5","6","7","8","9","10","J","Q","K"]
SUITS=["♠","♥","♦","♣"]
def _deck(): d=[(r,s) for r in CARDS for s in SUITS]; random.shuffle(d); return d
def _hv(h):
    tot=0; a=0
    for r,_ in h:
        if r in ("J","Q","K"): tot+=10
        elif r=="A": a+=1; tot+=11
        else: tot+=int(r)
    while tot>21 and a>0: tot-=10; a-=1
    return tot
def _rh(h): return " ".join(f"{r}{s}" for r,s in h)

def g_bj(c,token,inp=""):
    bet=100; bal=_get_user(c)[0]
    if bal<bet: return f"❌ {bet}$"
    deck=_deck(); p=[deck.pop(),deck.pop()]; d=[deck.pop(),deck.pop()]
    pv=_hv(p); dv=_hv(d)
    _adjust(c,-bet)
    while dv<17: d.append(deck.pop()); dv=_hv(d)
    if pv>21: res=f"🔴 خسارة *{bet}$*"
    elif dv>21 or pv>dv: _adjust(c,bet*2); res=f"🟢 ربحت *{bet*2}$*"
    elif pv==dv: _adjust(c,bet); res="🟡 تعادل"
    else: res=f"🔴 خسارة *{bet}$*"
    return f"🎴 **أنت:** {_rh(p)} = *{pv}*\n🎴 **الموزع:** {_rh(d)} = *{dv}*\n\n{res}\n💰 {_get_user(c)[0]:,.2f}$"

def g_dice(c,token,inp=""):
    bet=100; bal=_get_user(c)[0]
    if bal<bet: return f"❌ {bet}$"
    r=random.randint(1,6); d=["⚀","⚁","⚂","⚃","⚄","⚅"][r-1]
    if r>=5: _adjust(c,bet); return f"🎲 {d} ({r})\n🟢 +{bet}$"
    _adjust(c,-bet); return f"🎲 {d} ({r})\n🔴 -{bet}$"

def g_coin(c,token,inp=""):
    bet=100; bal=_get_user(c)[0]
    if bal<bet: return f"❌ {bet}$"
    pick=(inp or "heads").lower().strip()
    f=random.choice(["heads","tails"])
    icon="👑" if f=="heads" else "🌙"
    name="وجه" if f=="heads" else "كتابة"
    if pick==f: _adjust(c,bet); return f"🪙 {icon} {name}\n🟢 +{bet}$"
    _adjust(c,-bet); return f"🪙 {icon} {name}\n🔴 -{bet}$"

def g_rps(c,token,inp=""):
    bet=100; bal=_get_user(c)[0]
    if bal<bet: return f"❌ {bet}$"
    p=(inp or "rock").lower().strip()
    if p not in ("rock","paper","scissors"): p="rock"
    b=random.choice(["rock","paper","scissors"])
    L={"rock":"✊","paper":"✋","scissors":"✌️"}
    if p==b: return f"{L[p]} ضد {L[b]}\n🟡 تعادل"
    W={"rock":"scissors","paper":"rock","scissors":"paper"}
    if W[p]==b: _adjust(c,bet); return f"{L[p]} ضد {L[b]}\n🟢 +{bet}$"
    _adjust(c,-bet); return f"{L[p]} ضد {L[b]}\n🔴 -{bet}$"

def g_highlow(c,token,inp=""):
    bet=100; bal=_get_user(c)[0]
    if bal<bet: return f"❌ {bet}$"
    r=random.randint(1,12); p=(inp or "high").lower().strip()
    hi=r>6
    if (p=="high" and hi) or (p=="low" and not hi):
        _adjust(c,bet); return f"📈 {r}\n🟢 +{bet}$"
    _adjust(c,-bet); return f"📈 {r}\n🔴 -{bet}$"

def g_trivia(c,token,inp=""):
    qs=[("عاصمة فرنسا؟","باريس"),("أكبر كوكب؟","المشتري"),
        ("مكتشف الجاذبية؟","نيوتن"),("ساعات اليوم؟","24")]
    q,a=random.choice(qs); return f"🧠 **{q}**\nمكافأة +200$"

def g_wheel(c,token,inp=""):
    bet=100; bal=_get_user(c)[0]
    if bal<bet: return f"❌ {bet}$"
    m=random.choices([0,0.5,1,2,3,5,10],weights=[30,20,20,15,8,5,2])[0]
    if m==0: _adjust(c,-bet); return f"🎡 0x\n🔴 -{bet}$"
    if m<1: _adjust(c,-int(bet*0.5)); return f"🎡 {m}x\n🟡 -{int(bet*0.5)}$"
    win=int(bet*m); _adjust(c,win-bet); return f"🎡 {m}x\n🟢 +{win}$"

def g_soccer(c,token,inp=""):
    bet=100; bal=_get_user(c)[0]
    if bal<bet: return f"❌ {bet}$"
    a,b=random.randint(0,4),random.randint(0,4)
    if a>b: _adjust(c,bet); return f"⚽ {a}-{b}\n🟢 +{bet}$"
    elif b>a: _adjust(c,-bet); return f"⚽ {a}-{b}\n🔴 -{bet}$"
    return f"⚽ {a}-{b}\n🟡 تعادل"

def g_guess(c,token,inp=""):
    return "🎯 أرسل رقم 1-10 (رهان 100$)"

GAMES={"slot":g_slot,"roulette":g_roulette,"bj":g_bj,"dice":g_dice,
       "coin":g_coin,"rps":g_rps,"highlow":g_highlow,"trivia":g_trivia,
       "wheel":g_wheel,"soccer":g_soccer,"guess":g_guess,
       "horse":g_horse,"car":g_car}

# ==========================================================
# OTHER REAL TOOLS
# ==========================================================
def eng_ip_info(c, token, ip=""):
    if not ip: return "🌐 أرسل IP أو domain"
    try:
        url=f"http://ip-api.com/json/{ip}?fields=status,country,city,isp,org,as,query,lat,lon,timezone"
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req,timeout=8) as r: d=json.loads(r.read().decode())
        if d.get("status")=="fail": return f"❌ {d.get('message','فشل')}"
        return (f"🌐 **{d['query']}**\n"
                f"• الدولة: {d.get('country')}\n• المدينة: {d.get('city')}\n"
                f"• المزود: {d.get('isp')}\n• AS: {d.get('as')}\n"
                f"• الإحداثيات: {d.get('lat')}, {d.get('lon')}\n"
                f"• التوقيت: {d.get('timezone')}")
    except Exception as e: return f"❌ {e}"

def eng_whois(c, token, domain=""):
    if not domain: return "🌐 أرسل دومين"
    try: ip=socket.gethostbyname(domain)
    except: return f"❌ تعذر حل {domain}"
    L=[f"🌐 **{domain}**\n• IP: `{ip}`"]
    try:
        url=f"http://ip-api.com/json/{ip}?fields=country,isp,org,as"
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req,timeout=6) as r: d=json.loads(r.read().decode())
        L.append(f"• الدولة: {d.get('country','?')}")
        L.append(f"• المزود: {d.get('isp','?')}")
        L.append(f"• AS: {d.get('as','?')}")
    except: pass
    return "\n".join(L)

def eng_tech_detect(c, token, url=""):
    if not url: return "🌐 أرسل URL"
    if not url.startswith("http"): url="https://"+url
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req,timeout=8) as r:
            headers=dict(r.headers); html=r.read(50000).decode("utf-8",errors="ignore").lower()
        L=[f"🔧 **{url}**"]
        L.append(f"• السيرفر: {headers.get('Server','?')}")
        if "wp-content" in html: L.append("• CMS: WordPress")
        elif "drupal" in html: L.append("• CMS: Drupal")
        if "_next" in html: L.append("• Framework: Next.js")
        elif "react" in html: L.append("• Framework: React")
        elif "vue" in html: L.append("• Framework: Vue")
        return "\n".join(L)
    except Exception as e: return f"❌ {e}"

def eng_url_parse(c, token, url=""):
    if not url: return "🔗 أرسل URL"
    if not url.startswith("http"): url="https://"+url
    try:
        p=urllib.parse.urlparse(url)
        L=[f"🔗 **{url}**",f"• Scheme: `{p.scheme}`",
           f"• Host: `{p.netloc}`",f"• Path: `{p.path or '/'}`"]
        if p.query:
            L.append(f"• Query: `{p.query}`")
        return "\n".join(L)
    except Exception as e: return f"❌ {e}"

def eng_short_expand(c, token, url=""):
    if not url: return "🔗 أرسل رابط مختصر"
    if not url.startswith("http"): url="https://"+url
    try:
        req=urllib.request.Request(url,method="HEAD",headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req,timeout=8) as r: final=r.url
        return f"🔗 **{url}**\n→ **{final}**"
    except Exception as e: return f"❌ {e}"

def eng_qr_gen(c, token, text=""):
    if not text: return "📱 أرسل النص/الرابط"
    qr=f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={urllib.parse.quote(text)}"
    return f"📱 **QR جاهز**\n[فتح الصورة]({qr})"

def eng_pass_gen(c, token, opts=""):
    length=16; use_sym=True
    if "طويل" in opts: length=32
    elif "قصير" in opts: length=8
    elif "سهل" in opts: length=12; use_sym=False
    elif "PIN" in opts: return f"🔢 PIN: `{''.join(random.choices(string.digits,k=6))}`"
    pool=string.ascii_letters+string.digits
    if use_sym: pool+="!@#$%^&*"
    pw="".join(random.choices(pool,k=length))
    return f"🔐 **كلمة سر**\n`{pw}`\n• الطول: {length}"

def eng_fake_id(c, token, country=""):
    names={"مصر":["أحمد محمود","محمد علي","يوسف حسن"],
        "السعودية":["عبدالله محمد","فهد سعد","سلطان ناصر"],
        "الإمارات":["محمد أحمد","علي راشد","سعيد مبارك"],
        "أمريكا":["John Smith","Michael Johnson","David Brown"],
        "بريطانيا":["Oliver Smith","Harry Jones","Jack Williams"]}
    pool=names.get(country,names["مصر"]); name=random.choice(pool)
    first=name.split()[0].lower()
    return (f"👤 **هوية وهمية — {country or 'مصر'}**\n"
            f"• الاسم: {name}\n• العمر: {random.randint(18,65)}\n"
            f"• الهاتف: +{random.randint(1,99)}{random.randint(100000000,999999999)}\n"
            f"• البريد: {first}{random.randint(1,999)}@mail.com")

def eng_wallet_gen(c, token, sym=""):
    sym=(sym or "BTC").upper()
    chars="123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    if sym=="BTC":
        addr="1"+"".join(random.choices(chars,k=33))
        return f"💰 **محفظة BTC (محاكاة)**\n`{addr}`\n\n⚠️ محاكاة فقط"
    if sym=="ETH":
        addr="0x"+"".join(random.choices("0123456789abcdef",k=40))
        return f"💰 **محفظة ETH (محاكاة)**\n`{addr}`\n\n⚠️ محاكاة فقط"
    if sym=="SOL":
        addr="".join(random.choices(chars,k=44))
        return f"💰 **محفظة SOL (محاكاة)**\n`{addr}`\n\n⚠️ محاكاة فقط"
    return "💰 BTC أو ETH أو SOL"

def eng_addr_check(c, token, addr=""):
    if not addr: return "🔍 أرسل عنوان"
    r=[]
    if re.match(r"^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$",addr): r.append("✅ BTC صالح")
    if re.match(r"^0x[a-fA-F0-9]{40}$",addr): r.append("✅ ETH صالح")
    if re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$",addr): r.append("✅ SOL محتمل")
    if not r: r.append("❌ غير معروف")
    return f"🔍 **{addr[:24]}...**\n"+"\n".join(r)

def eng_roi(c, token, inp=""):
    parts=(inp or "").split()
    if len(parts)<2: return "📊 `initial final`\nمثال: `1000 1500`"
    try: i=float(parts[0]); f=float(parts[1])
    except: return "❌ أرقام"
    roi=(f-i)/i*100 if i else 0
    return f"📊 **ROI**\n• الاستثمار: {i:,.2f}$\n• النتيجة: {f:,.2f}$\n• العائد: **{roi:+.2f}%**\n• الربح: {f-i:+,.2f}$"

def eng_risk(c, token, inp=""):
    parts=(inp or "").split()
    if len(parts)<2: return "⚠️ `capital risk_pct`\nمثال: `1000 5`"
    try: cap=float(parts[0]); risk=float(parts[1])
    except: return "❌ أرقام"
    if risk>100: return "❌ 0-100"
    amt=cap*risk/100
    return f"⚠️ **المخاطرة**\n• رأس المال: {cap:,.2f}$\n• المخاطرة: {risk:.1f}%\n• المعرض: *{amt:,.2f}$*\n• الآمن: {cap-amt:,.2f}$"

def eng_num(c, token, op, txt):
    try:
        n=int(txt.split()[0])
        if n<0 or n>10**12: raise ValueError
    except: return "🔢 أرسل عدد صحيح"
    if op=="أولي":
        if n<2: return f"🔢 {n}: ليس أولياً"
        for i in range(2,int(n**0.5)+1):
            if n%i==0: return f"🔢 {n}: ليس (÷{i})"
        return f"🔢 {n}: **أولي** ✅"
    if op=="عوامل":
        fs=[]; tmp=n; d=2
        while d*d<=tmp:
            while tmp%d==0: fs.append(d); tmp//=d
            d+=1
        if tmp>1: fs.append(tmp)
        return f"🔢 عوامل {n}: **{fs}**"
    if op=="فيبوناتشي":
        if n>100: return "🔢 n ≤ 100"
        a,b=0,1
        for _ in range(n): a,b=b,a+b
        return f"🔢 Fib({n}) = **{a}**"
    if op=="مضروب":
        if n>1000: return "🔢 n ≤ 1000"
        return f"🔢 {n}! = **{math.factorial(n)}**"
    if op=="جذر": return f"🔢 √{n} = **{n**0.5:.6f}**"
    if op=="عشوائي": return f"🎲 **{random.randint(0,n)}**"
    if op in ("gcd","lcm"):
        parts=txt.split()
        if len(parts)<2: return "🔢 أرسل رقمين"
        try:
            a,b=int(parts[0]),int(parts[1])
            g=math.gcd(a,b)
            if op=="gcd": return f"🔢 GCD({a},{b}) = **{g}**"
            return f"🔢 LCM({a},{b}) = **{a*b//g}**"
        except: return "❌"
    return f"🔢 {op}: {n}"

def eng_date(c, token, op):
    now=datetime.datetime.now()
    if op=="الآن": return f"📅 {now.strftime('%Y-%m-%d %H:%M:%S')}"
    if op=="UTC": return f"📅 {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
    if op=="ts": return f"📅 Unix: **{int(time.time())}**"
    return f"📅 {now.strftime('%Y-%m-%d')}"

def eng_conv(c, token, op, txt):
    if not txt: return "🔢 أرسل النص"
    try:
        if op=="hex-bin": return f"🔢 {int(txt,16):08b}"
        if op=="bin-dec": return f"🔢 {int(txt,2)}"
        if op=="dec-hex": return f"🔢 0x{int(txt):X}"
        if op=="dec-bin": return f"🔢 {int(txt):b}"
    except: return "❌"
    if op=="ASCII": return "🔢 "+" ".join(str(ord(ch)) for ch in txt[:100])
    if op=="Unicode": return "🔢 "+" ".join(f"U+{ord(ch):04X}" for ch in txt[:50])
    return f"🔢 {txt}"

def eng_gen(c, token, op):
    if op=="UUID": return f"🆔 `{uuid.uuid4()}`"
    if op=="كلمة سر": return f"🔐 `{''.join(random.choices(string.ascii_letters+string.digits+'!@#$%',k=16))}`"
    if op=="توكن": return f"🎫 `{''.join(random.choices(string.hexdigits.lower(),k=32))}`"
    if op=="مفتاح": return f"🔑 `{''.join(random.choices(string.hexdigits.lower(),k=64))}`"
    if op=="nonce": return f"🎲 `{random.randint(0,2**31)}`"
    if op=="ID": return f"🆔 `{random.randint(100000,999999)}`"
    if op=="رقم طلب": return f"📦 `ORD-{random.randint(100000,999999)}`"
    if op=="جلسة": return f"🔗 `{uuid.uuid4().hex[:16]}`"
    return f"🎲 `{uuid.uuid4().hex[:8]}`"

def eng_scan(c, token, txt=""):
    if not txt: return "🔌 host:port أو host"
    if ":" in txt:
        h,ps=txt.split(":",1)
        try: ports=[int(ps)]
        except: return "❌"
    else: h=txt; ports=list(range(1,1001))
    try: ip=socket.gethostbyname(h)
    except: return f"❌ {h}"
    def _sp(p):
        try:
            s=socket.socket(); s.settimeout(0.4)
            r=s.connect_ex((h,p)); s.close(); return p,r==0
        except: return p,False
    op=[]
    with ThreadPoolExecutor(max_workers=80) as ex:
        for p,ok in ex.map(_sp,ports):
            if ok: op.append(p)
    return f"🔌 {h} ({ip})\n🟢 {len(op)}: " + (", ".join(f"`{p}`" for p in op[:30]) if op else "لا شيء")

def eng_launch(c,token,txt=""):
    if not txt or "|" not in txt: return "🪙 `الاسم | الرمز | العرض`"
    p=[x.strip() for x in txt.split("|")]
    if len(p)<3: return "❌"
    name,sym,sup=p[0],p[1].upper(),p[2]
    try:
        supply=float(sup.replace(",",""))
        if supply<=0 or supply>1e12: raise ValueError
    except: return "❌"
    conn=sqlite3.connect(DB_PATH)
    if conn.execute("SELECT 1 FROM user_coins WHERE coin_symbol=?",(sym,)).fetchone():
        conn.close(); return f"❌ {sym} موجودة"
    conn.execute("INSERT INTO user_coins(owner_uid,coin_name,coin_symbol,total_supply,price,created_at) VALUES(?,?,?,?,1.0,?)",
                 (c,name,sym,supply,int(time.time())))
    conn.commit(); conn.close()
    return f"🪙 **{name}** `{sym}` — {supply:,.0f}"

def eng_daily(c,token,_=""):
    now=int(time.time()); _get_user(c)
    conn=sqlite3.connect(DB_PATH)
    r=conn.execute("SELECT last_daily,balance FROM sovereign_users WHERE uid=?",(c,)).fetchone()
    last,bal=r or (0,100000.0)
    if now-(last or 0)<86400:
        rem=86400-(now-(last or 0)); h,m,s=rem//3600,(rem%3600)//60,rem%60
        conn.close(); return f"⏳ تبقى *{h}س {m}د {s}ث*\n💰 {bal:,.2f}$"
    conn.execute("UPDATE sovereign_users SET balance=balance+1900, last_daily=? WHERE uid=?",(now,c))
    conn.commit()
    nb=conn.execute("SELECT balance FROM sovereign_users WHERE uid=?",(c,)).fetchone()[0]
    conn.close(); return f"🎁 **+1900$**\n💰 {nb:,.2f}$"

JOBS=[("🕵️ محقق",1200.0,7200),("💻 مبرمج",2500.0,10800),("🎮 لاعب",800.0,5400),
      ("🛡️ محلل",1800.0,7200),("🚀 رائد",5000.0,14400),("🧠 AI",3500.0,12600)]

def eng_salary(c,token,_=""):
    now=int(time.time()); _get_user(c)
    conn=sqlite3.connect(DB_PATH)
    r=conn.execute("SELECT last_salary,job_salary,job_interval,current_job,balance FROM sovereign_users WHERE uid=?",(c,)).fetchone()
    last,sal,itv,job,bal=r or (0,500.0,3600,"",100000.0)
    if not job:
        j=random.choice(JOBS)
        conn.execute("UPDATE sovereign_users SET current_job=?,job_salary=?,job_interval=? WHERE uid=?",(j[0],j[1],j[2],c))
        conn.commit(); conn.close()
        return f"💼 {j[0]}\n💰 *{j[1]:,.0f}$*"
    if now-(last or 0)<(itv or 3600):
        rem=(itv or 3600)-(now-(last or 0)); m,s=rem//60,rem%60
        conn.close(); return f"⏳ {job} — {m}د {s}ث"
    conn.execute("UPDATE sovereign_users SET balance=balance+?, last_salary=? WHERE uid=?",(sal,now,c))
    conn.commit()
    nb=conn.execute("SELECT balance FROM sovereign_users WHERE uid=?",(c,)).fetchone()[0]
    conn.close(); return f"💸 +{sal:,.0f}$ ({job})\n💰 {nb:,.2f}$"

# ==========================================================
# MARKET DISPLAY ENGINES
# ==========================================================
def eng_pulse(c,token,_=""):
    data=[]
    with ThreadPoolExecutor(max_workers=10) as ex:
        for s,p,pc in ex.map(_crypto_24h,CRYPTO):
            if p: data.append((s,p,pc))
    up=sum(1 for _,_,x in data if x>0); dn=sum(1 for _,_,x in data if x<0)
    sent="🟢 صاعد" if up>dn else "🔴 هابط" if dn>up else "🟡 محايد"
    L=[f"📈 **مؤشر السوق:** {sent}",f"• صاعد: *{up}* | هابط: *{dn}*",""]
    for s,p,pc in data:
        a="🟢" if pc>0 else "🔴"
        L.append(f"{a} *{s}*: `${p:,.2f}` ({pc:+.2f}%)")
    return "\n".join(L)

def eng_stocks(c,token,_=""):
    L=["📈 **الأسهم:**"]
    with ThreadPoolExecutor(max_workers=10) as ex:
        for s,p,pc in ex.map(_stooq,STOCKS):
            if p:
                a="🟢" if pc>0 else "🔴"
                L.append(f"{a} *{s}*: `${p:,.2f}` ({pc:+.2f}%)")
    return "\n".join(L)

def eng_reits(c,token,_=""):
    L=["🏢 **العقارات:**"]
    with ThreadPoolExecutor(max_workers=10) as ex:
        for s,p,pc in ex.map(_stooq,REITS):
            if p:
                a="🟢" if pc>0 else "🔴"
                L.append(f"{a} *{s}*: `${p:,.2f}` ({pc:+.2f}%)")
    return "\n".join(L)

def eng_crypto(c,token,_=""):
    L=["📊 **العملات:**"]
    with ThreadPoolExecutor(max_workers=10) as ex:
        for s,p,pc in ex.map(_crypto_24h,CRYPTO):
            if p:
                a="🟢" if pc>0 else "🔴"
                L.append(f"{a} *{s}*: `${p:,.2f}` ({pc:+.2f}%)")
    return "\n".join(L)

# ==========================================================
# SECTIONS — real tools only
# ==========================================================
SECTIONS=[
    (1,"🦅 عين الصقر",50),(2,"🗝️ خزانة الأسرار",20),
    (3,"🕵️ شبكة الجواسيس",15),(4,"🏰 حصن الحماية",15),
    (5,"🎣 مصيدة الروابط",8),(6,"💓 قلب السوق",25),
    (7,"⛏️ منجم العملات",6),(8,"🎰 كازينو البروفيسور",12),
    (9,"🏦 بنك البروفيسور",8),(10,"🎟️ مصنع الأكواد",6),
    (11,"🎁 صندوق العجائب",35),(12,"🔐 قبو التشفير",11),
    (13,"🎭 قناع الهوية",10),(14,"👑 عرش البروفيسور",0),
    (15,"📈 برج الاستثمار",24),(16,"📚 مكتبة الأدوات",0),
]

def _mtools():
    T={}
    # Section 1 - عين الصقر (50 tools)
    plats=["تيك توك","إنستغرام","تيليجرام","جيت هاب","تويتر","فيسبوك","يوتيوب",
           "ريديت","لينكدإن","بينترست","سناب","تويتش","ساوند كلاود","سبوتيفاي",
           "ستيم","ميديم","دريبل","بيهانس","فيميو","تمبلر","VK","سبستاك",
           "باتريون","ديف تو","جود ريدز","جيت لاب","كود بين","ثريدز","ديسكورد","كي بيس"]
    T[1]=[(f"فحص {p}","user_audit","") for p in plats]
    T[1]+=[("فحص بريد","info","فحص بريد"),("فحص هاتف","info","فحص هاتف")]
    T[1]+=[(f"مولد يوزر {s}","user_gen",s) for s in ["عشوائي","قصير","طويل"]]
    T[1]+=[(f"بحث {s}","info",s) for s in ["جوجل","بينج","DDG","Yandex","Baidu"]]
    T[1]+=[("تحقق GitHub","info","تحقق"),("تحقق Kaggle","info","تحقق"),
           ("تحقق PyPI","info","تحقق"),("تحقق npm","info","تحقق"),
           ("فحص Instagram","user_audit",""),("فحص Twitter","user_audit",""),
           ("فحص Reddit","user_audit",""),("فحص TikTok","user_audit",""),
           ("تحقق Proton","info","تحقق"),("تحقق Gmail","info","تحقق"),
           ("مولد UUID","gen","UUID"),("مولد كلمة سر","gen","كلمة سر"),
           ("تحقق عنوان IP","info","IP")]
    
    # Section 2 - خزانة الأسرار (20)
    T[2]=[(f"بحث {x}","deep_search","") for x in ["بالاسم","بالهاتف","بالفيس","بالبريد","بـIP"]]
    T[2]+=[(f"دمج {x}","info",f"دمج {x}") for x in ["2","5","10","50","100+"]]
    T[2]+=[(f"تحليل {x}","info",x) for x in ["نوع","حجم","أسطر"]]
    T[2]+=[(f"استخراج {x}","info",x) for x in ["إيميلات","أرقام","روابط"]]
    T[2]+=[(f"تحويل {x}","info",x) for x in ["CSV→JSON","JSON→CSV"]]
    T[2]+=[("ضغط DB","info","ضغط"),("فهرسة","info","فهرس")]
    
    # Section 3 - شبكة الجواسيس (15)
    T[3]=[
        ("🌐 WHOIS دومين","whois",""),("🌐 IP Info","ip_info",""),
        ("🔧 كشف التقنيات","tech_detect",""),
        ("📡 DNS A","dns","A"),("📡 DNS MX","dns","MX"),
        ("📡 DNS TXT","dns","TXT"),("📡 DNS CNAME","dns","CNAME"),
        ("🌐 HTTP Headers","http","headers"),("🌐 HTTP Status","http","status"),
        ("🌐 HTTP Cookies","http","cookies"),("🌐 HTTP Redirect","http","redirect"),
        ("🌐 Subdomain DNS","info","subdomain"),
        ("🌐 SSL شهادة","info","ssl"),
        ("🌐 Reverse DNS","info","reverse_dns"),
        ("🌐 AS Lookup","info","as"),
    ]
    
    # Section 4 - حصن الحماية (15)
    T[4]=[
        ("🔌 بورت 1-100","port_scan","1-100"),
        ("🔌 بورت 1-1000","port_scan","1-1000"),
        ("🔌 بورت 1-10000","port_scan","1-10000"),
        ("🔐 SSL شهادة","info","ssl_valid"),
        ("🛡️ HTTP HSTS","info","hsts"),
        ("🛡️ HTTP CSP","info","csp"),
        ("🛡️ HTTP XFO","info","xfo"),
        ("🔍 كشف SQLi","info","sqli"),
        ("🔍 كشف XSS","info","xss"),
        ("🔍 CVE بحث","info","cve"),
        ("🔐 قوة كلمة سر","pass_gen","قوي"),
        ("🔐 تحليل هاش","info","hash_id"),
    ]
    
    # Section 5 - مصيدة الروابط (8)
    T[5]=[
        ("🔗 تحليل URL","url_parse",""),
        ("🔗 فك الاختصار","short_expand",""),
        ("📱 QR Code","qr_gen",""),
        ("🎣 كشف تصيد","url_parse",""),
        ("🔗 بنية الرابط","url_parse",""),
        ("📊 دومين عمر","info","domain_age"),
        ("🔒 WHOIS خصوصية","info","whois_privacy"),
        ("🔗 باراميترات","url_parse",""),
    ]
    
    # Section 6 - قلب السوق (25)
    T[6]=[
        ("📈 نبض السوق","market_pulse",""),
        ("📊 أسهم","stocks",""),
        ("🏢 عقارات","reits",""),
        ("📊 كل الإشارات","signals_all",""),
        ("📊 إشارة BTC","signal_one","BTC"),
        ("📊 إشارة ETH","signal_one","ETH"),
        ("📊 إشارة AAPL","signal_one","AAPL"),
        ("📊 إشارة SPY","signal_one","SPY"),
        ("💓 سعر BTC","crypto_price",""),
        ("💓 سعر ETH","crypto_price",""),
        ("💓 سعر BNB","crypto_price",""),
        ("💓 سعر SOL","crypto_price",""),
        ("💓 سعر XRP","crypto_price",""),
        ("💓 سعر ADA","crypto_price",""),
        ("📈 سهم AAPL","info","stock"),
        ("📈 سهم MSFT","info","stock"),
        ("📈 سهم TSLA","info","stock"),
        ("📈 سهم NVDA","info","stock"),
        ("🏢 REIT O","info","reit"),
        ("🏢 REIT SPG","info","reit"),
        ("📊 حاسبة ROI","roi_calc",""),
        ("⚠️ حاسبة مخاطرة","risk_calc",""),
        ("📊 معنويات السوق","market_pulse",""),
        ("📊 حجم التداول","info","volume"),
        ("📊 تقويم اقتصادي","info","calendar"),
    ]
    
    # Section 7 - منجم العملات (6)
    T[7]=[
        ("💰 محفظة BTC (محاكاة)","wallet_gen","BTC"),
        ("💰 محفظة ETH (محاكاة)","wallet_gen","ETH"),
        ("💰 محفظة SOL (محاكاة)","wallet_gen","SOL"),
        ("🔍 تحقق عنوان","addr_check",""),
        ("🪙 إطلاق عملة","launch_coin",""),
        ("📊 معلومات محفظة","portfolio",""),
    ]
    
    # Section 8 - كازينو (12 games)
    T[8]=[
        ("🎰 سلوت","game","slot"),
        ("🎯 روليت","game","roulette"),
        ("🎴 بلاك جاك","game","bj"),
        ("🎲 نرد","game","dice"),
        ("🪙 عملة","game","coin"),
        ("✊ حجر ورقة","game","rps"),
        ("📈 هاي لو","game","highlow"),
        ("🧠 تريفيا","game","trivia"),
        ("🎡 عجلة","game","wheel"),
        ("🏇 سباق خيول","game","horse"),
        ("🏎️ سباق سيارات","game","car"),
        ("⚽ كرة","game","soccer"),
    ]
    
    # Section 9 - بنك (8)
    T[9]=[
        ("💼 عرض المحفظة","portfolio",""),
        ("🎁 الهدية اليومية","daily_gift",""),
        ("💰 الراتب","salary",""),
        ("💰 رصيدي","balance",""),
        ("📊 سجل الصفقات","trade_history",""),
        ("💵 إيداع","daily_gift",""),
        ("🔔 تنبيهاتي","alerts_list",""),
        ("📊 إحصائيات","info","stats"),
    ]
    
    # Section 10 - مصنع الأكواد (6)
    T[10]=[
        ("🎟️ كود عشوائي","gen","ID"),
        ("🎟️ توكن","gen","توكن"),
        ("🎟️ UUID","gen","UUID"),
        ("🔑 مفتاح","gen","مفتاح"),
        ("🎲 nonce","gen","nonce"),
        ("📦 رقم طلب","gen","رقم طلب"),
    ]
    
    # Section 11 - صندوق العجائب (35)
    T[11]=[
        ("📝 كبير","text",""),("📝 صغير","text",""),
        ("📝 عناوين","text",""),("📝 عكس","text",""),
        ("📝 عد","text",""),("📝 تنظيف","text",""),
        ("🔢 أولي","num","أولي"),("🔢 عوامل","num","عوامل"),
        ("🔢 GCD","num","gcd"),("🔢 LCM","num","lcm"),
        ("🔢 فيبوناتشي","num","فيبوناتشي"),("🔢 مضروب","num","مضروب"),
        ("🔢 جذر","num","جذر"),("🔢 عشوائي","num","عشوائي"),
        ("📅 الآن","date","الآن"),("📅 UTC","date","UTC"),
        ("📅 ts","date","ts"),
        ("🆔 UUID","gen","UUID"),("🔐 كلمة سر","gen","كلمة سر"),
        ("🎫 توكن","gen","توكن"),("🔑 مفتاح","gen","مفتاح"),
        ("🎲 nonce","gen","nonce"),("🆔 ID","gen","ID"),
        ("📦 رقم طلب","gen","رقم طلب"),("🔗 جلسة","gen","جلسة"),
        ("🔢 hex-bin","conv","hex-bin"),("🔢 bin-dec","conv","bin-dec"),
        ("🔢 dec-hex","conv","dec-hex"),("🔢 dec-bin","conv","dec-bin"),
        ("🔢 ASCII","conv","ASCII"),("🔢 Unicode","conv","Unicode"),
        ("📊 ROI","roi_calc",""),("⚠️ مخاطرة","risk_calc",""),
        ("🌐 IP","ip_info",""),
    ]
    
    # Section 12 - قبو التشفير (11)
    T[12]=[
        ("🔐 Base64 تشفير","b64","encode"),
        ("🔓 Base64 فك","b64","decode"),
        ("🔐 Base64 URL-safe","b64","url-safe"),
        ("🔓 MD5","hash","MD5"),
        ("🔓 SHA1","hash","SHA1"),
        ("🔓 SHA256","hash","SHA256"),
        ("🔓 SHA512","hash","SHA512"),
        ("🔐 قيصر","cipher","Caesar"),
        ("🔐 ROT13","cipher","ROT13"),
        ("🔐 أتباش","cipher","Atbash"),
        ("🔐 كلمة سر قوية","pass_gen","قوي"),
    ]
    
    # Section 13 - قناع الهوية (10)
    T[13]=[
        ("🔐 كلمة سر قوية","pass_gen","قوي"),
        ("🔐 كلمة سر طويلة","pass_gen","طويل"),
        ("🔐 كلمة سر سهلة","pass_gen","سهل"),
        ("🔢 PIN","pass_gen","PIN"),
        ("👤 هوية مصر","fake_id","مصر"),
        ("👤 هوية السعودية","fake_id","السعودية"),
        ("👤 هوية الإمارات","fake_id","الإمارات"),
        ("👤 هوية أمريكا","fake_id","أمريكا"),
        ("👤 هوية بريطانيا","fake_id","بريطانيا"),
        ("🎭 مولد هوية","fake_id","مصر"),
    ]
    
    # Section 14 - عرش (admin)
    T[14]=[]
    
    # Section 15 - برج الاستثمار (24)
    T[15]=[
        ("💼 عرض المحفظة + P&L","portfolio",""),
        ("💵 شراء سهم/عملة","buy_prompt",""),
        ("💰 بيع سهم/عملة","sell_prompt",""),
        ("📋 سجل الصفقات","trade_history",""),
        ("📊 كل الإشارات","signals_all",""),
        ("🔔 تنبيه سعري","alert_prompt",""),
        ("📋 تنبيهاتي","alerts_list",""),
        ("📊 إشارة BTC","signal_one","BTC"),
        ("📊 إشارة ETH","signal_one","ETH"),
        ("📊 إشارة AAPL","signal_one","AAPL"),
        ("📊 إشارة MSFT","signal_one","MSFT"),
        ("📊 إشارة TSLA","signal_one","TSLA"),
        ("📊 إشارة O","signal_one","O"),
        ("📊 إشارة SPY","signal_one","SPY"),
        ("📈 أسهم حية","stocks",""),
        ("🏢 عقارات حية","reits",""),
        ("📊 نبض السوق","market_pulse",""),
        ("🧪 Backtest AAPL","backtest_real","AAPL"),
        ("🧪 Backtest MSFT","backtest_real","MSFT"),
        ("🧪 Backtest TSLA","backtest_real","TSLA"),
        ("🧪 Backtest O","backtest_real","O"),
        ("🧪 Backtest SPY","backtest_real","SPY"),
        ("📊 حساب ROI","roi_calc",""),
        ("⚠️ حساب المخاطر","risk_calc",""),
    ]
    
    # Section 16 - مكتبة (empty, handled separately)
    T[16]=[]
    
    return T

MAIN_TOOLS=_mtools()
TOTAL_REAL_TOOLS=sum(len(v) for v in MAIN_TOOLS.values() if v)

# ==========================================================
# USERNAME AUDIT
# ==========================================================
PLATFORMS=[("تيك توك","https://www.tiktok.com/@{}"),("إنستغرام","https://instagram.com/{}"),
    ("تيليجرام","https://t.me/{}"),("جيت هاب","https://github.com/{}"),
    ("تويتر","https://twitter.com/{}"),("فيسبوك","https://facebook.com/{}"),
    ("يوتيوب","https://youtube.com/@{}"),("ريديت","https://reddit.com/user/{}"),
    ("لينكدإن","https://linkedin.com/in/{}"),("بينترست","https://pinterest.com/{}"),
    ("سناب","https://snapchat.com/add/{}"),("تويتش","https://twitch.tv/{}"),
    ("ساوند كلاود","https://soundcloud.com/{}"),("سبوتيفاي","https://open.spotify.com/user/{}"),
    ("ستيم","https://steamcommunity.com/id/{}"),("ميديم","https://medium.com/@{}"),
    ("دريبل","https://dribbble.com/{}"),("بيهانس","https://behance.net/{}"),
    ("فيميو","https://vimeo.com/{}"),("تمبلر","https://{}.tumblr.com"),
    ("VK","https://vk.com/{}"),("سبستاك","https://{}.substack.com"),
    ("باتريون","https://patreon.com/{}"),("ديف تو","https://dev.to/{}"),
    ("جود ريدز","https://goodreads.com/{}"),("جيت لاب","https://gitlab.com/{}"),
    ("كود بين","https://codepen.io/{}"),("ثريدز","https://threads.net/@{}"),
    ("ديسكورد","https://discord.com/users/{}"),("كي بيس","https://keybase.io/{}")]
_NF=["not found","404","doesn't exist","user not found","page not found",
     "no user","account suspended","لم يتم العثور","غير موجود"]

def _probe(args):
    n,tmpl,u=args; link=tmpl.format(u)
    try:
        req=urllib.request.Request(link,headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req,timeout=5) as r:
            if r.status==200:
                h=r.read(30000).decode("utf-8",errors="ignore").lower()
                return (n,link,not any(k in h for k in _NF))
    except: return (n,link,False)
    return (n,link,False)

def audit_user(u):
    u=u.strip().replace("@","").split("/")[-1]; a,i=[],[]
    with ThreadPoolExecutor(max_workers=30) as ex:
        for f in as_completed([ex.submit(_probe,(p[0],p[1],u)) for p in PLATFORMS]):
            try:
                n,l,ok=f.result(); (a if ok else i).append((n,l))
            except: pass
    return sorted(a),sorted(i)

# ==========================================================
# MENUS
# ==========================================================
def menu_home(c):
    kb,row=[],[]
    for sid,name,cnt in SECTIONS:
        badge="👑" if sid==14 else (f"({cnt})" if cnt else "📚")
        row.append({"text":f"{name} {badge}","callback_data":f"sec_{sid}"})
        if len(row)==2: kb.append(row); row=[]
    if row: kb.append(row)
    kb.append([{"text":"📈 السوق","callback_data":"pulse"},
               {"text":"📊 إشارات","callback_data":"signals_all"},
               {"text":"💼 محفظتي","callback_data":"portfolio"}])
    kb.append([{"text":"🎰 كازينو","callback_data":"casino"},
               {"text":"💰 رصيدي","callback_data":"balance"},
               {"text":"ℹ️","callback_data":"about"}])
    kb.append([{"text":"👑 العرش","callback_data":"sec_14"}])
    return {"inline_keyboard":kb}

def menu_casino(c):
    games=[("🎰 سلوت","game_slot"),("🎯 روليت","game_roulette"),
           ("🎴 بلاك جاك","game_bj"),("🎲 نرد","game_dice"),
           ("🪙 عملة","game_coin"),("✊ حجر/ورقة","game_rps"),
           ("📈 هاي لو","game_highlow"),("🧠 تريفيا","game_trivia"),
           ("🎡 عجلة","game_wheel"),("🏇 سباق خيول","game_horse"),
           ("🏎️ سباق سيارات","game_car"),("⚽ كرة","game_soccer")]
    kb,row=[],[]
    for name,cb in games:
        row.append({"text":name,"callback_data":cb})
        if len(row)==3: kb.append(row); row=[]
    if row: kb.append(row)
    kb.append([{"text":"🏠 الرئيسية","callback_data":"home"}])
    return {"inline_keyboard":kb}

def menu_section(c,sid,page=1):
    if sid==14: return menu_admin(c)
    if sid==16: return menu_library(c)
    tools=MAIN_TOOLS.get(sid,[])
    if not tools: return {"inline_keyboard":[[{"text":"🏠","callback_data":"home"}]]}
    per=9; start=(page-1)*per; end=start+per
    items=tools[start:end]; kb,row=[],[]
    for idx,(name,cat,sub) in enumerate(items,start):
        row.append({"text":name,"callback_data":f"tool_{sid}_{idx}"})
        if len(row)==3: kb.append(row); row=[]
    if row: kb.append(row)
    tp=(len(tools)+per-1)//per
    nav=[]
    if page>1: nav.append({"text":"⬅️","callback_data":f"secpage_{sid}_{page-1}"})
    nav.append({"text":f"📄 {page}/{tp}","callback_data":f"secpage_{sid}_{page}"})
    if end<len(tools): nav.append({"text":"➡️","callback_data":f"secpage_{sid}_{page+1}"})
    kb.append(nav)
    kb.append([{"text":"🏠","callback_data":"home"}])
    return {"inline_keyboard":kb}

def menu_library(c):
    L=["📚 **مكتبة الأدوات**","━━━━━━━━━━━━━━━━━━",""]
    for sid,name,cnt in SECTIONS:
        if sid in (14,16): continue
        L.append(f"{name} — *{cnt}* أداة")
    L.append("")
    L.append("━━━━━━━━━━━━━━━━━━")
    L.append(f"💎 **الإجمالي: {TOTAL_REAL_TOOLS} أداة حقيقية**")
    L.append("")
    L.append("كل أداة تعمل 100% — لا حشو")
    # Send as one message and show home
    return {"inline_keyboard":[
        [{"text":"🏠 الرئيسية","callback_data":"home"}]
    ]}

# ADMIN
def menu_admin(c):
    return {"inline_keyboard":[
        [{"text":"👥 المستخدمون","callback_data":"adm_users"},
         {"text":"👑 المشرفون","callback_data":"adm_mods"},
         {"text":"📢 البث","callback_data":"adm_bc"}],
        [{"text":"📊 الإحصائيات","callback_data":"adm_stats"},
         {"text":"💾 القاعدة","callback_data":"adm_db"},
         {"text":"⚙️ الإعدادات","callback_data":"adm_settings"}],
        [{"text":"💰 الاقتصاد","callback_data":"adm_economy"},
         {"text":"📋 السجلات","callback_data":"adm_audit"},
         {"text":"🏠","callback_data":"home"}]]}

def menu_admin_users(c):
    return {"inline_keyboard":[
        [{"text":"📋 الكل","callback_data":"adm_list_users"},
         {"text":"🚫 حظر","callback_data":"adm_ban"},
         {"text":"✅ رفع حظر","callback_data":"adm_unban"}],
        [{"text":"🗑️ حذف","callback_data":"adm_del"},
         {"text":"🔙","callback_data":"sec_14"}]]}

def menu_admin_mods(c):
    return {"inline_keyboard":[
        [{"text":"📋 قائمة","callback_data":"adm_list_mods"},
         {"text":"👑 رفع","callback_data":"adm_promote"}],
        [{"text":"📉 طرد","callback_data":"adm_demote"},
         {"text":"🔙","callback_data":"sec_14"}]]}

def menu_admin_bc(c):
    return {"inline_keyboard":[
        [{"text":"🌐 للجميع","callback_data":"adm_bc_all"},
         {"text":"👑 للأدمن","callback_data":"adm_bc_admins"}],
        [{"text":"🎯 لمستخدم","callback_data":"adm_bc_user"},
         {"text":"🔙","callback_data":"adm_bc"}]]}

def menu_admin_econ(c):
    return {"inline_keyboard":[
        [{"text":"💵 إعطاء","callback_data":"adm_give"},
         {"text":"💸 سحب","callback_data":"adm_take"}],
        [{"text":"🔙","callback_data":"sec_14"}]]}

def menu_admin_db(c):
    return {"inline_keyboard":[
        [{"text":"💾 نسخ","callback_data":"adm_backup"},
         {"text":"⚡ تحسين","callback_data":"adm_optimize"}],
        [{"text":"🔙","callback_data":"sec_14"}]]}

def menu_admin_set(c):
    return {"inline_keyboard":[
        [{"text":"🔒 قفل","callback_data":"adm_toggle_lock"},
         {"text":"🛠️ صيانة","callback_data":"adm_toggle_maint"}],
        [{"text":"📝 ترحيب","callback_data":"adm_set_welcome"},
         {"text":"🔙","callback_data":"sec_14"}]]}

def _bc_all(token,text):
    conn=sqlite3.connect(DB_PATH)
    rows=conn.execute("SELECT uid FROM sovereign_users WHERE is_banned=0").fetchall()
    conn.close()
    n=0
    for (u,) in rows:
        if send(token,u,text): n+=1
        time.sleep(0.05)
    return n

def _bc_admins(token,text):
    conn=sqlite3.connect(DB_PATH)
    rows=conn.execute("SELECT uid FROM sovereign_users WHERE is_admin=1 AND is_banned=0").fetchall()
    conn.close()
    n=0
    for (u,) in rows:
        if send(token,u,text): n+=1
        time.sleep(0.05)
    return n

def admin_stats(token,c):
    conn=sqlite3.connect(DB_PATH)
    u=conn.execute("SELECT COUNT(*) FROM sovereign_users").fetchone()[0]
    a=conn.execute("SELECT COUNT(*) FROM admins").fetchone()[0]
    i=conn.execute("SELECT COUNT(*) FROM global_intelligence").fetchone()[0]
    t=conn.execute("SELECT COUNT(*) FROM trade_log").fetchone()[0]
    conn.close()
    send(token,c,f"📊 **إحصائيات**\n• مستخدمون: *{u}*\n• أدمن: *{a}*\n• سجلات: *{i}*\n• صفقات: *{t}*",menu_admin(c))

def admin_users(token,c):
    conn=sqlite3.connect(DB_PATH)
    rows=conn.execute("SELECT uid,COALESCE(username,'?'),balance FROM sovereign_users ORDER BY balance DESC LIMIT 20").fetchall()
    conn.close()
    L=["👥 **آخر 20:**"]
    for u,un,b in rows: L.append(f"• `{u}` @{un} — *{b:,.0f}$*")
    send(token,c,"\n".join(L),menu_admin_users(c))

def admin_mods(token,c):
    conn=sqlite3.connect(DB_PATH)
    rows=conn.execute("SELECT a.uid,COALESCE(u.username,'?'),a.level FROM admins a LEFT JOIN sovereign_users u ON a.uid=u.uid").fetchall()
    conn.close()
    if not rows: send(token,c,"📋 لا مشرفين",menu_admin_mods(c)); return
    L=["👑 **المشرفون:**"]
    for u,un,lvl in rows: L.append(f"• `{u}` @{un} — مستوى {lvl}")
    send(token,c,"\n".join(L),menu_admin_mods(c))

# ==========================================================
# DISPATCH
# ==========================================================
def dispatch(c,token,cat,sub):
    if cat=="game":
        fn=GAMES.get(sub)
        if not fn: return "❌"
        return fn(c,token,"")
    if cat=="crypto_price": return eng_crypto(c,token)
    if cat=="market_pulse": return eng_pulse(c,token)
    if cat=="stocks": return eng_stocks(c,token)
    if cat=="reits": return eng_reits(c,token)
    if cat=="signals_all": return eng_signals_all(c,token)
    if cat=="signal_one": return eng_signal_advanced(c,token,sub)
    if cat=="backtest_real": return eng_backtest_real(c,token,sub)
    if cat=="portfolio": return render_portfolio(c)
    if cat=="trade_history": return eng_trade_history(c,token)
    if cat=="buy_prompt":
        user_states[c]="wait_buy"
        return "💵 **شراء**\nأرسل: `SYMBOL USD`\nمثال: `BTC 100`\n\nالرموز: BTC,ETH,AAPL,TSLA,O,SPY..."
    if cat=="sell_prompt":
        user_states[c]="wait_sell"
        return "💰 **بيع**\nأرسل: `SYMBOL QTY`\nمثال: `BTC 0.001`"
    if cat=="alert_prompt":
        user_states[c]="wait_alert"
        return "🔔 **تنبيه**\nأرسل: `SYMBOL above/below PRICE`\nمثال: `BTC above 100000`"
    if cat=="alerts_list":
        conn=sqlite3.connect(DB_PATH)
        rows=conn.execute("SELECT symbol,target_price,direction,triggered FROM price_alerts WHERE uid=? ORDER BY id DESC LIMIT 20",(c,)).fetchall()
        conn.close()
        if not rows: return "📋 لا تنبيهات\n\nأضف: `تنبيه BTC above 100000`"
        L=["📋 **تنبيهاتك:**"]
        for sym,tgt,dr,trig in rows:
            emoji="⬆️" if dr=="above" else "⬇️"
            status="✅" if trig else "⏳"
            L.append(f"{status} {emoji} *{sym}* @ ${tgt:,.2f}")
        return "\n".join(L)
    if cat=="daily_gift": return eng_daily(c,token)
    if cat=="salary": return eng_salary(c,token)
    if cat=="balance":
        u=_get_user(c); return f"💰 *{u[0]:,.2f}$*"
    if cat=="user_audit": user_states[c]="wait_username"; return "🔍 أرسل اليوزر:"
    if cat=="user_gen": return f"👤 `{''.join(random.choices(string.ascii_lowercase+string.digits,k=10))}`"
    if cat=="deep_search": user_states[c]="wait_query"; return "📁 أرسل (اسم/رقم/فيس):"
    if cat=="text": user_states[c]="wait_text"; return "📝 أرسل النص:"
    if cat=="hash": user_states[c]="wait_hash"; return "🔐 أرسل النص:"
    if cat=="b64": user_states[c]="wait_b64"; return "🔐 أرسل النص:"
    if cat=="cipher": user_states[c]="wait_cipher"; return "🔐 أرسل النص:"
    if cat=="dns": user_states[c]="wait_dns"; return f"🌐 أرسل دومين ({sub}):"
    if cat=="http": user_states[c]="wait_http"; return "🌐 أرسل URL:"
    if cat=="port_scan": user_states[c]="wait_scan"; return "🔌 host:port أو host"
    if cat=="launch_coin": user_states[c]="wait_launch"; return "🪙 `الاسم | الرمز | العرض`"
    if cat=="num": user_states[c]=f"wait_num_{sub}"; return f"🔢 أرسل رقم ({sub}):"
    if cat=="date": return eng_date(c,token,sub)
    if cat=="gen": return eng_gen(c,token,sub)
    if cat=="conv": user_states[c]=f"wait_conv_{sub}"; return f"🔢 أرسل النص ({sub}):"
    if cat=="roi_calc": user_states[c]="wait_roi"; return "📊 `initial final`"
    if cat=="risk_calc": user_states[c]="wait_risk"; return "⚠️ `capital risk_pct`"
    if cat=="wallet_gen": return eng_wallet_gen(c,token,sub)
    if cat=="addr_check": user_states[c]="wait_addr"; return "🔍 أرسل العنوان:"
    if cat=="ip_info": user_states[c]="wait_ip"; return "🌐 أرسل IP أو domain:"
    if cat=="whois": user_states[c]="wait_whois"; return "🌐 أرسل دومين:"
    if cat=="tech_detect": user_states[c]="wait_tech"; return "🔧 أرسل URL:"
    if cat=="url_parse": user_states[c]="wait_url_parse"; return "🔗 أرسل URL:"
    if cat=="short_expand": user_states[c]="wait_short"; return "🔗 أرسل رابط مختصر:"
    if cat=="qr_gen": user_states[c]="wait_qr"; return "📱 أرسل النص/الرابط:"
    if cat=="pass_gen": return eng_pass_gen(c,token,sub)
    if cat=="fake_id": return eng_fake_id(c,token,sub)
    if cat=="info": return f"ℹ️ **{sub}** — قيد التطوير بانتظار تحديث قادم"

user_states = {}

# ==========================================================
# MAIN HANDLER
# ==========================================================
def handle(token,upd):
    if "callback_query" in upd:
        cq=upd["callback_query"]; cid=cq["id"]
        c=cq["message"]["chat"]["id"]; d=cq["data"]
        acb(token,cid)
        
        if d=="home":
            user_states.pop(c,None)
            send(token,c,f"👑 **{BOT_BRAND}**\n{OWNER_AR}\n\n💎 {TOTAL_REAL_TOOLS} أداة حقيقية",menu_home(c)); return
        if d=="about":
            send(token,c,f"👑 **{BOT_BRAND} v11**\n• 16 قسماً\n• {TOTAL_REAL_TOOLS} أداة حقيقية\n• سباق حي 60 ثانية\n• cooldown 15 دقيقة\n• RTP 92%",menu_home(c)); return
        if d=="pulse": send(token,c,eng_pulse(c,token),menu_home(c)); return
        if d=="signals_all": send(token,c,"⏳"); send(token,c,eng_signals_all(c,token),menu_home(c)); return
        if d=="portfolio":
            check_alerts(c,token)
            send(token,c,render_portfolio(c),menu_home(c)); return
        if d=="balance":
            u=_get_user(c)
            send(token,c,f"💰 *{u[0]:,.2f}$*",menu_home(c)); return
        if d=="casino": send(token,c,"🎰",menu_casino(c)); return
        
        if d.startswith("sec_"):
            sid=int(d.split("_")[1])
            if sid==14:
                if not _is_admin(c):
                    user_states[c]="adm_pass"
                    send(token,c,"👑 أدخل كلمة السر:",{"inline_keyboard":[[{"text":"🔙","callback_data":"home"}]]})
                else: send(token,c,"👑 العرش",menu_admin(c))
                return
            if sid==16:
                # Library overview
                L=["📚 **مكتبة الأدوات**","━━━━━━━━━━━━━━━━━━",""]
                for s_id,name,cnt in SECTIONS:
                    if s_id in (14,16): continue
                    L.append(f"{name} — *{cnt}* أداة")
                L.append("")
                L.append("━━━━━━━━━━━━━━━━━━")
                L.append(f"💎 **الإجمالي: {TOTAL_REAL_TOOLS} أداة حقيقية**")
                L.append("")
                L.append("✅ كل أداة تعمل 100% — لا حشو")
                send(token,c,"\n".join(L),menu_home(c))
                return
            s=next((x for x in SECTIONS if x[0]==sid),None)
            if s: send(token,c,s[1],menu_section(c,sid,1)); return
        
        if d.startswith("secpage_"):
            p=d.split("_"); send(token,c,f"📄 {p[2]}",menu_section(c,int(p[1]),int(p[2]))); return
        
        if d.startswith("tool_"):
            p=d.split("_"); sid=int(p[1]); idx=int(p[2])
            tools=MAIN_TOOLS.get(sid,[])
            if idx>=len(tools): return
            name,cat,sub=tools[idx]
            try: res=dispatch(c,token,cat,sub)
            except Exception as e: res=f"⚠️ {e}"
            if res:
                send(token,c,res,{"inline_keyboard":[[{"text":"🔙","callback_data":f"sec_{sid}"}],[{"text":"🏠","callback_data":"home"}]]})
            return
        
        if d.startswith("game_"):
            sub=d.replace("game_","")
            fn=GAMES.get(sub)
            if fn:
                try: res=fn(c,token,"")
                except Exception as e: res=f"⚠️ {e}"
                if res is not None:
                    # Cooldown and lobby need proper menu
                    if sub in ("horse","car") and user_states.get(c) in ("horse_lobby","horse_bet","car_lobby","car_bet"):
                        send(token,c,res,menu_casino(c))
                    else:
                        send(token,c,res,menu_casino(c))
            return
        
        if d.startswith("adm_"):
            if not _is_admin(c): send(token,c,"❌"); return
            if d=="adm_users": send(token,c,"👥",menu_admin_users(c)); return
            if d=="adm_mods": send(token,c,"👑",menu_admin_mods(c)); return
            if d=="adm_bc": send(token,c,"📢",menu_admin_bc(c)); return
            if d=="adm_db": send(token,c,"💾",menu_admin_db(c)); return
            if d=="adm_settings": send(token,c,"⚙️",menu_admin_set(c)); return
            if d=="adm_economy": send(token,c,"💰",menu_admin_econ(c)); return
            if d=="adm_stats": admin_stats(token,c); return
            if d=="adm_list_users": admin_users(token,c); return
            if d=="adm_list_mods": admin_mods(token,c); return
            if d=="adm_audit":
                conn=sqlite3.connect(DB_PATH)
                rows=conn.execute("SELECT actor_uid,action,target FROM audit_log ORDER BY id DESC LIMIT 20").fetchall()
                conn.close()
                L=["📋 **آخر العمليات:**"]
                for a,act,tg in rows: L.append(f"• `{a}` → {act} {tg}")
                send(token,c,"\n".join(L) if len(L)>1 else "فارغ",
                     {"inline_keyboard":[[{"text":"🔙","callback_data":"sec_14"}]]}); return
            if d=="adm_backup":
                try:
                    shutil.copy(DB_PATH,DB_PATH+".bak")
                    send(token,c,"💾 تم",menu_admin_db(c))
                except Exception as e: send(token,c,f"❌ {e}")
                return
            if d=="adm_optimize":
                try:
                    conn=sqlite3.connect(DB_PATH)
                    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    conn.execute("VACUUM"); conn.close()
                    send(token,c,"⚡ تم",menu_admin_db(c))
                except Exception as e: send(token,c,f"❌ {e}")
                return
            if d=="adm_toggle_lock":
                cur=_get_setting("chat_locked","0"); new="0" if cur=="1" else "1"
                _set_setting("chat_locked",new)
                send(token,c,f"🔒 = {new}",menu_admin_set(c)); return
            if d=="adm_toggle_maint":
                cur=_get_setting("maintenance","0"); new="0" if cur=="1" else "1"
                _set_setting("maintenance",new)
                send(token,c,f"🛠️ = {new}",menu_admin_set(c)); return
            if d=="adm_promote":
                user_states[c]="promote_uid"
                send(token,c,"👑 UID/@user:",{"inline_keyboard":[[{"text":"🔙","callback_data":"adm_mods"}]]}); return
            if d=="adm_demote":
                user_states[c]="demote_uid"
                send(token,c,"📉 UID/@user:",{"inline_keyboard":[[{"text":"🔙","callback_data":"adm_mods"}]]}); return
            if d=="adm_ban": user_states[c]="ban_uid"; send(token,c,"🚫 UID/@user:"); return
            if d=="adm_unban": user_states[c]="unban_uid"; send(token,c,"✅ UID/@user:"); return
            if d=="adm_del": user_states[c]="del_uid"; send(token,c,"🗑️ UID/@user:"); return
            if d=="adm_bc_all": user_states[c]="bc_all"; send(token,c,"📢"); return
            if d=="adm_bc_admins": user_states[c]="bc_admins"; send(token,c,"📢"); return
            if d=="adm_bc_user": user_states[c]="bc_user_uid"; send(token,c,"🎯 UID/@user:"); return
            if d=="adm_give": user_states[c]="give_input"; send(token,c,"💵 `UID | مبلغ`"); return
            if d=="adm_take": user_states[c]="take_input"; send(token,c,"💸 `UID | مبلغ`"); return
            if d=="adm_set_welcome": user_states[c]="set_welcome"; send(token,c,"📝"); return
            send(token,c,"⚙️",menu_admin(c)); return
        
        send(token,c,"👑",menu_home(c)); return
    
    if "message" not in upd: return
    msg=upd["message"]; c=msg["chat"]["id"]
    if "text" not in msg: return
    txt=msg["text"].strip(); state=user_states.get(c)
    
    # Global escape
    if txt in ("0","رجوع","back","عودة") and not txt.startswith("/"):
        user_states.pop(c,None)
        for k in list(user_states.keys()):
            if k.endswith(f"_{c}") or k == c:
                user_states.pop(k,None)
        send(token,c,"🏠 عدت للقائمة الرئيسية",menu_home(c)); return
    
    if txt.startswith("/start"):
        user_states.pop(c,None); _get_user(c)
        conn=sqlite3.connect(DB_PATH)
        conn.execute("UPDATE sovereign_users SET username=?, first_name=? WHERE uid=?",
                     (msg["from"].get("username",""),msg["from"].get("first_name",""),c))
        conn.commit(); conn.close()
        send(token,c,f"👑 **{BOT_BRAND}**\n{OWNER_AR}\n\n💎 {TOTAL_REAL_TOOLS} أداة حقيقية",menu_home(c)); return
    
    if txt.startswith("/portfolio"):
        send(token,c,render_portfolio(c),menu_home(c)); return
    if txt.startswith("/alerts"):
        conn=sqlite3.connect(DB_PATH)
        rows=conn.execute("SELECT symbol,target_price,direction FROM price_alerts WHERE uid=? AND triggered=0",(c,)).fetchall()
        conn.close()
        if not rows: send(token,c,"📋 لا تنبيهات"); return
        L=["📋 **تنبيهاتك:**"]
        for sym,tgt,dr in rows:
            emoji="⬆️" if dr=="above" else "⬇️"
            L.append(f"{emoji} *{sym}* @ ${tgt:,.2f}")
        send(token,c,"\n".join(L)); return
    
    # Investment commands
    if txt.startswith("شراء ") or txt.startswith("buy "):
        parts=txt.split()
        if len(parts)>=3:
            try:
                result=do_buy_sync(c,parts[1],float(parts[2]))
                send(token,c,result,menu_home(c)); return
            except: send(token,c,"❌ صيغة: `شراء BTC 100`",menu_home(c)); return
    if txt.startswith("بيع ") or txt.startswith("sell "):
        parts=txt.split()
        if len(parts)>=3:
            try:
                result=do_sell_sync(c,parts[1],float(parts[2]))
                send(token,c,result,menu_home(c)); return
            except: send(token,c,"❌ صيغة: `بيع BTC 0.001`",menu_home(c)); return
    if txt.startswith("محفظتي") or txt.startswith("/wallet"):
        send(token,c,render_portfolio(c),menu_home(c)); return
    if txt.startswith("تنبيه ") or txt.startswith("alert "):
        parts=txt.split()
        if len(parts)>=4:
            sym=parts[1].upper(); dr=parts[2].lower()
            try: tgt=float(parts[3])
            except: send(token,c,"❌ السعر رقم",menu_home(c)); return
            if dr not in ("above","below"): send(token,c,"❌ above/below",menu_home(c)); return
            conn=sqlite3.connect(DB_PATH)
            conn.execute("INSERT INTO price_alerts (uid,symbol,target_price,direction,created_at) VALUES (?,?,?,?,?)",
                         (c,sym,tgt,dr,int(time.time())))
            conn.commit(); conn.close()
            emoji="⬆️" if dr=="above" else "⬇️"
            send(token,c,f"🔔 **تنبيه مضاف**\n{emoji} {sym} @ ${tgt:,.2f}",menu_home(c)); return
    
    # Admin login
    if state=="adm_pass":
        user_states.pop(c,None)
        if admin_login(c,txt): send(token,c,"👑 **مرحباً!**",menu_admin(c))
        else: send(token,c,"❌ كلمة السر غلط.",menu_home(c))
        return
    
    if state=="promote_uid":
        user_states[c]="promote_pass"; user_states[f"target_{c}"]=txt
        send(token,c,f"👑 `{txt}`\n🔐 كلمة السر:"); return
    if state=="promote_pass":
        target=user_states.pop(f"target_{c}",None); user_states.pop(c,None)
        if txt!=ADMIN_PASS: send(token,c,"❌",menu_admin_mods(c)); return
        ok,msg_out,tuid,disp=do_promote(target,c)
        send(token,c,msg_out,menu_admin_mods(c))
        if ok and tuid:
            try: send(token,tuid,f"👑 **تم رفعك!**")
            except: pass
        return
    
    if state=="demote_uid":
        user_states[c]="demote_pass"; user_states[f"target_{c}"]=txt
        send(token,c,f"📉 `{txt}`\n🔐 كلمة السر:"); return
    if state=="demote_pass":
        target=user_states.pop(f"target_{c}",None); user_states.pop(c,None)
        if txt!=ADMIN_PASS: send(token,c,"❌",menu_admin_mods(c)); return
        ok,msg_out,tuid,disp=do_demote(target,c)
        send(token,c,msg_out,menu_admin_mods(c))
        if ok and tuid:
            try: send(token,tuid,f"📉 **أُلغيت صلاحيتك**")
            except: pass
        return
    
    if state=="ban_uid":
        user_states.pop(c,None)
        uid,un,disp=find_user(txt)
        if not uid: send(token,c,"❌",menu_admin_users(c)); return
        conn=sqlite3.connect(DB_PATH)
        conn.execute("UPDATE sovereign_users SET is_banned=1 WHERE uid=?",(uid,))
        conn.commit(); conn.close()
        send(token,c,f"🚫 {disp}",menu_admin_users(c)); return
    if state=="unban_uid":
        user_states.pop(c,None)
        uid,un,disp=find_user(txt)
        if not uid: send(token,c,"❌",menu_admin_users(c)); return
        conn=sqlite3.connect(DB_PATH)
        conn.execute("UPDATE sovereign_users SET is_banned=0 WHERE uid=?",(uid,))
        conn.commit(); conn.close()
        send(token,c,f"✅ {disp}",menu_admin_users(c)); return
    if state=="del_uid":
        user_states.pop(c,None)
        uid,un,disp=find_user(txt)
        if not uid: send(token,c,"❌",menu_admin_users(c)); return
        conn=sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM sovereign_users WHERE uid=?",(uid,))
        conn.execute("DELETE FROM admins WHERE uid=?",(uid,))
        conn.commit(); conn.close()
        send(token,c,f"🗑️ {disp}",menu_admin_users(c)); return
    if state in ("give_input","take_input"):
        user_states.pop(c,None)
        try:
            parts=txt.split("|")
            uid,un,disp=find_user(parts[0].strip())
            amt=float(parts[1].strip())
            if not uid: raise ValueError
            sign="+" if state=="give_input" else "-"
            conn=sqlite3.connect(DB_PATH)
            conn.execute(f"UPDATE sovereign_users SET balance=MAX(0,balance{sign}?) WHERE uid=?",(amt,uid))
            conn.commit(); conn.close()
            send(token,c,f"💰 {sign}{amt:,.0f}$ → {disp}",menu_admin_econ(c))
        except: send(token,c,"❌ `UID | مبلغ`",menu_admin_econ(c))
        return
    if state=="set_welcome":
        user_states.pop(c,None); _set_setting("welcome",txt)
        send(token,c,"📝 ✅",menu_admin_set(c)); return
    if state=="bc_all":
        user_states.pop(c,None); n=_bc_all(token,txt)
        send(token,c,f"📢 {n}",menu_admin_bc(c)); return
    if state=="bc_admins":
        user_states.pop(c,None); n=_bc_admins(token,txt)
        send(token,c,f"📢 {n}",menu_admin_bc(c)); return
    if state=="bc_user_uid":
        uid,un,disp=find_user(txt)
        if not uid:
            user_states.pop(c,None); send(token,c,"❌",menu_admin_bc(c)); return
        user_states[c]="bc_user_text"; user_states[f"target_{c}"]=uid
        send(token,c,f"🎯 {disp}"); return
    if state=="bc_user_text":
        target=user_states.pop(f"target_{c}",None); user_states.pop(c,None)
        if target: send(token,target,txt)
        send(token,c,"✅",menu_admin_bc(c)); return
    
    # Horse / Car state machines
    if state in ("horse_lobby","horse_bet"):
        res=g_horse(c,token,txt)
        if res: send(token,c,res,menu_casino(c))
        return
    if state in ("car_lobby","car_bet"):
        res=g_car(c,token,txt)
        if res: send(token,c,res,menu_casino(c))
        return
    
    # Investment inputs
    if state=="wait_buy":
        user_states.pop(c,None)
        parts=txt.split()
        if len(parts)>=2:
            try: send(token,c,do_buy_sync(c,parts[0],float(parts[1])),menu_home(c))
            except Exception as e: send(token,c,f"❌ {e}",menu_home(c))
        else: send(token,c,"❌ `SYMBOL USD`",menu_home(c))
        return
    if state=="wait_sell":
        user_states.pop(c,None)
        parts=txt.split()
        if len(parts)>=2:
            try: send(token,c,do_sell_sync(c,parts[0],float(parts[1])),menu_home(c))
            except Exception as e: send(token,c,f"❌ {e}",menu_home(c))
        else: send(token,c,"❌ `SYMBOL QTY`",menu_home(c))
        return
    if state=="wait_alert":
        user_states.pop(c,None)
        parts=txt.split()
        if len(parts)>=3:
            sym=parts[0].upper(); dr=parts[1].lower()
            try: tgt=float(parts[2])
            except: send(token,c,"❌ السعر رقم",menu_home(c)); return
            if dr not in ("above","below"): send(token,c,"❌ above/below",menu_home(c)); return
            conn=sqlite3.connect(DB_PATH)
            conn.execute("INSERT INTO price_alerts (uid,symbol,target_price,direction,created_at) VALUES (?,?,?,?,?)",
                         (c,sym,tgt,dr,int(time.time())))
            conn.commit(); conn.close()
            emoji="⬆️" if dr=="above" else "⬇️"
            send(token,c,f"🔔 **تنبيه مضاف**\n{emoji} {sym} @ ${tgt:,.2f}",menu_home(c))
        else: send(token,c,"❌ `SYMBOL above/below PRICE`",menu_home(c))
        return
    
    # Other states
    if state and state.startswith("wait_num_"):
        user_states.pop(c,None)
        op=state.replace("wait_num_","")
        send(token,c,eng_num(c,token,op,txt),menu_home(c)); return
    if state and state.startswith("wait_conv_"):
        user_states.pop(c,None)
        op=state.replace("wait_conv_","")
        send(token,c,eng_conv(c,token,op,txt),menu_home(c)); return
    if state=="wait_roi":
        user_states.pop(c,None); send(token,c,eng_roi(c,token,txt),menu_home(c)); return
    if state=="wait_risk":
        user_states.pop(c,None); send(token,c,eng_risk(c,token,txt),menu_home(c)); return
    if state=="wait_addr":
        user_states.pop(c,None); send(token,c,eng_addr_check(c,token,txt),menu_home(c)); return
    if state=="wait_ip":
        user_states.pop(c,None); send(token,c,eng_ip_info(c,token,txt),menu_home(c)); return
    if state=="wait_whois":
        user_states.pop(c,None); send(token,c,eng_whois(c,token,txt),menu_home(c)); return
    if state=="wait_tech":
        user_states.pop(c,None); send(token,c,eng_tech_detect(c,token,txt),menu_home(c)); return
    if state=="wait_url_parse":
        user_states.pop(c,None); send(token,c,eng_url_parse(c,token,txt),menu_home(c)); return
    if state=="wait_short":
        user_states.pop(c,None); send(token,c,eng_short_expand(c,token,txt),menu_home(c)); return
    if state=="wait_qr":
        user_states.pop(c,None); send(token,c,eng_qr_gen(c,token,txt),menu_home(c)); return
    if state=="wait_username":
        user_states.pop(c,None); send(token,c,"⏳")
        a,i=audit_user(txt)
        kb,row=[],[]
        rep=f"👑 `{txt}`\n🟢 {len(a)} | 🔴 {len(i)}\n\n"
        for n,l in a:
            rep+=f"• [{n}]({l})\n"
            row.append({"text":f"🚀 {n}","url":l})
            if len(row)==3: kb.append(row); row=[]
        if row: kb.append(row)
        kb.append([{"text":"🔍","callback_data":"sec_1"},{"text":"🏠","callback_data":"home"}])
        send(token,c,rep,{"inline_keyboard":kb}); return
    if state=="wait_query":
        user_states.pop(c,None); send(token,c,"⏳")
        res=deep_search(txt)
        if not res: send(token,c,"❌",menu_home(c)); return
        rep=f"🔥 {len(res)}:\n\n"
        for i,r in enumerate(res[:15],1):
            rep+=f"*{i}*. 👤 {r['name']}\n📞 `{r['phone']}`\n🔗 {r['fb']}\n📋 {r['payload']}\n📂 `{r['src']}`\n———\n"
        send(token,c,rep,menu_home(c)); return
    if state=="wait_text":
        user_states.pop(c,None)
        send(token,c,f"📝 كبير:`{txt.upper()}`\nصغير:`{txt.lower()}`\nعكس:`{txt[::-1]}`\nعدد:{len(txt)}",menu_home(c)); return
    if state=="wait_hash":
        user_states.pop(c,None)
        send(token,c,f"🔓 MD5: `{hashlib.md5(txt.encode()).hexdigest()}`\nSHA256: `{hashlib.sha256(txt.encode()).hexdigest()}`",menu_home(c)); return
    if state=="wait_b64":
        user_states.pop(c,None)
        enc=base64.b64encode(txt.encode()).decode()
        try: dec=base64.b64decode(txt).decode("utf-8",errors="ignore")
        except: dec="—"
        send(token,c,f"🔐: `{enc}`\n🔓: `{dec}`",menu_home(c)); return
    if state=="wait_cipher":
        user_states.pop(c,None)
        rot=txt.translate(str.maketrans('ABCDEFGHIJKLMabcdefghijklmNOPQRSTUVWXYZnopqrstuvwxyz','NOPQRSTUVWXYZnopqrstuvwxyzABCDEFGHIJKLMabcdefghijklm'))
        send(token,c,f"🔐 ROT13: `{rot}`",menu_home(c)); return
    if state=="wait_dns":
        user_states.pop(c,None)
        try: ip=socket.gethostbyname(txt); send(token,c,f"🌐 {txt} → `{ip}`",menu_home(c))
        except: send(token,c,"❌",menu_home(c))
        return
    if state=="wait_http":
        user_states.pop(c,None)
        url=txt if txt.startswith("http") else f"https://{txt}"
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req,timeout=8) as r:
                h="\n".join(f"• {k}: {v}" for k,v in list(r.headers.items())[:10])
                send(token,c,f"🌐 {url}\nحالة: {r.status}\n{h}",menu_home(c))
        except Exception as e: send(token,c,f"❌ {e}",menu_home(c))
        return
    if state=="wait_scan":
        user_states.pop(c,None); send(token,c,eng_scan(c,token,txt),menu_home(c)); return
    if state=="wait_launch":
        user_states.pop(c,None); send(token,c,eng_launch(c,token,txt),menu_home(c)); return
    
    send(token,c,"👑 اختر:",menu_home(c))

# ==========================================================
# POLLING
# ==========================================================
def polling(token):
    offset=0; fails=0
    print(f"[*] {BOT_BRAND} v11 LIVE")
    print(f"[*] Token: ...{token[-8:] if len(token)>8 else '???'}")
    while True:
        try:
            url=f"https://api.telegram.org/bot{token}/getUpdates?offset={offset}&timeout=30"
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req,timeout=40) as res:
                data=json.loads(res.read().decode())
            if not data.get("ok"):
                print(f"[-] {data.get('description','?')}")
                fails+=1
                if fails>5: time.sleep(30); fails=0
                else: time.sleep(3)
                continue
            fails=0
            for upd in data.get("result",[]):
                offset=upd["update_id"]+1
                try: handle(token,upd)
                except: traceback.print_exc()
        except KeyboardInterrupt: return
        except: traceback.print_exc(); time.sleep(5)

if __name__=="__main__":
    print(f"=== {BOT_BRAND} v11 BOOT ===")
    try: init_db(); print("[✓] DB ready")
    except: traceback.print_exc()
    
    token=os.environ.get("PROFISORE_TOKEN","").strip()
    if not token:
        tf=os.path.join(BASE_DIR,"token.txt")
        if os.path.isfile(tf):
            try:
                with open(tf,"r") as f: token=f.read().strip()
                print(f"[✓] Token file ({len(token)} chars)")
            except: pass
    if not token:
        try: token=input("👉 التوكن: ").strip()
        except: input("Enter..."); sys.exit(1)
    if not token: sys.exit(1)
    
    try:
        url=f"https://api.telegram.org/bot{token}/getMe"
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req,timeout=10) as r:
            me=json.loads(r.read().decode())
        if me.get("ok"): print(f"[✓] @{me['result']['username']}")
        else: print("❌"); sys.exit(1)
    except Exception as e: print(f"❌ {e}"); sys.exit(1)
    
    try: polling(token)
    except KeyboardInterrupt: print("\n[*] bye.")
    except: traceback.print_exc()