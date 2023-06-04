#!/usr/bin/python3
import os, glob, time, psycopg2
import paho.mqtt.client as mqttClient
import time
from ds18b20 import DS18B20
from spl06 import get_pressure
import smbus
import board
import adafruit_dht
import psutil
import RPi.GPIO as GPIO


#GPIO SETUP
channel = 17
GPIO.setmode(GPIO.BCM)
GPIO.setup(channel, GPIO.IN)
count = 0

# mqtt vars
Connected = False   #global variable for the state of the connection
broker_address= "192.168.68.63"
port = 1883
temp_topic = "python/temp"
pressure_topic = "python/pressure"
humidity_topic = "python/humidity"
sound_topic = "python/sound"

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

def kill_libgpiod():
    for proc in psutil.process_iter():
        if proc.name() == 'libgpiod_pulsein' or proc.name() == 'libgpiod_pulsei':
            proc.kill()

def get_humidity(humidity_sensor):
    #while True:
    try:
        humidity = humidity_sensor.humidity
        print("humidity: {}".format(humidity))
        return humidity
    except RuntimeError as error:
        print(error.args[0])

def sound_callback(channel):
    global count
    count += 1
    sleep(0.1)

GPIO.add_event_detect(channel, GPIO.BOTH, bouncetime=300)  # let us know when the pin goes HIGH or LOW
GPIO.add_event_callback(channel, sound_callback)  # assign function to GPIO PIN, Run function on change

if __name__ == "__main__":

    # Give time on startup for the db + mqtt broker to come alive
    print("sleeping for 60 seconds to ensure postgres and mqtt broker is alive")
    time.sleep(60)
    # connect to db + mqtt
    client = connect_mqtt()
    conn = psycopg2.connect("dbname=postgres user=postgres password=postgres")
    cur = conn.cursor()

    temp_sensor = DS18B20()
    pressure_sensor = smbus.SMBus(1)
    humidity_sensor = adafruit_dht.DHT11(board.D23)
    
    try:
        while True:
            try:

                temp = temp_sensor.read_temp()
                pressure = get_pressure(pressure_sensor)
                humidity = get_humidity(humidity_sensor)
            
                t = time.localtime()
        
                cur.execute("INSERT INTO weather.temperature (timestamp, value) VALUES (%s, %s)", (time.strftime("%Y-%m-%d %H:%M:%S"), temp))
                cur.execute("INSERT INTO weather.pressure (timestamp, value) VALUES (%s, %s)", (time.strftime("%Y-%m-%d %H:%M:%S"), pressure))
               
                cur.execute("INSERT INTO weather.sound (timestamp, value) VALUES (%s, %s)", (time.strftime("%Y-%m-%d %H:%M:%S"), count))

                print("temp: {}".format(temp))             
                print("pressure: {}".format(pressure))
                print("sound count: {}".format(count))

                client.publish(temp_topic, temp)
                client.publish(pressure_topic, pressure)
                client.publish(sound_topic, count)

                if humidity != None:
                     
                    cur.execute("INSERT INTO weather.humidity (timestamp, value) VALUES (%s, %s)", (time.strftime("%Y-%m-%d %H:%M:%S"), humidity))
                
                    client.publish(humidity_topic, humidity)
                
                conn.commit()
                count = 0
                
                time.sleep(60)
            except RuntimeError as error:
                print(error.args[0])
                time.sleep(5)
                continue
  
    except KeyboardInterupt:
        client.disconnect()
        client.loop_stop()

        # close the file and the db connection    
        cur.close()
        conn.close()
