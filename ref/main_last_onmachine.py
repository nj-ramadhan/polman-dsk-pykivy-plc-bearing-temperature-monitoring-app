import sys
import os
import numpy as np
np.set_printoptions(threshold=sys.maxsize)
import kivy
from kivymd.app import MDApp
from kivymd.toast import toast
from kivymd.uix.datatables import MDDataTable
from kivy.lang import Builder
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock
from kivy.config import Config
from kivy.metrics import dp
from kivy.garden.matplotlib.backend_kivyagg import FigureCanvasKivyAgg
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.figure import Figure
from matplotlib.colors import ListedColormap, LinearSegmentedColormap
from matplotlib.ticker import AutoMinorLocator
from datetime import datetime
from pathlib import Path
from kivy.properties import ObjectProperty
import time
import minimalmodbus
import serial
from serial.tools import list_ports

plt.style.use("bmh")

colors = {
    "Red": {
        "200": "#EE2222",
        "500": "#EE2222",
        "700": "#EE2222",
    },
    "Blue": {
        "200": "#196BA5",
        "500": "#196BA5",
        "700": "#196BA5",
    },
    "Light": {
        "StatusBar": "E0E0E0",
        "AppBar": "#202020",
        "Background": "#EEEEEE",
        "CardsDialogs": "#FFFFFF",
        "FlatButtonDown": "#CCCCCC",
    },
    "Dark": {
        "StatusBar": "101010",
        "AppBar": "#E0E0E0",
        "Background": "#111111",
        "CardsDialogs": "#000000",
        "FlatButtonDown": "#333333",
    },
}

DEBUG = False

STEPS = 51
# MAX_POINT_WENNER = 500
MAX_POINT = 10000
ELECTRODES_NUM = 48

PIN_ENABLE = 23 #16
PIN_POLARITY = 24 #18

C_OFFSET = 2.5412
C_GAIN = 5.0 * 1000.0 #channge from A to mA with gain

P_OFFSET = 0.001
P_GAIN = 1.0
# SHUNT_OHMS = 0.1
# MAX_EXPECTED_AMPS = 0.1
# 
# PIN_FWD = 16
# PIN_REV = 18

USERNAME = "labtek"
DISK_ADDRESS = Path("/media/labtek/RESDONGLE/")
#DISK_ADDRESS = Path("/media/" + USERNAME + "/RESDONGLE/")
SERIAL_NUMBER = "2301212112233412"

BAUDRATE = 19200
BYTESIZE = 8
PARITY = serial.PARITY_NONE
STOPBIT = 2
TIMEOUT = 0.05

if(not DEBUG):
    ser = serial.Serial("COM3")  # COM to Arduino Nano, checked manually
    ser.baudrate = BAUDRATE
    ser.parity = PARITY
    ser.bytesize = BYTESIZE
    time.sleep(3)
    # import ADC and I2C library 
#     import board
#     import busio
#     import adafruit_ads1x15.ads1115 as ADS
#     from adafruit_ads1x15.analog_in import AnalogIn
#     import RPi.GPIO as GPIO    
#     # GPIO control and sensor acquisiton
#     import RPi.GPIO as GPIO
#     i2c = busio.I2C(board.SCL, board.SDA)
#     ads = ADS.ADS1115(i2c)
# #     from ina219c import INA219 as read_c
# #     from ina219p import INA219 as read_p

#     GPIO.cleanup
#     GPIO.setmode(GPIO.BCM)
#     GPIO.setup(PIN_ENABLE, GPIO.OUT)
#     GPIO.setup(PIN_POLARITY, GPIO.OUT)

# x_datum = np.zeros(MAX_POINT)
# y_datum = np.zeros(MAX_POINT)
x_electrode = np.zeros((4, MAX_POINT))
n_electrode = np.zeros((ELECTRODES_NUM, STEPS))
c_electrode = np.array(["#196BA5","#FF0000","#FFDD00","#00FF00","#00FFDD"])
l_electrode = np.array(["Datum","C1","C2","P1","P2"])
arr_electrode = np.zeros([4, 0])
data_base = np.zeros([5, 0])
data_electrode = np.zeros([4, 0], dtype=int)
data_pos = np.zeros([2, 0])

checks_mode = []
checks_config = []
dt_mode = ""
dt_config = ""
dt_distance = 1
dt_constant = 1
real_constant = 1
dt_time = 500
dt_cycle = 1

dt_measure = np.zeros(6)
dt_current = np.zeros(10)
dt_voltage = np.zeros(10)
flag_run = False
flag_measure = False
flag_dongle = True
flag_autosave_data = False
flag_autosave_graph = False

data_rtu = np.zeros([216, 0], dtype=int)
data_rtu1 = np.zeros(36, dtype=int)
data_rtu2 = np.zeros(36, dtype=int)
data_rtu3 = np.zeros(36, dtype=int)
data_rtu4 = np.zeros(36, dtype=int)
data_rtu5 = np.zeros(36, dtype=int)
data_rtu6 = np.zeros(36, dtype=int)

step = 0
max_step = 1

count_mounting = 0
inject_state = 0
graph_state = 0

class ScreenSplash(BoxLayout):
    screen_manager = ObjectProperty(None)
    screen_setting = ObjectProperty(None)
    app_window = ObjectProperty(None)
    
    def __init__(self, **kwargs):
        super(ScreenSplash, self).__init__(**kwargs)
        try:
            os.system('cmd /c "cd /media"')
            os.system('cmd /c "sudo rm -r /labtek"')
        except:
            pass
        Clock.schedule_interval(self.update_progress_bar, 0.01)

    def update_progress_bar(self, *args):
        if (self.ids.progress_bar.value + 1) < 100:
            raw_value = self.ids.progress_bar_label.text.split("[")[-1]
            value = raw_value[:-2]
            value = eval(value.strip())
            new_value = value + 1
            self.ids.progress_bar.value = new_value
            self.ids.progress_bar_label.text = "Loading.. [{:} %]".format(new_value)
        else:
            self.ids.progress_bar.value = 100
            self.ids.progress_bar_label.text = "Loading.. [{:} %]".format(100)
            time.sleep(0.5)
            self.screen_manager.current = "screen_setting"
            return False


class ScreenSetting(BoxLayout):
    screen_manager = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(ScreenSetting, self).__init__(**kwargs)
        Clock.schedule_once(self.delayed_init)
        Clock.schedule_interval(self.regular_check, 1)

    def regular_check(self, dt):
        global flag_run
        if(flag_run):
            self.ids.bt_measure.text = "STOP MEASUREMENT"
            self.ids.bt_measure.md_bg_color = "#A50000"
        else:
            self.ids.bt_measure.text = "RUN MEASUREMENT"
            self.ids.bt_measure.md_bg_color = "#196BA5"

    def delayed_init(self, dt):
        global rtu1, rtu2, rtu3, rtu4, rtu5, rtu6
        global data_rtu1, data_rtu2, data_rtu3, data_rtu4, data_rtu5, data_rtu6

        self.ids.bt_shutdown.md_bg_color = "#A50000"
        self.ids.mode_ves.active = True

        self.fig, self.ax = plt.subplots()
        self.fig.set_facecolor("#eeeeee")
        self.fig.tight_layout()
        l, b, w, h = self.ax.get_position().bounds
        self.ax.set_position(pos=[l, b + 0.3*h, w, h*0.7])
        
        self.ax.set_xlabel("distance [m]", fontsize=10)
        self.ax.set_ylabel("n", fontsize=10)

        self.ids.layout_illustration.add_widget(FigureCanvasKivyAgg(self.fig))

        try:
            ports = list_ports.comports(include_links=False)
            for port in ports :
#                com_port = port.device[0]
                
                # change port setting to "COMXX" for windows
                com_port = "COM4"
                toast("switching box is connected to " + com_port)
                print("switching box is connected to " + com_port)

            rtu1 = minimalmodbus.Instrument(com_port, 1, mode=minimalmodbus.MODE_RTU)
            rtu2 = minimalmodbus.Instrument(com_port, 2, mode=minimalmodbus.MODE_RTU)
            rtu3 = minimalmodbus.Instrument(com_port, 3, mode=minimalmodbus.MODE_RTU)
            rtu4 = minimalmodbus.Instrument(com_port, 4, mode=minimalmodbus.MODE_RTU)
            rtu5 = minimalmodbus.Instrument(com_port, 5, mode=minimalmodbus.MODE_RTU)
            rtu6 = minimalmodbus.Instrument(com_port, 6, mode=minimalmodbus.MODE_RTU)

            rtu1.write_bits(80, data_rtu1.tolist())
            rtu2.write_bits(80, data_rtu2.tolist())
            rtu3.write_bits(80, data_rtu3.tolist())
            rtu4.write_bits(80, data_rtu4.tolist())
            rtu5.write_bits(80, data_rtu5.tolist())
            rtu6.write_bits(80, data_rtu6.tolist())

        except:
            toast("no switching box connected")
            print("no switching box connected")

    def illustrate(self):
        global dt_mode
        global dt_config
        global dt_distance
        global dt_constant
        global dt_time
        global dt_cycle
        global x_datum
        global y_datum
        global data_pos
        global data_rtu
        global max_step
        global arr_electrode

        dt_distance = self.ids.slider_distance.value
        dt_constant = self.ids.slider_constant.value
        dt_time = int(self.ids.slider_time.value)
        dt_cycle = int(self.ids.slider_cycle.value)

        self.fig, self.ax = plt.subplots()
        self.ids.layout_illustration.remove_widget(FigureCanvasKivyAgg(self.fig))
        x_datum = np.zeros(MAX_POINT)
        y_datum = np.zeros(MAX_POINT)
        x_electrode = np.zeros((4, MAX_POINT))

        if("WENNER (ALPHA)" in dt_config):
            num_step = 0
            num_trial = 1
            for multiplier in range(dt_constant):
                for pos_el in range(ELECTRODES_NUM - 3 * num_trial):
                    x_electrode[0, num_step] = pos_el
                    x_electrode[1, num_step] = num_trial + x_electrode[0, num_step]
                    x_electrode[2, num_step] = num_trial + x_electrode[1, num_step]
                    x_electrode[3, num_step] = num_trial + x_electrode[2, num_step]
                    x_datum[num_step] = (
                        x_electrode[1, num_step]
                        + (x_electrode[2, num_step] - x_electrode[1, num_step]) / 2
                    ) * dt_distance
                    y_datum[num_step] = (multiplier + 1) * dt_distance

                    num_step += 1

                num_trial += 1

        elif("WENNER (BETA)" in dt_config):
            num_step = 0
            num_trial = 1
            for multiplier in range(dt_constant):
                for pos_el in range(ELECTRODES_NUM - 3 * num_trial):
                    x_electrode[0, num_step] = pos_el
                    x_electrode[1, num_step] = num_trial + x_electrode[0, num_step]
                    x_electrode[2, num_step] = num_trial + x_electrode[1, num_step]
                    x_electrode[3, num_step] = num_trial + x_electrode[2, num_step]
                    x_datum[num_step] = (x_electrode[1, num_step] + (x_electrode[2, num_step] - x_electrode[1, num_step])/2) * dt_distance
                    y_datum[num_step] = (multiplier + 1) * dt_distance
                    
                    num_step += 1

                num_trial += 1

        if("WENNER (GAMMA)" in dt_config):
            num_step = 0
            num_trial = 1
            for multiplier in range(dt_constant):
                for pos_el in range(ELECTRODES_NUM - 3 * num_trial):
                    x_electrode[0, num_step] = pos_el
                    x_electrode[1, num_step] = num_trial + x_electrode[0, num_step]
                    x_electrode[2, num_step] = num_trial + x_electrode[1, num_step]
                    x_electrode[3, num_step] = num_trial + x_electrode[2, num_step]
                    x_datum[num_step] = (x_electrode[1, num_step] + (x_electrode[2, num_step] - x_electrode[1, num_step])/2) * dt_distance
                    y_datum[num_step] = (multiplier + 1) * dt_distance
                    
                    num_step += 1

                num_trial += 1

        elif("SCHLUMBERGER" in dt_config):
            num_step = 0
            num_trial = 1
            for multiplier in range(dt_constant):
                for pos_el in range(ELECTRODES_NUM - 3 * num_trial):
                    x_electrode[0, num_step] = pos_el
                    x_electrode[1, num_step] = num_trial + x_electrode[0, num_step]
                    x_electrode[2, num_step] = num_trial + x_electrode[1, num_step]
                    x_electrode[3, num_step] = num_trial + x_electrode[2, num_step]
                    x_datum[num_step] = (x_electrode[1, num_step] + (x_electrode[2, num_step] - x_electrode[1, num_step])/2) * dt_distance
                    y_datum[num_step] = (multiplier + 1) * dt_distance
                    
                    num_step += 1

                num_trial += 1

        elif("DIPOLE-DIPOLE" in dt_config):
            nmax_available = 0
            if(ELECTRODES_NUM % 2) != 0:
                if(dt_constant > (ELECTRODES_NUM - 3) / 2):
                    nmax_available = (ELECTRODES_NUM - 3) / 2
                else:
                    nmax_available = dt_constant
            else:
                if(dt_constant > (ELECTRODES_NUM - 3) / 2):
                    nmax_available = round((ELECTRODES_NUM - 3) / 2)
                else:
                    nmax_available = dt_constant

            num_datum = 0
            count_datum = 0      
            for i in range(nmax_available):
                for j in range(ELECTRODES_NUM - 1 - i * 2):
                    num_datum = num_datum + j
                count_datum = count_datum + num_datum
                num_datum = 0     

            num_step = 0
            num_trial = 0
            for i in range(nmax_available):
                for j in range(ELECTRODES_NUM - 1 - i * 2):
                    for k in range(ELECTRODES_NUM - i * 2 - j - 1):
                        x_electrode[1, num_step] = j - 1
                        x_electrode[0, num_step] = j + (i - 2)
                        x_electrode[2, num_step] = num_trial + 2 + x_electrode[0, num_step]
                        x_electrode[3, num_step] = i + 1 + x_electrode[2, num_step]
                        x_datum[num_step] = (x_electrode[0, num_step] + (x_electrode[2, num_step] - x_electrode[0, num_step])/2) * dt_distance
                        y_datum[num_step] = (i + 1) * dt_distance
                        
                        num_step += 1
                        num_trial += 1

                    num_trial = 0
        else:
            x_electrode[0,0] = 0
            x_electrode[1,0] = 1
            x_electrode[2,0] = 2
            x_electrode[3,0] = 3

        try:
            max_step = np.trim_zeros(x_electrode[1,:]).size

            data_c1 = x_electrode[0,:max_step]
            data_p1 = x_electrode[1,:max_step]
            data_p2 = x_electrode[2,:max_step]
            data_c2 = x_electrode[3,:max_step]

            arr_electrode = np.array([data_c1, data_p1, data_p2, data_c2], dtype=int)
            print(arr_electrode.T)

            data_rtu = np.zeros([216,max_step], dtype=int)
            for i in range(max_step):
                data_rtu[arr_electrode[0,i]*4, i] = 1
                data_rtu[arr_electrode[1,i]*4 + 1, i] = 1
                data_rtu[arr_electrode[2,i]*4 + 2, i] = 1
                data_rtu[arr_electrode[3,i]*4 + 3, i] = 1
            # print(data_rtu.T)

        except:
            print("error simulating")
            toast("error simulating")

        self.fig.set_facecolor("#eeeeee")
        self.fig.tight_layout()
        l, b, w, h = self.ax.get_position().bounds
        self.ax.set_position(pos=[l, b + 0.3*h, w*0.9, h*0.7])
        self.ax.set_xlabel("distance [m]", fontsize=10)
        self.ax.set_ylabel("n", fontsize=10)
       
        self.ax.set_facecolor("#eeeeee")
        
        x_data = np.trim_zeros(x_datum)
        y_data = np.trim_zeros(y_datum)
        # x_data = x_datum[np.array([x.size>0 for x in x_datum])]
        # y_data = y_datum[np.array([y.size>0 for y in y_datum])]
        data_pos = np.array([x_data, y_data])

        #datum location
        self.ax.scatter(x_data, y_data, c=c_electrode[0], label=l_electrode[0], marker='.')

        #electrode location
        self.ax.scatter(x_electrode[0,0]*dt_distance , 0, c=c_electrode[1], label=l_electrode[1], marker=7)
        self.ax.scatter(x_electrode[1,0]*dt_distance , 0, c=c_electrode[2], label=l_electrode[2], marker=7)
        self.ax.scatter(x_electrode[2,0]*dt_distance , 0, c=c_electrode[3], label=l_electrode[3], marker=7)
        self.ax.scatter(x_electrode[3,0]*dt_distance , 0, c=c_electrode[4], label=l_electrode[4], marker=7)

        self.ax.invert_yaxis()
        self.ax.legend(loc='center left', bbox_to_anchor=(1, 0.5), title="Electrode")         
        self.ids.layout_illustration.clear_widgets()
        self.ids.layout_illustration.add_widget(FigureCanvasKivyAgg(self.fig))

    def measure(self):
        global flag_run

        if(flag_run):
            flag_run = False
        else:
            flag_run = True

    def checkbox_mode_click(self, instance, value, waves):
        global checks_mode
        global dt_mode
        
        if value == True:
            checks_mode.append(waves)
            modes = ''
            for x in checks_mode:
                modes = f'{modes} {x}'
            self.ids.output_mode_label.text = f'{modes} MODE CHOSEN'
        else:
            checks_mode.remove(waves)
            modes = ''
            for x in checks_mode:
                modes = f'{modes} {x}'
            self.ids.output_mode_label.text = ''
        
        dt_mode = modes

    def checkbox_config_click(self, instance, value, waves):
        global checks_config
        global dt_config

        if value == True:
            checks_config.append(waves)
            configs = ''
            for x in checks_config:
                configs = f'{configs} {x}'
            self.ids.output_config_label.text = f'{configs} CONFIGURATION CHOSEN'
        else:
            checks_config.remove(waves)
            configs = ''
            for x in checks_config:
                configs = f'{configs} {x}'
            self.ids.output_config_label.text = ''
        
        dt_config = configs

    def screen_setting(self):
        self.screen_manager.current = 'screen_setting'

    def screen_data(self):
        self.screen_manager.current = 'screen_data'

    def screen_graph(self):
        self.screen_manager.current = 'screen_graph'

    def exec_shutdown(self):
        global flag_run

        if(not flag_run):        
            toast("shutting down system")
            os.system("shutdown /s /t 1") #for windows os
            # os.system("shutdown -h now")
        else:
            toast("cannot shutting down while measuring")


class ScreenData(BoxLayout):
    screen_manager = ObjectProperty(None)

    def __init__(self, **kwargs):
        global dt_time
        global dt_cycle

        super(ScreenData, self).__init__(**kwargs)
        Clock.schedule_once(self.delayed_init)
        Clock.schedule_interval(self.regular_check, 2.5)

    def stop_measure(self):
        global flag_measure
        global inject_state
        global flag_autosave_data
        global step
        global max_step
        global ser

        self.ids.bt_measure.text = "RUN MEASUREMENT"
        self.ids.bt_measure.md_bg_color = "#196BA5"
        Clock.unschedule(self.measurement_check)
        Clock.unschedule(self.inject_current)
        inject_state = 0
        flag_measure = False
        step = 0
        max_step = 0
        self.reset_switching()
        if(not DEBUG):
            # change to communication to exec relay
            # GPIO.output(PIN_ENABLE, GPIO.HIGH)
            # GPIO.output(PIN_POLARITY, GPIO.HIGH)
            ser.write(b"C")
        if flag_autosave_data:
            self.autosave_data()
            flag_autosave_data = False

    def regular_check(self, dt):
        global flag_run
        global flag_measure
        global flag_dongle
        global count_mounting
        global dt_time
        global dt_cycle
        global inject_state
        global flag_autosave_data
        global step
        global max_step
        global ser

        if(flag_run):
            self.ids.bt_measure.text = "STOP MEASUREMENT"
            self.ids.bt_measure.md_bg_color = "#A50000"

            flag_autosave_data = True
            measure_interval = ((4 * dt_cycle * dt_time) / 1000)
            inject_interval = ((dt_time) / 1000)
            # print("measure interval:", measure_interval, " inject interval:", inject_interval)

            if("(VES) VERTICAL ELECTRICAL SOUNDING" in dt_mode):
                if(flag_measure == False):
                    Clock.schedule_interval(self.measurement_check, measure_interval)
                    Clock.schedule_interval(self.inject_current, inject_interval)
                flag_measure = True
        
            elif("(SP) SELF POTENTIAL" in dt_mode):
                if(flag_measure == False):
                    Clock.schedule_interval(self.measurement_check, measure_interval)
                    Clock.schedule_interval(self.measurement_sampling, inject_interval)
                flag_measure = True
                
            elif("(R) RESISTIVITY" in dt_mode):
                if(flag_measure == False):
                    Clock.schedule_interval(self.measurement_check, measure_interval)
                    Clock.schedule_interval(self.inject_current, inject_interval)
                flag_measure = True
                
            elif("(R+IP) INDUCED POLARIZATION" in dt_mode):
                if(flag_measure == False):
                    Clock.schedule_interval(self.measurement_check, measure_interval)
                    Clock.schedule_interval(self.inject_current, inject_interval)
                flag_measure = True                        
            else:
                pass

        else:
            # self.stop_measure()
            pass
           
        if not DISK_ADDRESS.exists() and flag_dongle:
             try:
                 toast("try mounting")
                 serial_file = str(DISK_ADDRESS) + "/serial.key"
                 # print(serial_file)
                 with open(serial_file,"r") as f:
                     serial_number = f.readline()
                     if serial_number == SERIAL_NUMBER:
                         print("success, serial number is valid")
                         self.ids.bt_save_data.disabled = False
                     else:
                         print("fail, serial number is invalid")
                         self.ids.bt_save_data.disabled = True                    
             except:
                 toast(f"Could not mount Dongle")
                 self.ids.bt_save_data.disabled = True
                 count_mounting += 1
                 if(count_mounting > 10):
                     flag_dongle = False 

    def measurement_check(self, dt):
        global flag_run
        global dt_time
        global data_base
        global data_electrode
        global dt_current
        global dt_voltage
        global x_electrode
        global step
        global ser

        if("WENNER (ALPHA)" in dt_config):
            k = 2 * np.pi * dt_distance * dt_constant
        elif("WENNER (BETA)" in dt_config):
            k = 6 * np.pi * dt_distance * dt_constant
        elif("WENNER (GAMMA)" in dt_config):
            k = 3 * np.pi * dt_distance * dt_constant
        elif("POLE-POLE" in dt_config):
            k = 2 * np.pi * dt_distance * dt_constant
        elif("DIPOLE-DIPOLE" in dt_config):
            k = np.pi * dt_distance * dt_constant * (dt_constant + 1) * (dt_constant + 2)
        elif("SCHLUMBERGER" in dt_config):
            k = np.pi * dt_distance * dt_constant * (dt_constant + 1)

        voltage = np.max(np.fabs(dt_voltage))
        current = np.max(np.fabs(dt_current))
        if(current > 0.0):
            resistivity = k * voltage / current
        else:
            resistivity = 0.0
            
        std_resistivity = np.std(data_base[2, :])
        ip_decay = (np.sum(dt_voltage) / voltage ) * ((dt_cycle * dt_time)/10000)

        data_acquisition = np.array([voltage, current, resistivity, std_resistivity, ip_decay])
        data_acquisition.resize([5, 1])
        data_base = np.concatenate([data_base, data_acquisition], axis=1)

        try:
            data_c1 = arr_electrode[0, step] + 1
            data_p1 = arr_electrode[1, step] + 1
            data_p2 = arr_electrode[2, step] + 1
            data_c2 = arr_electrode[3, step] + 1
            electrode_pos = np.array([data_c1, data_p1, data_p2, data_c2])
        except:
            electrode_pos = np.array([1, 2, 3, 4])

        electrode_pos.resize([4, 1])
        data_electrode = np.concatenate([data_electrode, electrode_pos], axis=1)

        self.ids.realtime_voltage.text = f"{voltage:.3f}"
        self.ids.realtime_current.text = f"{current:.3f}"
        self.ids.realtime_resistivity.text = f"{resistivity:.3f}"

        avg_voltage = np.average(data_base[0, :])
        avg_current = np.average(data_base[1, :])
        avg_resistivity = np.average(data_base[2, :])

        self.ids.average_voltage.text = f"{avg_voltage:.3f}"
        self.ids.average_current.text = f"{avg_current:.3f}"
        self.ids.average_resistivity.text = f"{avg_resistivity:.3f}"

        self.data_tables.row_data=[(f"{i + 1}", f"{data_base[0,i]:.3f}", f"{data_base[1,i]:.3f}", f"{data_base[2,i]:.3f}", f"{data_base[3,i]:.3f}", f"{data_base[4,i]:.3f}") for i in range(len(data_base[1]))]

        # print("shape:", arr_electrode.shape, " step:",step)

        if(arr_electrode.shape == (4, step+1)):
            print("stop")
            flag_run = False
            self.stop_measure()


    def inject_current(self, dt):
        global inject_state
        global step
        global dt_time
        global dt_cycle
        global ser

        if(inject_state >= int(4 * dt_cycle)):
            Clock.unschedule(self.measurement_sampling)
            inject_state = 0
            step += 1
            
        if(inject_state == 0 | inject_state == 4 | inject_state == 8 | inject_state == 12 | inject_state == 16 | inject_state == 20 | inject_state == 24 | inject_state == 28 | inject_state == 32 | inject_state == 36):
            Clock.unschedule(self.measurement_sampling)
            self.switching_commands()
            if(not DEBUG):
                # change to communication to exec relay
                # GPIO.output(PIN_ENABLE, GPIO.HIGH)
                # GPIO.output(PIN_POLARITY, GPIO.HIGH)
                ser.write(b"C")
                print("not injecting current")
            
        elif(inject_state == 1 | inject_state == 5 | inject_state == 9 | inject_state == 13 | inject_state == 17 | inject_state == 21 | inject_state == 25 | inject_state == 29 | inject_state == 33 | inject_state == 37):
            Clock.schedule_interval(self.measurement_sampling, (dt_time) / 2000)
            if(not DEBUG):
                # change to communication to exec relay
                # GPIO.output(PIN_ENABLE, GPIO.LOW)
                # GPIO.output(PIN_POLARITY, GPIO.HIGH)
                ser.write(b"D")
                print("inject positive current")
            
        elif(inject_state == 2 | inject_state == 6 | inject_state == 10 | inject_state == 14 | inject_state == 18 | inject_state == 22 | inject_state == 26 | inject_state == 30 | inject_state == 34 | inject_state == 38):
            Clock.unschedule(self.measurement_sampling)
            if(not DEBUG):
                # change to communication to exec relay
                # GPIO.output(PIN_ENABLE, GPIO.HIGH)
                # GPIO.output(PIN_POLARITY, GPIO.HIGH)
                ser.write(b"C")
                print("not injecting current")
            
        elif(inject_state == 3 | inject_state == 7 | inject_state == 11 | inject_state == 15 | inject_state == 19 | inject_state == 23 | inject_state == 27 | inject_state == 31 | inject_state == 35 | inject_state == 39):
            Clock.schedule_interval(self.measurement_sampling, (dt_time) / 2000)
            if(not DEBUG):
                # change to communication to exec relay
                # GPIO.output(PIN_ENABLE, GPIO.LOW)
                # GPIO.output(PIN_POLARITY, GPIO.LOW)
                ser.write(b"E")
                print("inject negative current")
            
        # print("step:", step, ", inject:",inject_state)
        inject_state += 1
        
    def measurement_sampling(self, dt):
        global dt_current
        global dt_voltage
        global ads
        global ser

        # Data acquisition
        dt_voltage_temp = np.zeros_like(dt_voltage)
        dt_current_temp = np.zeros_like(dt_current)

        if (not DEBUG):
            ser.write(b"A")
            if ser.inWaiting() > 0:
                data = (ser.readline().decode("utf-8").strip())  # read the incoming data and remove newline character
                vF = float(data)
                realtime_current = vF
                print("Realtime Curr:")
                print(realtime_current)
                dt_current_temp[:1] = realtime_current
                # change to communication to read analog current
                # chan_c = AnalogIn(ads, ADS.P0)
                # realtime_current = (chan_c.voltage - C_OFFSET) * C_GAIN
                # dt_current_temp[:1] = realtime_current
                # ser.write(b"A")
                # time.sleep(1)
                # if ser.inWaiting() > 0:
                #     data = (ser.readline().decode("utf-8").strip())  # read the incoming data and remove newline character
                #     vF = float(data)
                #     realtime_current = vF
                #     print("Realtime Curr:")
                #     print(realtime_current)
                #     dt_current_temp[:1] = realtime_current
            # except serial.SerialException as exxx:
            #     toast("error read current")
            #     print(exxx)
            #     dt_current_temp[:1] = 0.0

            try:
                # change to communication to read analog potential voltage
                # chan_p = AnalogIn(ads, ADS.P1)
                # realtime_voltage = (chan_p.voltage - P_OFFSET) * P_GAIN
                # dt_voltage_temp[:1] = realtime_voltage
                ser.write(b"B")
                if ser.inWaiting() > 0:
                    data1 = (
                        ser.readline().decode("utf-8").strip()
                    )  # read the incoming data and remove newline character
                    vF1 = float(data1)
                    # print(vF)
                    realtime_voltage = vF1
                    dt_voltage_temp[:1] = realtime_voltage

            except:
                toast("error read voltage")
                dt_voltage_temp[:1] = 0.0

        dt_voltage_temp[1:] = dt_voltage[:-1]
        dt_voltage = dt_voltage_temp

        dt_current_temp[1:] = dt_current[:-1]
        dt_current = dt_current_temp

    def switching_commands(self):
        global step
        global max_step
        global ser

        try:
            reshaped_data_rtu = data_rtu.T[step,:].reshape(6, 36)

            data_rtu1 = reshaped_data_rtu[0]
            data_rtu2 = reshaped_data_rtu[1]
            data_rtu3 = reshaped_data_rtu[2]
            data_rtu4 = reshaped_data_rtu[3]
            data_rtu5 = reshaped_data_rtu[4]
            data_rtu6 = reshaped_data_rtu[5]

            rtu1.write_bits(80, data_rtu1.tolist()) 
            rtu2.write_bits(80, data_rtu2.tolist()) 
            rtu3.write_bits(80, data_rtu3.tolist()) 
            rtu4.write_bits(80, data_rtu4.tolist()) 
            rtu5.write_bits(80, data_rtu5.tolist()) 
            rtu6.write_bits(80, data_rtu6.tolist()) 
        except:
            pass

    def reset_switching(self):
        try:
            data_rtu1 = np.zeros(36, dtype=int)
            data_rtu2 = np.zeros(36, dtype=int)
            data_rtu3 = np.zeros(36, dtype=int)
            data_rtu4 = np.zeros(36, dtype=int)
            data_rtu5 = np.zeros(36, dtype=int)
            data_rtu6 = np.zeros(36, dtype=int)

            rtu1.write_bits(80, data_rtu1.tolist()) 
            rtu2.write_bits(80, data_rtu2.tolist()) 
            rtu3.write_bits(80, data_rtu3.tolist()) 
            rtu4.write_bits(80, data_rtu4.tolist()) 
            rtu5.write_bits(80, data_rtu5.tolist()) 
            rtu6.write_bits(80, data_rtu6.tolist()) 
        except:
            pass

    def delayed_init(self, dt):
        self.ids.bt_shutdown.md_bg_color = "#A50000"
        layout = self.ids.layout_tables
        
        self.data_tables = MDDataTable(
            use_pagination=True,
            pagination_menu_pos="auto",
            rows_num=4,
            column_data=[
                ("No.", dp(10), self.sort_on_num),
                ("Volt [V]", dp(27)),
                ("Curr [mA]", dp(27)),
                ("Resi [kOhm]", dp(27)),
                ("Std Dev Res", dp(27)),
                ("IP (R decay)", dp(27)),
            ],
        )
        layout.add_widget(self.data_tables)

    def reset_data(self):
        global data_base
        global data_electrode
        global dt_measure
        global dt_current
        global dt_voltage
        global flag_run
        global ser

        if(not flag_run):        
            toast("resetting data")
            data_base = np.zeros([5, 0])
            data_electrode = np.zeros([4, 0], dtype=int)
            dt_measure = np.zeros(6)
            dt_current = np.zeros(10)
            dt_voltage = np.zeros(10)
            
            layout = self.ids.layout_tables
            
            self.data_tables = MDDataTable(
                use_pagination=True,
                pagination_menu_pos="auto",
                rows_num=4,
                column_data=[
                    ("No.", dp(10), self.sort_on_num),
                    ("Volt [V]", dp(27)),
                    ("Curr [mA]", dp(27)),
                    ("Resi [kOhm]", dp(27)),
                    ("Std Dev Res", dp(27)),
                    ("IP (R decay)", dp(27)),
                ],
            )
            layout.add_widget(self.data_tables)

        else:
            toast("cannot reset data while measuring")
        

    def sort_on_num(self, data):
        try:
            return zip(
                *sorted(
                    enumerate(data),
                    key=lambda l: l[0][0]
                )
            )
        except:
            toast("error sorting data")
            
    def save_data(self):
        global data_base
        global data_electrode
        global dt_distance
        global dt_config
        global data_pos
        global ser

        if(not flag_run):
            try:
                if("WENNER (ALPHA)" in dt_config):
                    mode = 1
                    
                elif("WENNER (BETA)" in dt_config):
                    mode = 1
                    
                elif("WENNER (GAMMA)" in dt_config):
                    mode = 1
                    
                elif("POLE-POLE" in dt_config):
                    mode = 2
                    
                elif("DIPOLE-DIPOLE" in dt_config):
                    mode = 3
                    
                elif("SCHLUMBERGER" in dt_config):
                    mode = 7
                    

                toast("saving data")

                x_loc = data_pos[0, :]
                # print(x_loc)

                data = data_base[2, :len(x_loc)]
                # print(data)

                spaces = data_pos[0, :] - data_pos[0, :-1]
                print(spaces)

                data_write = np.vstack((x_loc, spaces, data))
                if(data_write.size == 0):
                    data_write = np.array([[0,1,2,3]])
                print(data_write)

                now = datetime.now().strftime("/%d_%m_%Y_%H_%M_%S.dat")
                disk = str(DISK_ADDRESS) + now
                #disk = os.getcwd() + now
                head="%s \n%.2f \n%s \n%s \n0 \n1" % (now, dt_distance, mode, len(data_base.T[2]))
                foot="0 \n0 \n0 \n0 \n0"
                with open(disk,"wb") as f:
                    np.savetxt(f, data_write.T, fmt="%.3f", delimiter="\t", header=head, footer=foot, comments="")
                print("sucessfully save data to Dongle")
                toast("sucessfully save data to Dongle")
            except:
                try:
                    now = datetime.now().strftime("/%d_%m_%Y_%H_%M_%S.dat")
                    disk = os.getcwd() + now
                    head="%s \n%.2f \n%s \n%s \n0 \n1" % (now, dt_distance, mode, len(data_base.T[2]))
                    foot="0 \n0 \n0 \n0 \n0"
                    with open(disk,"wb") as f:
                        np.savetxt(f, data_write.T, fmt="%.3f", delimiter="\t", header=head, footer=foot, comments="")
                    print("sucessfully save data to Default Directory")
                    toast("sucessfully save data to Default Directory")
                except:
                    print("error saving data")
                    toast("error saving data")
                
        else:
            toast("cannot save data while measuring")

    def autosave_data(self):
        global data_base
        global data_electrode

        data_save = np.vstack((data_electrode, data_base))
        print(data_save.T)

        try:
            now = datetime.now().strftime("/%d_%m_%Y_%H_%M_%S.raw")
            disk = str(DISK_ADDRESS) + now
            with open(disk,"wb") as f:
                np.savetxt(f, data_save.T, fmt="%.3f",delimiter="\t",header="C1  \t P1  \t P2  \t C2  \t Volt [V] \t Curr [mA] \t Res [kOhm] \t StdDev \t IP [R decay]")
            print("sucessfully auto save data to Dongle")
            # toast("sucessfully save data")
        except:
            try:
                now = datetime.now().strftime("/%d_%m_%Y_%H_%M_%S.raw")
                cwd = os.getcwd()
                disk = cwd + now
                with open(disk,"wb") as f:
                    np.savetxt(f, data_save.T, fmt="%.3f",delimiter="\t",header="C1  \t P1  \t P2  \t C2  \t Volt [V] \t Curr [mA] \t Res [kOhm] \t StdDev \t IP [R decay]")
                print("sucessfully auto save data to Default Directory")
                # toast("sucessfully save data")
            except:
                print("error auto saving data")
                # toast("error saving data")

    def measure(self):
        global flag_run
        global ser
        if(flag_run):
            flag_run = False
        else:
            flag_run = True

    def screen_setting(self):
        self.screen_manager.current = 'screen_setting'

    def screen_data(self):
        self.screen_manager.current = 'screen_data'

    def screen_graph(self):
        self.screen_manager.current = 'screen_graph'

    def exec_shutdown(self):
        global flag_run

        if(not flag_run):        
            toast("shutting down system")
            os.system("shutdown /s /t 1") #for windows os
            # os.system("shutdown -h now")
        else:
            toast("cannot shutting down while measuring")

class ScreenGraph(BoxLayout):
    screen_manager = ObjectProperty(None)
    global flag_run
    global ser

    def __init__(self, **kwargs):
        super(ScreenGraph, self).__init__(**kwargs)
        Clock.schedule_once(self.delayed_init)
        Clock.schedule_interval(self.regular_check, 1)

    def regular_check(self, dt):
        global flag_run
        global flag_dongle
        global count_mounting
        global dt_time
        global data_base
        global flag_autosave_graph
        global graph_state
        global ser

        if(graph_state > 10):
            graph_state = 0

        if(flag_run):
            self.ids.bt_measure.text = "STOP MEASUREMENT"
            self.ids.bt_measure.md_bg_color = "#A50000"
            flag_autosave_graph = True
            if(graph_state == 0):
                self.update_graph()
            
        else:
            self.ids.bt_measure.text = "RUN MEASUREMENT"
            self.ids.bt_measure.md_bg_color = "#196BA5"
            if(flag_autosave_graph):
                self.autosave_graph()
                flag_autosave_graph = False

        graph_state += 1

        if not DISK_ADDRESS.exists() and flag_dongle:
            try:
                print("try mounting")
                serial_file = str(DISK_ADDRESS) + "/serial.key"
                # print(serial_file)
                with open(serial_file,"r") as f:
                    serial_number = f.readline()
                    if serial_number == SERIAL_NUMBER:
                        print("success, serial number is valid")
                        self.ids.bt_save_graph.disabled = False
                    else:
                        print("fail, serial number is invalid")
                        self.ids.bt_save_graph.disabled = True                    
            except:
                toast(f"Could not mount Dongle")
                self.ids.bt_save_graph.disabled = True
                count_mounting += 1
                if(count_mounting > 10):
                    flag_dongle = False 

    def update_graph(self):
        global flag_run
        global x_datum
        global y_datum
        global data_base
        global data_pos

        data_limit = len(data_base[2,:])
        visualized_data_pos = data_pos

        try:
            self.fig.set_facecolor("#eeeeee")
            self.fig.tight_layout()
            
            self.ax.set_xlabel("distance [m]", fontsize=10)
            self.ax.set_ylabel("n", fontsize=10)
            self.ax.set_facecolor("#eeeeee")

            # datum location
            max_data = np.max(data_base[2,:data_limit])
            cmap, norm = mcolors.from_levels_and_colors([0.0, max_data, max_data * 2],['green','red'])
            self.ax.scatter(visualized_data_pos[0,:data_limit], -visualized_data_pos[1,:data_limit], c=data_base[2,:data_limit], cmap=cmap, norm=norm, label=l_electrode[0], marker='o')
            # electrode location
            self.ids.layout_graph.clear_widgets()
            self.ids.layout_graph.add_widget(FigureCanvasKivyAgg(self.fig))

            # print("successfully show graphic")
        
        except:
            print("error show graphic")

        if(data_limit >= len(data_pos[0,:])):
            self.measure()

    def delayed_init(self, dt):
        self.ids.bt_shutdown.md_bg_color = "#A50000"
        self.fig, self.ax = plt.subplots()
        self.fig.set_facecolor("#eeeeee")
        self.fig.tight_layout()
        l, b, w, h = self.ax.get_position().bounds
        self.ax.set_position(pos=[l, b + 0.3*h, w, h*0.7])
        
        self.ax.set_xlabel("distance [m]", fontsize=10)
        self.ax.set_ylabel("n", fontsize=10)

        self.ids.layout_graph.add_widget(FigureCanvasKivyAgg(self.fig))        

    def measure(self):
        global flag_run
        if(flag_run):
            flag_run = False
        else:
            flag_run = True

    def reset_graph(self):
        global data_base
        global data_pos
        global flag_run

        if(not flag_run):        
            toast("resetting graph")
            data_base = np.zeros([5, 0])
            data_pos = np.zeros([2, 0])

            try:
                self.ids.layout_graph.clear_widgets()
                self.fig, self.ax = plt.subplots()
                self.fig.set_facecolor("#eeeeee")
                self.fig.tight_layout()
                l, b, w, h = self.ax.get_position().bounds
                self.ax.set_position(pos=[l, b + 0.3*h, w, h*0.7])
                
                self.ax.set_xlabel("distance [m]", fontsize=10)
                self.ax.set_ylabel("n", fontsize=10)

                self.ids.layout_graph.add_widget(FigureCanvasKivyAgg(self.fig))        
                print("successfully reset graphic")
            
            except:
                print("error reset graphic")

        else:
            toast("cannot reset graph while measuring")


    def save_graph(self):
        if(not flag_run):        
            toast("saving graph")
            try:
                now = datetime.now().strftime("/%d_%m_%Y_%H_%M_%S.jpg")
                disk = str(DISK_ADDRESS) + now
                self.fig.savefig(disk)
                print("sucessfully save graph to Dongle")
                toast("sucessfully save graph to Dongle")
            except:
                try:
                    now = datetime.now().strftime("/%d_%m_%Y_%H_%M_%S.jpg")
                    disk = os.getcwd() + now
                    self.fig.savefig(disk)
                    print("sucessfully save graph to Default Directory")
                    toast("sucessfully save graph to Default Directory")
                except:
                    print("error saving graph")
                    toast("error saving graph")
        else:
            toast("cannot save graph while measuring")

    def autosave_graph(self):
        try:
            now = datetime.now().strftime("/%d_%m_%Y_%H_%M_%S.jpg")
            disk = str(DISK_ADDRESS) + now
            self.fig.savefig(disk)
            print("sucessfully auto save graph to Dongle")
        except:
            try:
                now = datetime.now().strftime("/%d_%m_%Y_%H_%M_%S.jpg")
                disk = os.getcwd() + now
                self.fig.savefig(disk)
                print("sucessfully auto save graph to Default Directory")
            except:
                print("error auto saving graph")
                
    def screen_setting(self):
        self.screen_manager.current = 'screen_setting'

    def screen_data(self):
        self.screen_manager.current = 'screen_data'

    def screen_graph(self):
        self.screen_manager.current = 'screen_graph'

    def exec_shutdown(self):
        global flag_run

        if(not flag_run):        
            toast("shutting down system")
            os.system("shutdown /s /t 1") #for windows os
            # os.system("shutdown -h now")
        else:
            toast("cannot shutting down while measuring")


class ResistivityMeterApp(MDApp):
    def build(self):
        self.theme_cls.colors = colors
        self.theme_cls.primary_palette = "Blue"
        self.icon = "asset/logo_labtek_p.ico"
        Window.fullscreen = 'auto'
        Window.borderless = True
        # Window.size = 1024, 600
        Window.allow_screensaver = True

        screen = Builder.load_file("main.kv")

        return screen


if __name__ == "__main__":
    ResistivityMeterApp().run()
