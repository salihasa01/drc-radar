#!/usr/bin/env python3
"""Haber Radarı: RSS kaynaklarını çeker, config.yaml'daki kurallara göre süzer,
docs/news.json dosyasını günceller ve isteğe bağlı olarak Telegram'a bildirim gönderir."""

import hashlib
import html
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config.yaml"
OUT = ROOT / "docs" / "news.json"
UA = "Mozilla/5.0 (HaberRadari; +https://github.com)"


def norm(text: str) -> str:
    """Küçük harf + aksanları kaldır (tués -> tues, sécurité -> securite)."""
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def compile_terms(terms):
    """Kelime sınırlarına dikkat eden tek bir regex (\"beni\" -> \"benin\" ile eşleşmez)."""
    parts = []
    for t in terms or []:
        t = norm(str(t)).strip()
        if not t:
            continue
        # Sonu * ile biten terim kök olarak eşleşir: "evacuat*" -> evacuate, evacuation...
        prefix = t.endswith("*")
        t = t.rstrip("*")
        esc = re.escape(t)
        right = "" if prefix else r"(?![a-z0-9])"
        parts.append(rf"(?<![a-z0-9]){esc}{right}")
    return re.compile("|".join(parts)) if parts else None


def found(rx, text):
    return sorted({m.group(0).strip() for m in rx.finditer(text)}) if rx else []


def clean_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def entry_time(e):
    for key in ("published_parsed", "updated_parsed"):
        t = e.get(key)
        if t:
            return datetime.fromtimestamp(time.mktime(t), tz=timezone.utc)
    return datetime.now(timezone.utc)


def classify(title, summary, rules):
    text = norm(f"{title} {summary}")
    if found(rules["exclude"], text):
        return None
    country = found(rules["country"], text)
    strong = found(rules["strong"], text)
    security = found(rules["security"], text)

    if not strong and not (country and security):
        return None

    # Sadece Brazzaville/Kongo Cumhuriyeti'ne işaret ediyorsa ele
    if found(rules["exclude_only"], text):
        drc_specific = [c for c in country if c not in ("congo", "congolese", "congolais", "congolaise")]
        if not strong and not drc_specific and "democratic" not in text and "democratique" not in text:
            return None

    high = found(rules["high"], text)
    return {
        "priority": "high" if high else "normal",
        "tags": sorted(set(strong + security[:4]))[:6],
    }


def load_existing():
    if OUT.exists():
        try:
            return json.loads(OUT.read_text(encoding="utf-8")).get("items", [])
        except Exception:
            pass
    return []


def send_telegram(items):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat or not items:
        return
    for it in items[:15]:  # bir seferde en fazla 15 bildirim
        flag = "🔴" if it["priority"] == "high" else "🔵"
        title = it.get("title_tr") or it["title"]
        msg = f"{flag} <b>{html.escape(title)}</b>\n{html.escape(it['source'])}\n{it['link']}"
        data = urllib.parse.urlencode(
            {"chat_id": chat, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": "true"}
        ).encode()
        try:
            urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data, timeout=15)
        except Exception as ex:
            print(f"  ! Telegram hatası: {ex}", file=sys.stderr)


def _gtx(text):
    """Google Çeviri'nin herkese açık JSON adresi (anahtar gerektirmez)."""
    q = urllib.parse.urlencode({"client": "gtx", "sl": "auto", "tl": "tr", "dt": "t", "q": text})
    req = urllib.request.Request(f"https://translate.googleapis.com/translate_a/single?{q}",
                                 headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode("utf-8"))
    return "".join(seg[0] for seg in data[0] if seg and seg[0]).strip()


def _deep(text):
    """Yedek yöntem: deep-translator kütüphanesi."""
    from deep_translator import GoogleTranslator
    return (GoogleTranslator(source="auto", target="tr").translate(text) or "").strip()


def translate(text):
    errors = []
    for fn in (_gtx, _deep):
        try:
            out = fn(text)
            if out:
                return out
            errors.append(f"{fn.__name__}: boş sonuç")
        except Exception as ex:
            errors.append(f"{fn.__name__}: {type(ex).__name__}: {ex}")
    raise RuntimeError(" | ".join(errors))


def translate_items(items, limit):
    """Türkçe karşılığı olmayan haberleri ücretsiz Google Çeviri ile çevirir.
    Çeviri başarısız olursa haber orijinal diliyle kalır, bir sonraki taramada yeniden denenir."""
    done = fails = 0
    for it in items:
        if done >= limit or fails >= 3:
            break
        if it.get("title_tr"):
            continue
        try:
            it["title_tr"] = translate(it["title"])
            if it.get("summary"):
                it["summary_tr"] = translate(it["summary"])
            done += 1
            time.sleep(0.3)
        except Exception as ex:
            fails += 1
            print(f"  ! Çeviri hatası: {ex}")
    print(f"Çevrilen: {done} | Hata: {fails}")


def main():
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    rules = {
        "country": compile_terms(cfg.get("country_terms")),
        "strong": compile_terms(cfg.get("strong_terms")),
        "security": compile_terms(cfg.get("security_terms")),
        "high": compile_terms(cfg.get("high_priority_terms")),
        "exclude_only": compile_terms(cfg.get("exclude_if_only")),
        "exclude": compile_terms(cfg.get("exclude_terms")),
    }

    existing = load_existing()
    known_ids = {it["id"] for it in existing}
    known_titles = {norm(it["title"])[:70] for it in existing}
    new_items, status = [], []

    for src in cfg.get("sources", []):
        name, url = src["name"], src["url"]
        try:
            feed = feedparser.parse(url, agent=UA)
            entries = feed.entries
            status.append({"source": name, "ok": bool(entries), "count": len(entries)})
            print(f"{name}: {len(entries)} haber okundu")
        except Exception as ex:
            status.append({"source": name, "ok": False, "count": 0})
            print(f"  ! {name}: {ex}", file=sys.stderr)
            continue

        is_gnews = "news.google.com" in url
        for e in entries:
            title = clean_html(e.get("title", ""))
            if is_gnews:  # "Başlık - Reuters" son ekini kaldır
                title = re.sub(r"\s+-\s+[^-]+$", "", title)
            summary = clean_html(e.get("summary", ""))
            if is_gnews:
                summary = ""  # Google News özeti sadece başlığı tekrarlar
            link = e.get("link", "")
            if not title or not link:
                continue

            res = classify(title, summary, rules)
            if not res:
                continue

            uid = hashlib.sha1(link.encode()).hexdigest()[:16]
            tkey = norm(title)[:70]
            if uid in known_ids or tkey in known_titles:
                continue
            known_ids.add(uid)
            known_titles.add(tkey)

            new_items.append({
                "id": uid,
                "title": title,
                "summary": summary[:400],
                "link": link,
                "source": name,
                "published": entry_time(e).isoformat(),
                "found": datetime.now(timezone.utc).isoformat(),
                **res,
            })

    cutoff = datetime.now(timezone.utc) - timedelta(days=cfg.get("keep_days", 14))
    items = [it for it in new_items + existing
             if datetime.fromisoformat(it["published"]) >= cutoff]
    items.sort(key=lambda it: it["published"], reverse=True)
    items = items[: cfg.get("max_items", 400)]

    if cfg.get("translate", True):
        translate_items(items, cfg.get("translate_limit", 80))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "title": cfg.get("title", "Haber Radarı"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": status,
        "items": items,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Yeni: {len(new_items)} | Toplam: {len(items)}")

    mode = cfg.get("notify", "high")
    # İlk çalıştırmada (boş arşiv) yüzlerce bildirim gitmesin
    if mode != "off" and existing:
        to_send = new_items if mode == "all" else [i for i in new_items if i["priority"] == "high"]
        send_telegram(to_send)


if __name__ == "__main__":
    main()
