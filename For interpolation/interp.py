import numpy
def interp(s_arr, e_arr, time:tuple)-> numpy.array:
    start_time = time[0] if time[0]<time[1] else time[1]
    end_time = time[1] if time[1]>time[0] else time[0]
    recon_time = time[2]
    out_arr=numpy.empty(s_arr.shape)
    for i in range(len(s_arr)):
        out_arr[i]=numpy.interp(recon_time, [start_time, end_time], [s_arr[i], e_arr[i]])

    return out_arr




