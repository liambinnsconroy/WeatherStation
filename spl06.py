#!/usr/bin/python3

import os, glob, time
import smbus
import numpy as np
import psycopg2
import paho.mqtt.client as mqttClient

i2c_ch = 1

# SPL06-007 I2C address
i2c_address = 0x76

def get_c0(bus):
  tmp_MSB = bus.read_byte_data(i2c_address, 0x10)
  tmp_LSB = bus.read_byte_data(i2c_address, 0x11)

  tmp_LSB = tmp_LSB >> 4;
  tmp = tmp_MSB << 4 | tmp_LSB

  if (tmp & (1 << 11)):
    tmp = tmp | 0xF000

  return np.int16(tmp)

def get_c1(bus):
  tmp_MSB = bus.read_byte_data(i2c_address, 0x11)
  tmp_LSB = bus.read_byte_data(i2c_address, 0x12)

  tmp_LSB = bus.read_byte_data(i2c_address, 0xF)
  tmp = tmp_MSB << 8 | tmp_LSB

  if (tmp & (1 << 11)):
    tmp = tmp | 0xF000

  return np.int16(tmp)

def get_c00(bus):
  tmp_MSB = bus.read_byte_data(i2c_address, 0x13)
  tmp_LSB = bus.read_byte_data(i2c_address, 0x14)
  tmp_XLSB = bus.read_byte_data(i2c_address, 0x15)

  tmp = np.uint32(tmp_MSB << 12) | np.uint32(tmp_LSB << 4) | np.uint32(tmp_XLSB >> 4)

  if(tmp & (1 << 19)):
    tmp = tmp | 0XFFF00000
  
  return np.int32(tmp)

def get_c10(bus):
  tmp_MSB = bus.read_byte_data(i2c_address, 0x15)
  tmp_LSB = bus.read_byte_data(i2c_address, 0x16)
  tmp_XLSB = bus.read_byte_data(i2c_address, 0x17)

  tmp_MSB = tmp_MSB & 0xF

  #tmp = tmp_MSB << 8 | tmp_LSB
  #tmp = tmp << 8
  tmp = np.uint32(tmp_MSB << 16) | np.uint32(tmp_LSB << 8) | np.uint32(tmp_XLSB)

  if(tmp & (1 << 19)):
    tmp = tmp | 0XFFF00000

  return np.int32(tmp)

def get_c01(bus):
  tmp_MSB = bus.read_byte_data(i2c_address, 0x18)
  tmp_LSB = bus.read_byte_data(i2c_address, 0x19)

  tmp = (tmp_MSB << 8) | tmp_LSB

  return np.int16(tmp)

def get_c11(bus):
  tmp_MSB = bus.read_byte_data(i2c_address, 0x1A)
  tmp_LSB = bus.read_byte_data(i2c_address, 0x1B)

  tmp = (tmp_MSB << 8) | tmp_LSB

  return np.int16(tmp)

def get_c20(bus):
  tmp_MSB = bus.read_byte_data(i2c_address, 0x1C)
  tmp_LSB = bus.read_byte_data(i2c_address, 0x1D)

  tmp = (tmp_MSB << 8) | tmp_LSB

  return np.int16(tmp)

def get_c21(bus):
  tmp_MSB = bus.read_byte_data(i2c_address, 0x1E)
  tmp_LSB = bus.read_byte_data(i2c_address, 0x1F)

  tmp = (tmp_MSB << 8) | tmp_LSB

  return np.int16(tmp)

def get_c30(bus):
  tmp_MSB = bus.read_byte_data(i2c_address, 0x20)
  tmp_LSB = bus.read_byte_data(i2c_address, 0x21)

  tmp = (tmp_MSB << 8) | tmp_LSB

  return np.int16(tmp)

def get_traw(bus):
  tmp_MSB = bus.read_byte_data(i2c_address, 0x03)
  tmp_LSB = bus.read_byte_data(i2c_address, 0x04)
  tmp_XLSB = bus.read_byte_data(i2c_address, 0x05)

  tmp = np.uint32(tmp_MSB << 16) | np.uint32(tmp_LSB << 8) | np.uint32(tmp_XLSB)

  if(tmp & (1 << 23)):
    tmp = tmp | 0XFF000000

  return np.int32(tmp)

def get_temperature_scale_factor(bus):
  tmp_Byte = bus.read_byte_data(i2c_address, 0x07)

  tmp_Byte = tmp_Byte & 0B111

  if(tmp_Byte == 0B000):
    k = 524288.0

  if(tmp_Byte == 0B001):
    k = 1572864.0

  if(tmp_Byte == 0B010):
    k = 3670016.0

  if(tmp_Byte == 0B011):
    k = 7864320.0

  if(tmp_Byte == 0B100):
    k = 253952.0

  if(tmp_Byte == 0B101):
    k = 516096.0

  if(tmp_Byte == 0B110):
    k = 1040384.0

  if(tmp_Byte == 0B111):
    k = 2088960.0 

  return k

def get_praw(bus):
  tmp_MSB = bus.read_byte_data(i2c_address, 0x00)
  tmp_LSB = bus.read_byte_data(i2c_address, 0x01)
  tmp_XLSB = bus.read_byte_data(i2c_address, 0x02)

  tmp = np.uint32(tmp_MSB << 16) | np.uint32(tmp_LSB << 8) | np.uint32(tmp_XLSB)

  if(tmp & (1 << 23)):
    tmp = tmp | 0XFF000000

  return np.int32(tmp)


def get_pressure_scale_factor(bus):
  tmp_Byte = bus.read_byte_data(i2c_address, 0x06)

  tmp_Byte = tmp_Byte & 0B111

  if(tmp_Byte == 0B000):
    k = 524288.0

  if(tmp_Byte == 0B001):
    k = 1572864.0

  if(tmp_Byte == 0B010):
    k = 3670016.0

  if(tmp_Byte == 0B011):
    k = 7864320.0

  if(tmp_Byte == 0B100):
    k = 253952.0

  if(tmp_Byte == 0B101):
    k = 516096.0

  if(tmp_Byte == 0B110):
    k = 1040384.0

  if(tmp_Byte == 0B111):
    k = 2088960.0

  return k

def get_pressure(bus):

  # Set pressure configuration register
  bus.write_byte_data(i2c_address, 0x06, 0x03) # pressure 8x oversampling

  # Set temperature configuration register
  bus.write_byte_data(i2c_address, 0x07, 0x83) # temperature 8x oversampling

  # Set measurement register
  bus.write_byte_data(i2c_address, 0x08, 0x07)

  # Set configuration register
  bus.write_byte_data(i2c_address, 0x09, 0x00)

  c00 = get_c00(bus)
  c10 = get_c10(bus)
  c01 = get_c01(bus)
  c11 = get_c11(bus)
  c20 = get_c20(bus)
  c21 = get_c21(bus)
  c30 = get_c30(bus)
  traw = get_traw(bus)

  t_scale = get_temperature_scale_factor(bus)

  traw_sc = traw / t_scale

  praw = get_praw(bus)

  p_scale = get_pressure_scale_factor(bus)

  praw_sc = praw / p_scale

  pressure = c00+ praw_sc*(c10+ praw_sc*(c20+ praw_sc*c30)) + traw_sc*c01 + traw_sc*praw_sc*(c11+praw_sc*c21)
  return pressure/100
