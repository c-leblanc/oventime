from oven_time import api, decision

def get_diagnostic(
        at_time: str = None,
        tz_output: str = "Europe/Paris",
        update: bool = True
        ):
    
    if update: api.update_raw_data(verbose=False)
    
    diag = decision.diagnostic(at_time=at_time)
    
    # ------------------------------------------------------------
    # Qualitative interpretation for real-time feedback
    # ------------------------------------------------------------
    ccl = ""
    if diag["gas_phase"] <= 0.1 and diag["nuclear_use_rate"] <= 0.995:
        ccl = "A FOND! Y a de l'électricité à ne savoir qu'en faire."
    elif diag["gas_phase"] <= 0.3:
            ccl = "CA VAAA! On tire pas trop sur le gaz."
    elif diag["gas_phase"] <= 0.6:
        ccl = "Hmmm… C'est pas le pire, mais on tire un peu sur le gaz quand même."
    else:
        ccl = "EVITE! Le système est tendu et les centrales gaz tournent à fond."

    text = (
        f"📊 Etat du système à {diag['time'].tz_convert(tz_output).strftime('%H:%M')} ({diag['time'].tz_convert(tz_output).strftime('%d/%m')})\n\n"
        f"🔥 Gaz mobilisé à {diag['gas_phase']*100:.0f}%\n"
        f"💧 Hydro/Stockage mobilisé à {diag['storage_use_rate']*100:.0f}%\n"
        f"⚛️ Nucléaire à {diag['nuclear_use_rate']*100:.1f}% de sa capacité\n"
        f"🔎 Score: {diag['score']:.0f}\n\n"
        f"👉 {ccl}"
    )
    print(text)

    return(text)
