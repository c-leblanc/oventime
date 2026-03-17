import httpx
import pandas as pd

from oventime.utils import time_interpreter, to_utc_timestamp
from oventime.config import (
    TIMEZONE, API_BASE_URL,
    LEAF_THRESHOLD, GREEN_ORANGE_THRESHOLD, ORANGE_RED_THRESHOLD, FIRE_THRESHOLD
)


def concl_from_score(score: float) -> str:
    if score > LEAF_THRESHOLD:
        return "🍃🍃🍃 A FOND!\nY a de l'électricité à ne savoir qu'en faire."
    if score > GREEN_ORANGE_THRESHOLD:
        return "🟢 CA VA\nOn tire un peu sur le gaz, mais modérément."
    if score > ORANGE_RED_THRESHOLD:
        return "🟠 UN PEU TENDU\nC'est pas le pire, mais on tire un peu sur le gaz quand même."
    if score > FIRE_THRESHOLD:
        return "🔴 PAS MAINTENANT\nLe système est tendu et les centrales gaz tournent à fond."
    return "🔥🔥🔥 PIRE MOMENT!\nLe système est très tendu, on a démarré les centrales les plus polluantes."

def msg_diagnostic(
        at_time: str = None,
        tz_output: str = TIMEZONE
        ):
    
    target_time = time_interpreter(at_time)
    r = httpx.get(
        f"{API_BASE_URL}/diagnostic",
        params={"time": target_time},
        timeout=2
        )
    r.raise_for_status()
    
    diag = r.json()
    
    diag['ts'] = to_utc_timestamp(diag['ts']).tz_convert(tz_output)

    # ------------------------------------------------------------
    # Qualitative interpretation for real-time feedback
    # ------------------------------------------------------------
    ccl = concl_from_score(diag["score"])
    stock_ou_destock = "on déstocke"
    if diag['details']["storage_use_rate"]<0: stock_ou_destock = "on stocke"
    text = (
        f"{ccl}\n\n"
        f"⬇️\n\n"
        f"📊 *Etat du système* à {diag['ts'].strftime('%H:%M')} ({diag['ts'].strftime('%d/%m')})\n"
        f"🔥 Gaz mobilisé à {diag['details']['gasCCG_use_rate']*100:.0f}%\n"
        f"💧 Hydro/Stockage à {diag['details']['storage_use_rate']*100:.0f}% (**"+stock_ou_destock+"**)\n"
        f"⚛️ Nucléaire à {diag['details']['nuclear_use_rate']*100:.1f}% de sa dispo\n"
        f"👉🔎 *Score: {diag['score']:.0f}*\n\n"
    )

    return(text)

def msg_price_window(
        tz_output: str = TIMEZONE
        ) -> str:
    """
    Renvoie un message texte décrivant la prochaine bonne fenêtre de prix bas.
    """
    r = httpx.get(
        f"{API_BASE_URL}/next/window",
        timeout=2
        )
    r.raise_for_status()
    
    pwind = r.json()

    start = to_utc_timestamp(pwind['nextwind_start']).tz_convert(tz_output)
    end = to_utc_timestamp(pwind['nextwind_end']).tz_convert(tz_output)

    start_str = start.strftime("%H:%M")
    end_str = end.strftime("%H:%M")

    now = pd.Timestamp.now(tz_output).normalize()
    start_day = start.normalize()

    if start_day == now and start.hour <= 22:
        when = "aujourd’hui"
    elif start_day == now + pd.Timedelta(days=1) and start.hour > 6:
        when = "demain"
    elif start_day <= now + pd.Timedelta(days=1) and (start.hour >= 22 or start.hour < 6):
        when = "cette nuit"
    else:
        # fallback explicite
        when = start.strftime("le %d/%m")

    text = (
        f"⚡🌱 Bonne fenêtre {when}: "
        f"🕒 *{start_str}* à *{end_str}* 🕒 \n"
        f"👉 Bon moment pour lancer les gros consommateurs d'électricité"
    )

    return text

