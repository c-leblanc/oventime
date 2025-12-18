from oven_time import decision
from oven_time.config import TIMEZONE

import dateparser
from pandas import Timestamp

def time_interpreter(time_str, tz=TIMEZONE, freq="15min"):
    """
    Parse une chaîne en pd.Timestamp UTC, arrondie à `freq`.
    - accepte str | pd.Timestamp | datetime | None (retourne None)
    - localise en 'tz' si naive, convertit en UTC
    """
    if time_str is None:
        return None

    try:
        # If already a Timestamp / datetime, normalize directly
        if isinstance(time_str, Timestamp):
            ts = time_str
        else:
            # allow datetime too
            from datetime import datetime
            if isinstance(time_str, datetime):
                ts = Timestamp(time_str)
            else:
                dt = dateparser.parse(
                    time_str,
                    settings={
                        "TIMEZONE": tz,
                        "RETURN_AS_TIMEZONE_AWARE": True,
                        "DATE_ORDER": "DMY",
                        "PREFER_DATES_FROM": "past",
                    },
                )
                if dt is None:
                    raise ValueError()
                ts = Timestamp(dt)

        # Ensure timezone-aware and convert to UTC
        if ts.tzinfo is None:
            ts = ts.tz_localize(tz)
        else:
            ts = ts.tz_convert(tz)

        ts_utc = ts.tz_convert("UTC").floor(freq)
        return ts_utc

    except Exception:
        raise ValueError(
            f"Format d'heure invalide : {time_str}\nExemples valides : 9, 9am, 21:30, hier 9am, 25/12 14h, ..."
        )



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




def get_diagnostic(
        at_time: str = None,
        tz_output: str = TIMEZONE
        ):
    
    target_time = time_interpreter(at_time)
    diag = decision.diagnostic(target_time=target_time)
    
    # ------------------------------------------------------------
    # Qualitative interpretation for real-time feedback
    # ------------------------------------------------------------
    ccl = concl_from_score(diag["score"])
    text = (
        f"📊 *Etat du système* à {diag['time'].tz_convert(tz_output).strftime('%H:%M')} ({diag['time'].tz_convert(tz_output).strftime('%d/%m')})\n\n"
        f"🔥 Gaz mobilisé à {diag['gasCCG_use_rate']*100:.0f}%\n"
        f"💧 Hydro/Stockage mobilisé à {diag['storage_use_rate']*100:.0f}%\n"
        f"⚛️ Nucléaire à {diag['nuclear_use_rate']*100:.1f}% de sa dispo\n"
        f"🔎 *Score: {diag['score']:.0f}*\n\n"
        f"👉 {ccl}"
    )

    return(text)


def get_price_window(
    duration: str = None,
    method: str = "otsu",
    severity: float = 1.0,
    tz_output: str = TIMEZONE
) -> str:
    """
    Renvoie un message texte décrivant la prochaine bonne fenêtre de prix bas.
    """
    if duration is None:
        start_utc, end_utc, eff_window = decision.price_window(method=method,severity=severity)

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
        start_utc, end_utc, eff_window = decision.price_window(duration=duration,severity=severity)

    return text

if __name__ == "__main__":
    print(get_diagnostic("13/12 18:15"))
    #print(get_price_window(severity=2))

