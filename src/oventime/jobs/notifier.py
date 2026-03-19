import logging
import json
from pywebpush import webpush, WebPushException
from py_vapid import Vapid
from urllib.parse import urlparse

from oventime.cache.cache import get_fulldiag, get_wsubs, remove_wsubs
from oventime.config import LEAF_THRESHOLD, FIRE_THRESHOLD, ALERT_HYSTERESIS, EMAIL, VAPID_PRIVATE_KEY, VAPID_PUBLIC_KEY
from oventime.utils import to_utc_timestamp

logger = logging.getLogger(__name__)

VAPID_CLAIMS       = {"sub": f"mailto:{EMAIL}"}

class Notifier:
    def __init__(self):
        self.last_seen_ts:   str | None = None
        self.last_alert_high: bool = False
        self.last_alert_low:  bool = False
        self._restore_state()

    def _restore_state(self):
        """Restaure les flags depuis le cache pour éviter de renvoyer
        des notifications après un redémarrage de l'application."""
        try:
            diag = get_fulldiag()
            if diag is None:
                return
            score = diag["score"]
            self.last_seen_ts    = diag["ts"]
            self.last_alert_high = score > LEAF_THRESHOLD
            self.last_alert_low  = score < FIRE_THRESHOLD
        except Exception:
            pass

    async def check_and_notify(self):
        """
        À appeler depuis orchestrator_loop() après chaque mise à jour du cache.
        Vérifie si le score a franchi un seuil et envoie les alertes si besoin.
        """

        diag = get_fulldiag()
        if diag is None:
            return

        ts    = diag["ts"]
        score = diag["score"]

        # Rien de nouveau
        if ts == self.last_seen_ts:
            return
        self.last_seen_ts = ts

        from zoneinfo import ZoneInfo
        from oventime.config import TIMEZONE
        time = to_utc_timestamp(ts).astimezone(ZoneInfo(TIMEZONE)).strftime("%H:%M")

        title = None
        text = None

        if score <= LEAF_THRESHOLD - ALERT_HYSTERESIS and self.last_alert_high:
            title = "❌ Retour à la normale"
            text = "Fin de la période d'abondance ⚡🍃"
            self.last_alert_high = False

        elif score >= FIRE_THRESHOLD + ALERT_HYSTERESIS and self.last_alert_low:
            title = "✅ Retour à la normale"
            text = "Fin de la période de forte tension 🔥🏭"
            self.last_alert_low = False

        elif score > LEAF_THRESHOLD and not self.last_alert_high:
            title = "🍃⚡ ABONDANCE"
            text = (
                "Il y a un surplus d'électricité décarbonée sur le réseau !\n"
                f"(Score à {time} = {score:.0f})"
            )
            self.last_alert_high = True

        elif score < FIRE_THRESHOLD and not self.last_alert_low:
            title = "🔥🏭 FORTE TENSION"
            text = (
                "L'électricité se fait rare et on a démarré les centrales les plus polluantes !\n"
                f"(Score à {time} = {score:.0f})"
            )
            self.last_alert_low = True

        if text is None:
            return

        logger.info(f"Alerte déclenchée : {text[:50]}…")
        await self._notify_web(title=title, body=text)

    # ── Envoi Web Push ────────────────────────────────────────────────────────────
    async def _notify_web(self, title: str = None, body: str = None, subs_override: dict = None):
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

notifier = Notifier()
