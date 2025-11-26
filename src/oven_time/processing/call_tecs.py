import oven_time.processing.format_table as fmt



def call_tec(tec):
    data = fmt.init_data()
    call_idx = {}
    for t in tec:
        call_idx[t] = (data[t].iloc[-1]-data[t].min())/(data[t].max()-data[t].min())

    return(call_idx)