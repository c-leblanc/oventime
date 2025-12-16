from oven_time import api_eco2mix, decision
from oven_time.config import WINDOW_RANGE

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
        tz_output: str = "Europe/Paris",
        update: bool = False
        ):
    
    if update: api_eco2mix.update_eco2mix_data(verbose=False)
    
    diag = decision.diagnostic(at_time=at_time)
    
    # ------------------------------------------------------------
    # Qualitative interpretation for real-time feedback
    # ------------------------------------------------------------
    ccl = concl_from_score(diag["score"])
    text = (
        f"📊 *Etat du système* à {diag['time'].tz_convert(tz_output).strftime('%H:%M')} ({diag['time'].tz_convert(tz_output).strftime('%d/%m')})\n\n"
        f"🔥 Gaz mobilisé à {diag['gasCCG_use_rate']*100:.0f}%\n"
        f"💧 Hydro/Stockage mobilisé à {diag['storage_phase']*100:.0f}%\n"
        f"⚛️ Nucléaire à {diag['nuclear_use_rate']*100:.1f}% de sa dispo\n"
        f"🔎 *Score: {diag['score']:.0f}*\n\n"
        f"👉 {ccl}"
    )
    #print(text)

    return(text)


def get_price_window(
    method: str = "otsu",
    severity: float = 1.0,
    tz_output: str = "Europe/Paris"
) -> str:
    """
    Renvoie un message texte décrivant la prochaine bonne fenêtre de prix bas.
    """
    start_utc, end_utc, eff_window = decision.price_window(method=method,severity=severity)

    start_local = start_utc.tz_convert(tz_output)
    end_local = end_utc.tz_convert(tz_output)

    start_str = start_local.strftime("%H:%M")
    end_str = end_local.strftime("%H:%M")
    #date_str = start_local.strftime("%d/%m")

    text = (
        f"⚡🌱 Meilleure fenêtre dans les {eff_window}h à venir : "
        f"🕒 *{start_str}* à *{end_str}* 🕒\n"
        f"👉 Créneau idéal pour lancer les gros consommateurs d'électricité"
    )

    return text

if __name__ == "__main__":
    print(get_price_window(severity=2))

