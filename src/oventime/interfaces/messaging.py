import requests

from oventime.utils import time_interpreter, to_utc_timestamp, to_epoch
from oventime.config import TIMEZONE


API_BASE_URL = "http://127.0.0.1:8000"


def get_fulldiag(at_time = None):
    if at_time is None:
        r = requests.get(f"{API_BASE_URL}/diagnostic/now")
    else:
        at_time = to_epoch(at_time)
        r = requests.get(f"{API_BASE_URL}/diagnostic/at",
            params={"time": at_time},
            timeout=2,
        )
    r.raise_for_status()
    return r.json()

def concl_from_score(score: float) -> str:
    if score > 100:
        return "🍃🍃🍃 A FOND! Y a de l'électricité à ne savoir qu'en faire."
    if score > 85:
        return "🟢 VAS-Y : On est large."
    if score > 70:
        return "🟢 CA VA, On tire pas trop sur le gaz."
    if score > 30:
        return "🟠 UN PEU TENDU : C'est pas le pire, mais on tire un peu sur le gaz quand même."
    if score > 0:
        return "🔴 PAS MAINTENANT, Le système est tendu et les centrales gaz tournent à fond."
    return "🔥🔥🔥 PIRE MOMENT! Le système est si tendu qu'on a démarré les centrales les plus polluantes."

def msg_diagnostic(
        at_time: str = None,
        tz_output: str = TIMEZONE
        ):
    
    target_time = time_interpreter(at_time)
    diag = get_fulldiag(target_time)
    diag['time'] = to_utc_timestamp(diag['time']).tz_convert(tz_output)
    
    # ------------------------------------------------------------
    # Qualitative interpretation for real-time feedback
    # ------------------------------------------------------------
    ccl = concl_from_score(diag["score"])
    stock_ou_destock = "on déstocke"
    if diag['details']["storage_use_rate"]<0: stock_ou_destock = "on stocke"
    text = (
        f"📊 *Etat du système* à {diag['time'].strftime('%H:%M')} ({diag['time'].strftime('%d/%m')})\n\n"
        f"🔥 Gaz mobilisé à {diag['details']['gasCCG_use_rate']*100:.0f}%\n"
        f"💧 Hydro/Stockage à {diag['details']['storage_use_rate']*100:.0f}% (**"+stock_ou_destock+"**)\n"
        f"⚛️ Nucléaire à {diag['details']['nuclear_use_rate']*100:.1f}% de sa dispo\n"
        f"🔎 *Score: {diag['score']:.0f}*\n\n"
        f"👉 {ccl}"
    )

    return(text)

def msg_price_window(
    duration: str = None,
    method: str = "otsu",
    severity: float = 1.0,
    tz_output: str = TIMEZONE
) -> str:
    """
    Renvoie un message texte décrivant la prochaine bonne fenêtre de prix bas.
    """
    if duration is None:
        start_utc, end_utc, eff_window = diagnostic.price_window(method=method,severity=severity)

        start_local = start_utc.tz_convert(tz_output)
        end_local = end_utc.tz_convert(tz_output)

        start_str = start_local.strftime("%H:%M")
        end_str = end_local.strftime("%H:%M")

        text = (
            f"⚡🌱 Bonne fenêtre dans les {eff_window}h à venir : "
            f"🕒 *{start_str}* à *{end_str}* 🕒\n"
            f"👉 Bon moment pour lancer les gros consommateurs d'électricité"
        )
    else:
        start_utc, end_utc, eff_window = oventime.core.diagnostic.price_window(duration=duration,severity=severity)

    return text

if __name__ == "__main__":
    print(msg_diagnostic())
    #print(msg_price_window(severity=2))

