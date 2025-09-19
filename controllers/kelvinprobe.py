import pyvisa
import time
from pyvisa.constants import  Parity
import numpy as np
import lmfit
#import matplotlib.pyplot as plt
#from tqdm.notebook import tqdm
import pandas as pd
dict_tc = {"20ms":"10","50ms":"11","100ms":"12","500ms":"13","1s":"14"}
dict_tc_to_sec = {"20ms":0.02,"50ms":.050,"100ms":.100,"500ms":.500,"1s":1}

dict_demodv = {"X":"X.","Y.":"Y","Phase":"PHA.","R":"MAG."}
dict_sens = {"1pA":"15","2pA":"16","5pA":"17","10pA":"18","20pA":"19","50pA":"20"}
rm = pyvisa.ResourceManager('C:/Windows/System32/visa32.dll') # 32 bit windows

# opens a connection to the lock-in via RS232 of sPort, sBaudRate (strings)
def Connection_Open_RS232(sPort, sBaudRate,rm,verbose = True):
    if verbose:
        print('Open connection via RS232')
    inst = rm.open_resource(sPort)
    inst.baud_rate = int(sBaudRate)
    inst.parity = Parity.even
    inst.data_bits = 7
    return inst
   
# sends a write command string sCmd via RS232 to the lock-in already opened as inst
# and returns the resulting response string and status byte
def Inst_Query_Command_RS232(inst, sCmd, verbose = True):
    if verbose:
        print('Send query command: ' + sCmd)
    # serial port commands need sending one character at a time and checking for 
    # handshake
    for i in range(len(sCmd)):
        inst.write_raw(sCmd[i])
        sEcho = inst.read_bytes(1).decode('utf8')
    # write the terminator
    inst.write_raw('\r')
    sResponse = ''
    # read until recieve a prompt of ? or *
    sEcho = inst.read_bytes(1).decode('utf8')
    while (sEcho != '?') and (sEcho != '*'):
        sResponse = sResponse + sEcho
        sEcho = inst.read_bytes(1).decode('utf8')
    sResponse = sResponse.replace('\n',' ')
    sResponse = sResponse.replace('\r',' ')
    # set returned status byte to Comamnd Done
    nStatusByte = 1
    if (sEcho == '*'):
       nStatusByte = 1
    if ((sEcho == '?') & (sCmd != 'ST')):
        # send the status command to get instrument status except if this is being
        # called by a ST command itself
        sStatus = Inst_Query_Command_RS232(inst, 'ST')
        nStatusByte = int(sStatus[0])
    # mask out bits 4, 5 & 6 which are not consistent across all instruments
    nStatusByte = nStatusByte & 143
    # return the response from the instrument and the status byte
    return sResponse, nStatusByte  

# closes the open resource (use for USB, GPIB, RS232, and Ethernet)
def Connection_Close(inst,verbose = True):
    if verbose:
        print('Close connection')
    inst.before_close()
    return_status = inst.close()
    return return_status


def Print_Status_Byte(nStatusByte):
    if (nStatusByte & 1 == 1):
       print('Command Done')
    if (nStatusByte & 2 == 2):
       print('Invalid command')
    if (nStatusByte & 4 == 4):
       print('Command parameter error')
    if (nStatusByte & 8 == 8):
       print('Reference unlock')
    # bits 4, 5 and 6 are instrument model number dependent so are
    # not decoded here
    if (nStatusByte & 128 == 128):
       print('Data Available')

# x = "CBD00268" gets mag,phase,dac1
# x = "CBD
list_voltsp = [  "+0"+str(h)+"."+str(i) + str(j) + str(k) for h in range(10) for i in range(10) for j in range(10) for k in range(10)]
list_voltsn = [  "-0"+str(h)+"."+str(i) + str(j) + str(k) for h in range(9,-1,-1) for i in range(9,-1,-1) for j in range(9,-1,-1) for k in range(9,-1,-1)]
list_volts = list_voltsn + list_voltsp

def check_cmmd(tReturn):
    Print_Status_Byte(tReturn[1])
    if (tReturn[0] != ''):
        print('Response from lockin-in detected. \n')
        print('Command response: ' + tReturn[0] + '\n')  
        
def convert_lockin_data(raw_data_from_lockin):
    out = []
    list1 = raw_data_from_lockin[0].split(" ")
    
    for li in list1:
        if is_float(li):
            out.append(float(li))
    return out
    
def is_float(element: any) -> bool:
    #If you expect None to be passed:
    if element is None: 
        return False
    try:
        float(element)
        return True
    except ValueError:
        return False
    
#    #Autophase
#    tReturn = Inst_Query_Command_RS232(inst, "AQN")
#    check_cmmd(tReturn)
    
#Puts the scan parameters in the correct string format
## so that the lockin can read it. 
def hz_to_indx(x_hz):
    xtemp = int(x_hz*1e3)
    return str(xtemp)
    
def ampv_to_indx(x_volts):
    xtemp = np.round(x_volts,4)
    return str(xtemp)

def checkLockinDataFormat(x):
    try:
        number = float(x)
        
    except ValueError:
        out = ""
        for i in x:
            if "\\" in r"%r" % i:
                break
            else:
                out = out+i
        number = float(out)
        
    return number
# Time cte: 7:5ms,8:10ms,9:20ms,10:50ms,11:100ms,12:200ms 13:500 ms
# Sensitivity: 15: 1pA, 16: 2pA, 17: 5pA


def dacScanStep(i,expobj,inst,tcRatio,count_numpass):
        #set DAC value
    cmmdi = "DAC.1" + list_volts[i]
    Inst_Query_Command_RS232(inst, cmmdi,verbose = False)

    if count_numpass== 0:
        time.sleep(2)
    else:
        time.sleep(tcRatio*dict_tc_to_sec.get(expobj.timeconstant)) 

    datai = []
    dataMag,temp = Inst_Query_Command_RS232(inst, dict_demodv.get(expobj.demod1) ,verbose = False)
    dataPhi,temp = Inst_Query_Command_RS232(inst, dict_demodv.get(expobj.demod2),verbose = False)
    
    if i <int(len(list_volts)/2):
        datai.append(-float( list_volts[i][1:] ))
    else:
        datai.append(float( list_volts[i][1:] ))

    datai.append(checkLockinDataFormat(dataMag) )
    datai.append(checkLockinDataFormat(dataPhi) )
    

    return datai

def update_RP(expobj,rm):
    
    inst = Connection_Open_RS232(expobj.port, "9600",rm,verbose = False)
    dataMag,temp = Inst_Query_Command_RS232(inst, dict_demodv.get(expobj.demod1) ,verbose = False)
    dataPhi,temp = Inst_Query_Command_RS232(inst, dict_demodv.get(expobj.demod2),verbose = False)
    Connection_Close(inst,verbose = False)        
    
    return dataMag,dataPhi

def mV_to_index(x_mV):
    idx_temp = int(x_mV)
    return idx_temp + len(list_voltsn)
def V_to_index(x_V):
    idx_temp = int( float(x_V)*1000 )
    return idx_temp + len(list_voltsn)
    
def setLockinParams(expobj,rm):

    inst = Connection_Open_RS232(expobj.port, "9600",rm)
    
    Inst_Query_Command_RS232(inst, "TC"+dict_tc.get( expobj.timeconstant ), verbose = False)
    Inst_Query_Command_RS232(inst, "SEN"+dict_sens.get(expobj.sensitivity ), verbose = False)
    Inst_Query_Command_RS232(inst, "OF."+str(expobj.freq), verbose = False)
    Inst_Query_Command_RS232(inst, "OA."+str(expobj.amp), verbose = False)

    Connection_Close(inst)        

def fitParabola(expobj,vi,vf):
    
    def parabola(x, A,B,C):
        return A*(x-B)**2 + C

    df = expobj.datatemp
    colnames = df.columns
    vi_indx = df[colnames[0]].iloc[(df[colnames[0]]-vi).abs().argsort()[:1] ].index[0]
    vf_indx = df[colnames[0]].iloc[(df[colnames[0]]-vf).abs().argsort()[:1] ].index[0]
    
    x = df[colnames[0]][vi_indx:vf_indx].values
    y = df[colnames[1]][vi_indx:vf_indx].values*1e12
    
    
    model = lmfit.Model(parabola)
    results = model.fit(y, x=x, A =y.max(),B = x[y.argmin()] , C = y.min() )
    yeval = results.best_fit
    y0    = results.init_fit
    return x,y0,yeval,results.params.get("B").value

def fitLinear(expobj,vi,vf):
    
    def line(x, A,B):
        return A*x + B

    df = expobj.datatemp

    colnames = df.columns
    vi_indx = df[colnames[0]].iloc[(df[colnames[0]]-vi).abs().argsort()[:1] ].index[0]
    vf_indx = df[colnames[0]].iloc[(df[colnames[0]]-vf).abs().argsort()[:1] ].index[0]
    
    x = df[colnames[0]][vi_indx:vf_indx].values
    y = df[colnames[1]][vi_indx:vf_indx].values*1e12
    
    
    model = lmfit.Model(line)
    results = model.fit(y, x=x, A =(y.max()-y.min())/(x.max()-x.min()) ,B = np.abs(y).min() )
    yeval = results.best_fit
    y0    = results.init_fit

    return x,y0,yeval,-results.params.get("B").value/results.params.get("A").value,results.params.get("A").value



def freqSweep(indxs,expobj,rm):
    time_cte = dict_tc.get( expobj.timeconstant )
    tc_sec     = dict_tc_to_sec.get(expobj.timeconstant)
    sens     = dict_sens.get(expobj.sensitivity )
    inst = Connection_Open_RS232(expobj.port, "9600",rm)
    
    #print("Starting dac scan.. \n")
    #print("Centering phase, zeroing dac1...\n")
    Inst_Query_Command_RS232(inst, "AQN", verbose = False)
    Inst_Query_Command_RS232(inst, "TC"+time_cte, verbose = False)
    Inst_Query_Command_RS232(inst, "SEN"+sens, verbose = False)
    Inst_Query_Command_RS232(inst, "DAC1+00000", verbose = False)
    
    scanrange = np.arange(indxs[0], indxs[1],indxs[2])
    
    datai = []
    count= 0 
    for freqi in scanrange:

        #set DAC value
        cmmdi = "OF" + hz_to_indx(freqi)
        Inst_Query_Command_RS232(inst, cmmdi,verbose = False) 
        
        if count == 0:
            time.sleep(2)
        else:
            time.sleep(1*tc_sec)  

        dataMag,temp = Inst_Query_Command_RS232(inst, dict_demodv.get(expobj.demod1) ,verbose = False)
        count +=1        

        datai.append(freqi)
        datai.append(checkLockinDataFormat(dataMag) )

    data = np.array(datai).reshape(-1,2)
        
    Connection_Close(inst)
    print(data)
    return pd.DataFrame(data,columns = ["Freq. (Hz) ",expobj.demod1] )