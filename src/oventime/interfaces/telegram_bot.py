import logging
from telegram.ext import ContextTypes
import asyncio

from oventime.input.data_download import should_update_eco2mix, update_eco2mix_data, should_update_prices, update_price_data
from oventime.interfaces.messaging import get_diagnostic, get_price_window
from oventime.core.decision import diagnostic
from config import HIGH_SCORE_THRESHOLD, LOW_SCORE_THRESHOLD, WINDOW_METHOD, OTSU_SEVERITY

logging.basicConfig(level=logging.INFO)


async def now(update, context):
    """Répond avec le diagnostic actuel."""
    msg = get_diagnostic()
    await update.message.reply_text(msg, parse_mode="Markdown")

async def at(update, context):
    """Répond avec le diagnostic à l'heure demandée en supposant Europe/Paris puis converti en UTC."""
    if not context.args:
        await update.message.reply_text(
            "Veuillez préciser une heure après /a (ex: /a 15:30, /a 9am, /a hier 9am)", 
            parse_mode="Markdown"
        )
        return

    time_str = " ".join(context.args)

    try:
        msg = get_diagnostic(at_time=time_str)
    except ValueError as e:
        await update.message.reply_text(str(e), parse_mode="Markdown")
        return
    except Exception as e:
        await update.message.reply_text(f"Erreur lors du calcul du diagnostic", parse_mode="Markdown")
        return
    await update.message.reply_text(msg, parse_mode="Markdown")

async def window(update, context):
    """Répond avec la meilleure fenêtre à venir."""
    msg = get_price_window(method=WINDOW_METHOD,severity=OTSU_SEVERITY)
    await update.message.reply_text(msg, parse_mode="Markdown")


#############################################
## AUTOMATIC ALERT MESSAGES

SUBSCRIBERS_KEY = "subscribers"

async def start_auto(update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribers = context.application.bot_data.setdefault(SUBSCRIBERS_KEY, set())
    subscribers.add(chat_id)
    print(f"Subscriber to automatic messages added: {chat_id}. (Total={len(subscribers)} active subscribers)")
    await update.message.reply_text("✅ ACTIF: Alerte automatique en cas d'électricité verte abondante 🍃⚡ ou de forte tension sur le réseau 🔥🏭")

async def stop_auto(update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribers = context.application.bot_data.setdefault(SUBSCRIBERS_KEY, set())
    subscribers.discard(chat_id)
    print("Subscriber to automatic messages removed: {chat_id}. (Total={len(subscribers)} active subscribers)")
    await update.message.reply_text("❌ INACTIF: Alerte automatique en cas d'électricité verte abondante 🍃⚡ ou de forte tension sur le réseau 🔥🏭")



async def check_score_job(application):
    state_high = application.bot_data.setdefault("last_alert_high", False)
    print(f"Last alert high ? {state_high}")
    state_low = application.bot_data.setdefault("last_alert_low", False)
    print(f"Last alert low ? {state_low}")

    diag = diagnostic()
    score = diag["score"]
    subscribers = application.bot_data.get(SUBSCRIBERS_KEY, set())

    text=None
    if score <= HIGH_SCORE_THRESHOLD and state_high:
        text = "❌ Fin de la période d'abondance ⚡🍃"
        application.bot_data["last_alert_high"] = False
    if score >= LOW_SCORE_THRESHOLD and state_low:
        text = "✅ Fin de la période de forte tension 🔥🏭"
        application.bot_data["last_alert_low"] = False
    if score > HIGH_SCORE_THRESHOLD and not state_high:
        text = f"🍃⚡ ABONDANCE ⚡🍃\nIl y a un surplus d'électricité décarbonée sur le réseau !\n(Score : {score:.0f}, /m for more info)"
        application.bot_data["last_alert_high"] = True
    if score < LOW_SCORE_THRESHOLD and not state_low:
        text = f"🔥🏭 FORTE TENSION 🔥🏭\nL'électricité se fait rare et on a démarré les centrales les plus polluantes !\n(Score : {score:.0f}, /m for more info)"
        application.bot_data["last_alert_low"] = True


    if text is not None:
        for chat_id in subscribers:
            await application.bot.send_message(chat_id=chat_id, text=text)


async def background_job(application, freq=5):
    """
    Coroutine qui tourne en boucle infinie pour :
    1. mettre à jour eco2mix
    2. mettre à jour les prix day-ahead si on est après midi et qu'ils manquent
    3. lancer check_score_job après chaque update
    """
    last_timestamp_eco2mix = None
    last_timestamp_prices = None
    while True:
        if should_update_eco2mix(last_timestamp_eco2mix):
            try:
                # --- 1. Update eco2mix ---
                last_timestamp_eco2mix = update_eco2mix_data(verbose=True)

                # --- 2. Recompute score and triggers alerts ---
                await check_score_job(application)

            except Exception as e:
                print(f"[background_job] Erreur dans la MaJ des données de production : {e!r}")

        # --- 3. Update prices if needed ---
        if should_update_prices(last_timestamp_prices):
            try:
                update_price_data(verbose=True)
            except Exception as e:
                print(f"[background_job] Erreur dans la MaJ des données de prix: {e!r}")

        await asyncio.sleep(freq * 60)


        


