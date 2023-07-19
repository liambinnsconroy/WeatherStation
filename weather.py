#!/usr/bin/python3
import os, glob, time, psycopg2
import paho.mqtt.client as mqttClient
import time
from ds18b20 import DS18B20
from spl06 import get_pressure
import smbus
import board
import dht11
import psutil
import RPi.GPIO as GPIO

#sound_history = []

# mqtt vars
Connected = False   #global variable for the state of the connection
broker_address= "192.168.68.63"
port = 1883
temp_topic = "python/temp"
pressure_topic = "python/pressure"
humidity_topic = "python/humidity"
sound_topic = "python/sound"

class Sensors:
    def __init__(self, temp, pressure, humidity):
        self.temp = temp
        self.pressure = pressure
        self.humidity = humidity
        self.sound_count = 0
        self.sound_history = [99,99,99,99,99]

    
    # calculates the average of the values in sound_history
    def sound_average(self):
        if len(self.sound_history) == 0:
            return 99
        s = 0
        for i in self.sound_history:
            s += i
        return s/len(self.sound_history)



def on_connect(client, userdata, flags, rc):
    if rc == 0:
        #print("Connected to broker")
        global Connected
        Connected = True
 
    else:
        print("Connection failed")

def connect_mqtt():
    client = mqttClient.Client("Python")
    client.on_connect = on_connect
    client.connect(broker_address, port=port)
    client.loop_start()

    while Connected != True:
        time.sleep(0.1)
    return client

def get_humidity(humidity_sensor):

    # The humidity sensor is a bit flakey, retry up to 3 times
    count = 0
    while True:
        if count < 3:
            count +=1

            readings = humidity_sensor.read()

            if readings.is_valid():
                print("humidity: {}".format(readings.humidity))
                return readings.humidity
            else:
                print("humidity result was bad, trying again")
                time.sleep(0.2)

        else:
            break
    return None

# a callback function for the sound sensor to increment the global count var
def sound_callback(channel, sensors):
    sensors.sound_count += 1
    time.sleep(0.05)

def setup_sensors():

    temp_sensor = DS18B20()
    pressure_sensor = smbus.SMBus(1)
    humidity_sensor = dht11.DHT11(pin=23)

    sensors = Sensors(temp_sensor, pressure_sensor, humidity_sensor)
    
    # sound sensor setup (pin 17)
    channel = 17
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(channel, GPIO.IN)
    
    # sound sensor callbacks
    GPIO.add_event_detect(channel, GPIO.BOTH, bouncetime=300)  # let us know when the pin goes HIGH or LOW
    GPIO.add_event_callback(channel, callback=lambda channel: sound_callback(channel, sensors))  # assign function to GPIO PIN, Run function on change

    return sensors


if __name__ == "__main__":

    # Give time on startup for the db + mqtt broker to come alive
    print("sleeping for 60 seconds to ensure postgres and mqtt broker is alive")
    time.sleep(60)

    # connect to db + mqtt
    client = connect_mqtt()
    conn = psycopg2.connect("dbname=postgres user=postgres password=postgres")
    cur = conn.cursor()

    # setup sensors
    sensors = setup_sensors()


    while True:

        # read sensor values
        temp = sensors.temp.read_temp()
        pressure = get_pressure(sensors.pressure)
        humidity = get_humidity(sensors.humidity)
 
        t = time.localtime()
        
        # insert temp, pressure and sound count into db
        cur.execute("INSERT INTO weather.temperature (timestamp, value) VALUES (%s, %s)", (time.strftime("%Y-%m-%d %H:%M:%S"), temp))
        cur.execute("INSERT INTO weather.pressure (timestamp, value) VALUES (%s, %s)", (time.strftime("%Y-%m-%d %H:%M:%S"), pressure))
        cur.execute("INSERT INTO weather.sound (timestamp, value) VALUES (%s, %s)", (time.strftime("%Y-%m-%d %H:%M:%S"), sensors.sound_count))
            
        # publish the temp and pressure values to mqtt 
        client.publish(temp_topic, temp)
        client.publish(pressure_topic, pressure)

        # sometimes the sound sensor records incorrectly high measurements
        # we only log to mqtt if the value was less than 3 times the average 
        # of the past 5 measurements
        if sensors.sound_count < (sensors.sound_average()) * 3:
            client.publish(sound_topic, sensors.sound_count)
            print("sound count: {}".format(sensors.sound_count))

            sensors.sound_history.append(sensors.sound_count)
            if len(sensors.sound_history) > 5:
                sensors.sound_history.pop(0)

        else:
            print("sound was too high")
            print("sound: {}, average: {}".format(sensors.sound_count, sensors.sound_average()))

        print("temp: {}".format(temp))             
        print("pressure: {}".format(pressure))


        # the humidity sensor is flakey, check there's a value before sending data
        if humidity != None:
            cur.execute("INSERT INTO weather.humidity (timestamp, value) VALUES (%s, %s)", (time.strftime("%Y-%m-%d %H:%M:%S"), humidity))
            client.publish(humidity_topic, humidity)
                
        conn.commit()
        sensors.sound_count = 0

        time.sleep(60)
  
        # close the file and the db connection    
    cur.close()
    conn.close()
