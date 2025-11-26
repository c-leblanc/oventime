from oven_time import processing



def call_tec(tec):
    data = processing.init_data()
    call_idx = {}
    for t in tec:
        call_idx[t] = (data[t].iloc[-1]-data[t].min())/(data[t].max()-data[t].min())

    return(call_idx)