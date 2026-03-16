import logging
import json
import httpx
from pywebpush import webpush, WebPushException
from py_vapid import Vapid
from urllib.parse import urlparse

from oventime.cache.cache import get_fulldiag, get_tsubs, get_wsubs, remove_wsubs
from oventime.config import LEAF_THRESHOLD, FIRE_THRESHOLD, EMAIL, TELEGRAM_TOKEN, VAPID_PRIVATE_KEY, VAPID_PUBLIC_KEY

logger = logging.getLogger(__name__)

VAPID_CLAIMS       = {"sub": f"mailto:{EMAIL}"}

# ── État interne (remplace application.bot_data) ─────────────────────────────
_last_seen_ts:   str | None = None
_last_alert_high: bool = False
_last_alert_low:  bool = False


async def check_and_notify():
    """
    À appeler depuis orchestrator_loop() après chaque mise à jour du cache.
    Vérifie si le score a franchi un seuil et envoie les alertes si besoin.
    """
    global _last_seen_ts, _last_alert_high, _last_alert_low

    diag = get_fulldiag()
    if diag is None:
        return

    ts    = diag["ts"]
    score = diag["score"]

    # Rien de nouveau
    if ts == _last_seen_ts:
        return
    _last_seen_ts = ts

    text = None

    if score <= LEAF_THRESHOLD and _last_alert_high:
        text = "❌ Fin de la période d'abondance ⚡🍃"
        _last_alert_high = False

    elif score >= FIRE_THRESHOLD and _last_alert_low:
        text = "✅ Fin de la période de forte tension 🔥🏭"
        _last_alert_low = False

    elif score > LEAF_THRESHOLD and not _last_alert_high:
        text = (
            "🍃⚡ ABONDANCE ⚡🍃\n"
            "Il y a un surplus d'électricité décarbonée sur le réseau !\n"
            f"(Score : {score:.0f}, /m pour plus d'infos)"
        )
        _last_alert_high = True

    elif score < FIRE_THRESHOLD and not _last_alert_low:
        text = (
            "🔥🏭 FORTE TENSION 🔥🏭\n"
            "L'électricité se fait rare et on a démarré les centrales les plus polluantes !\n"
            f"(Score : {score:.0f}, /m pour plus d'infos)"
        )
        _last_alert_low = True

    if text is None:
        return

    logger.info(f"Alerte déclenchée : {text[:50]}…")
    await _notify_telegram(text)
    await _notify_web(body=text)


# ── Envoi Telegram ────────────────────────────────────────────────────────────

async def _notify_telegram(text: str):
    chat_ids = get_tsubs()
    if not chat_ids: return
    if not TELEGRAM_TOKEN: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=5) as client:
        for chat_id in chat_ids:
            try:
                r = await client.post(url, json={"chat_id": chat_id, "text": text})
                if r.status_code == 401:
                    logger.error("Telegram token invalide, envoi des alertes abandonné.")
                    return
                r.raise_for_status()
            except httpx.HTTPStatusError:
                pass  # déjà géré au dessus
            except Exception as e:
                logger.error(f"Erreur envoi Telegram chat_id={chat_id}: {e!r}")

# ── Envoi Web Push ────────────────────────────────────────────────────────────

async def _notify_web(title: str = None, body: str = None, subs_override: dict = None):
    subs = subs_override if subs_override is not None else get_wsubs()
    if not subs:
        logger.info("Aucun abonné web push.")
        return
    if not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
        logger.error("Clés VAPID non configurées, web push ignoré.")
        return
    payload = json.dumps({"title": title, "body": body, "tag": "oventime-alert"})
    to_remove = []
    for endpoint, sub in subs.items():
        vapid = Vapid.from_string(VAPID_PRIVATE_KEY)
        parsed = urlparse(endpoint)
        claims = {"sub": f"mailto:{EMAIL}", "aud": f"{parsed.scheme}://{parsed.netloc}"}
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=vapid,
                vapid_claims=claims,
                content_encoding="aes128gcm",
            )
            logger.info(f"Web push envoyé : {endpoint[:60]}…")
        except WebPushException as e:
            status = e.response.status_code if e.response else None
            if status in (403, 404, 410):
                to_remove.append(endpoint)
                logger.info(f"Web push subscription expirée ({status}): {endpoint[:60]}…")
            else:
                logger.error(f"Erreur web push {status}: {e!r}")
        except Exception as e:
            logger.error(f"Erreur inattendue web push: {e!r}")
    for ep in to_remove:
        remove_wsubs(ep)