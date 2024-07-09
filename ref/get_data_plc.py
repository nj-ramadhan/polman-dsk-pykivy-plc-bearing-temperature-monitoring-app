from scipy.signal import find_peaks
import numpy as np
import os
import snap7
import numpy as np
import locale
import time

locale.setlocale(locale.LC_TIME, "id_ID")

DEBUG = False

TEMP_OFFSET = 2.5412
TEMP_GAIN = 5.0 * 1000.0 #channge from A to mA with gain

BEARING_TEMP_DATA = 100
NUMBER_OF_BEARINGS = 100

BEARING_TEMP_MIN = 42.5

# Define constants for PLC connection and database read
PLC_IP = '192.168.0.2'
RACK = 0
SLOT = 1
DB_NUMBER = 3

DB_OFFSET_COUNTER = 0
DB_OFFSET_TRAIN_NAME = 2
DB_OFFSET_TRAIN_TYPE = 260
DB_OFFSET_TRAIN_SPEED = 534

DB_OFFSET_SENSOR = 532
DB_OFFSET_DIR = 538

DB_OFFSET_TEMPERATURE_L = 562
DB_OFFSET_TEMPERATURE_R = 962

DB_OFFSET_TEMPERATURE_BEARING = [1362, 1762, 2162, 2562, 2962, 3362, 3762, 4162, 4562, 4962,
                                 5362, 5762, 6162, 6562, 6962, 7362, 7762, 8162, 8562, 8962,
                                 9362, 9762, 10162, 10562, 10962, 11362, 11762, 12162, 12562, 12962,
                                 13362, 13762, 14162, 14562, 14962, 15362, 15762, 16162, 16562, 16962,
                                 17362, 1762, 18162, 18562, 18962, 19362, 19762, 20162, 20562, 20962, 
                                 ]

BYTES_TO_READ_S = 8
BYTES_TO_READ_M = 64
BYTES_TO_READ_L = 400

DELAY_BEFORE_READING_PLC = 7
INTERVAL_DURATION_DATA = 0.05  # seconds
INTERVAL_DURATION_UPDATE_TABLE = 0.5
INTERVAL_DURATION_UPDATE_DISPLAY = 1.0
REQUEST_TIME_OUT = 5.0

arr_bearing_temps_left_to_right = np.zeros(100)
arr_bearing_temps_right_to_left = np.zeros(100)

db_bearing_temps = np.zeros([100, 100]) # database set of bearing temperature raw value, array 100 x 100
arr_bearing_temps = np.zeros(100) # data array of bearing temperature raw value in a wheel, array 1 x 100
arr_calc_bearing_temps = np.zeros(200) # data array of calculated bearing temperature, array 1 x 100
calc_bearing_temps = 0.0 # data value of calculated bearing temperature

dir_left_to_right = False
dir_right_to_left = False
prev_dir_left_to_right = False
prev_dir_right_to_left = False

read_sensor_left_to_right = False
read_sensor_right_to_left = False

counting_wheel = 0
prev_counting_wheel = 0
counting_wheel_max = 0

train_name = ""
train_type = ""
train_speed = 0.0

flag_autosave_data = False
flag_autosave_graph = False
graph_state = 0

def connect_to_plc():
    global plc

    plc = snap7.client.Client()
    plc.connect(PLC_IP, RACK, SLOT)
    return plc

def read_plc():
    global plc
    global arr_bearing_temps, arr_bearing_temps_left_to_right, arr_bearing_temps_right_to_left
    global dir_left_to_right, dir_right_to_left
    global prev_dir_left_to_right, prev_dir_right_to_left
    global read_sensor_left_to_right, read_sensor_right_to_left
    global counting_wheel, prev_counting_wheel, counting_wheel_max
    global train_name, train_type, train_speed

    try:
        DB_bytearray = plc.db_read(DB_NUMBER,DB_OFFSET_TRAIN_NAME,BYTES_TO_READ_M)
        train_name = snap7.util.get_string(DB_bytearray, 0)

        DB_bytearray = plc.db_read(DB_NUMBER,DB_OFFSET_TRAIN_TYPE,BYTES_TO_READ_M)
        train_type = snap7.util.get_string(DB_bytearray, 0)

        DB_bytearray = plc.db_read(DB_NUMBER,DB_OFFSET_TRAIN_SPEED,BYTES_TO_READ_S)
        train_speed = snap7.util.get_real(DB_bytearray, 0)

        DB_bytearray = plc.db_read(DB_NUMBER,DB_OFFSET_DIR,BYTES_TO_READ_S)
        dir_right_to_left = snap7.util.get_bool(DB_bytearray, 0, 0)
        dir_left_to_right = snap7.util.get_bool(DB_bytearray, 0, 1)

        DB_bytearray = plc.db_read(DB_NUMBER,DB_OFFSET_SENSOR,BYTES_TO_READ_S)
        read_sensor_right_to_left = snap7.util.get_bool(DB_bytearray, 0, 0)
        read_sensor_left_to_right = snap7.util.get_bool(DB_bytearray, 0, 1)
        
        DB_bytearray = plc.db_read(DB_NUMBER,DB_OFFSET_COUNTER,BYTES_TO_READ_S)
        counting_wheel_max = snap7.util.get_int(DB_bytearray, 0)

        # print("dir left:", dir_left_to_right, "dir right:" ,  dir_right_to_left, "sens A:", read_sensor_left_to_right, "sens B:" , read_sensor_right_to_left)
        # print(counting_wheel)
        DB_bytearray = plc.db_read(DB_NUMBER,DB_OFFSET_TEMPERATURE_BEARING[counting_wheel],BYTES_TO_READ_L)
        print(DB_bytearray)

        for i in range(0, 49):
            arr_bearing_temps[i] = snap7.util.get_real(DB_bytearray, i * 4)
        
        # # if (dir_left_to_right):
        # if (dir_left_to_right == True):
        #     for i in range(0, 49):
        #         arr_bearing_temps_left_to_right[i] = snap7.util.get_real(DB_bytearray, i * 4)
                
        #     arr_bearing_temps = arr_bearing_temps_left_to_right

        # # if (dir_right_to_left):
        # if (dir_right_to_left == True):                
        #     for i in range(0, 49):
        #         arr_bearing_temps_right_to_left[i] = snap7.util.get_real(DB_bytearray, i * 4)

        #     arr_bearing_temps = arr_bearing_temps_right_to_left
        
        db_bearing_temps[counting_wheel] = arr_bearing_temps
        print(counting_wheel)
        print(DB_OFFSET_TEMPERATURE_BEARING[counting_wheel])
        print(db_bearing_temps)

        prev_dir_right_to_left = dir_right_to_left
        prev_dir_left_to_right = dir_left_to_right
        prev_counting_wheel = counting_wheel
        
    except RuntimeError as e:
        print("PLC is disconnected")

def finding_bearings(counting_wheel):
    global db_bearing_temps
    global arr_bearing_temps
    global calc_bearing_temps
    global arr_calc_bearing_temps  

    arr_bearing_temps = db_bearing_temps[counting_wheel][db_bearing_temps[counting_wheel] != np.array(None)]
    arr_bearing_trimmed = np.trim_zeros(arr_bearing_temps)
    peaks, _ = find_peaks(arr_bearing_temps, height = BEARING_TEMP_MIN)

    if arr_bearing_trimmed.size != 0:
        middle_value = np.take(arr_bearing_trimmed, arr_bearing_trimmed.size // 2)
        
    # print(middle_value)
    if arr_bearing_temps[peaks].size == 0:
            calc_bearing_temps = np.max(arr_bearing_trimmed)
    else:
        if middle_value <= arr_bearing_trimmed[0]:
            calc_bearing_temps = middle_value
        else:
            calc_bearing_temps = np.max(arr_bearing_temps[peaks])
            
    print(f"Calculated Bearing Temperature is {calc_bearing_temps}")

while(1):
    time.sleep(1)
    
    try:
        connect_to_plc()
        read_plc()
        counting_wheel +=1
    except Exception as e:
        print(e)

