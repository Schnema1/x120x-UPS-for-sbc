#!/usr/bin/python3

import os
import struct
import smbus2
import time
import logging
import subprocess
import gpiod
from subprocess import call

# User-configurable variables
SHUTDOWN_THRESHOLD = 3  # Number of consecutive failures required for shutdown
SLEEP_TIME = 60  # Time in seconds to wait between failure checks
Loop = False

# Charging control variables
MAX_CHARGE_VOLTAGE = 4.10  # Maximum charging voltage (V)
CHARGE_RESUME_VOLTAGE = 3.95  # Resume charging below this voltage (V)
CHARGE_CONTROL_PIN = 16  # GPIO pin to control charging (per Suptronics X120X manual)
CHARGE_ENABLE_STATE = 1  # GPIO state to enable charging (1 = high, 0 = low)

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def readVoltage(bus):
    """Read battery voltage from MAX17040/MAX17041"""
    try:
        read = bus.read_word_data(address, 2)  # VCELL register
        swapped = struct.unpack("<H", struct.pack(">H", read))[0]  # big endian to little endian
        voltage = swapped * 1.25 / 1000 / 16  # convert to voltage (MAX17040: 1.25mV resolution)
        return voltage
    except Exception as e:
        logger.error(f"Error reading voltage: {e}")
        return None

def readCapacity(bus):
    """Read battery capacity from MAX17040/MAX17041"""
    try:
        read = bus.read_word_data(address, 4)  # SOC register
        swapped = struct.unpack("<H", struct.pack(">H", read))[0]  # big endian to little endian
        capacity = swapped / 256  # convert to 1-100% scale
        return capacity
    except Exception as e:
        logger.error(f"Error reading capacity: {e}")
        return None

def readRawVoltage(bus):
    """Read raw voltage register value for debugging"""
    try:
        read = bus.read_word_data(address, 2)
        return read
    except Exception as e:
        logger.error(f"Error reading raw voltage: {e}")
        return None

def get_battery_status(voltage):
    """Determine battery status based on voltage"""
    if voltage is None:
        return "Unknown"
    elif 3.87 <= voltage <= 4.2:
        return "Full"
    elif 3.7 <= voltage < 3.87:
        return "High"
    elif 3.55 <= voltage < 3.7:
        return "Medium"
    elif 3.4 <= voltage < 3.55:
        return "Low"
    elif voltage < 3.4:
        return "Critical"
    else:
        return "Unknown"

def control_charging(charge_line, voltage, current_charge_state):
    """Control charging based on voltage thresholds"""
    if voltage is None:
        logger.warning("Cannot control charging - voltage reading failed")
        return current_charge_state
    
    try:
        if voltage >= MAX_CHARGE_VOLTAGE and current_charge_state:
            # Stop charging if voltage too high
            charge_line.set_value(1 - CHARGE_ENABLE_STATE)  # Disable charging
            logger.info(f"CHARGING STOPPED - Voltage {voltage:.3f}V >= {MAX_CHARGE_VOLTAGE}V")
            return False
        elif voltage <= CHARGE_RESUME_VOLTAGE and not current_charge_state:
            # Resume charging if voltage dropped sufficiently
            charge_line.set_value(CHARGE_ENABLE_STATE)  # Enable charging
            logger.info(f"CHARGING RESUMED - Voltage {voltage:.3f}V <= {CHARGE_RESUME_VOLTAGE}V")
            return True
        else:
            # No change needed
            return current_charge_state
    except Exception as e:
        logger.error(f"Error controlling charging: {e}")
        return current_charge_state

def quick_start_fuel_gauge(bus):
    """Perform quick start on fuel gauge for better initial readings"""
    try:
        bus.write_word_data(address, 6, 0x4000)  # MODE register quick-start command
        logger.info("Fuel gauge quick-start initiated")
        time.sleep(1)  # Wait for quick-start to complete
    except Exception as e:
        logger.error(f"Error performing quick-start: {e}")

# Ensure only one instance of the script is running
pid = str(os.getpid())
pidfile = "/var/run/X1200.pid"
if os.path.isfile(pidfile):
    print("Script already running")
    exit(1)
else:
    with open(pidfile, 'w') as f:
        f.write(pid)

# Initialize variables
charging_enabled = True  # Assume charging starts enabled
bus = None
chip = None
pld_line = None
charge_line = None

try:
    # Initialize I2C bus
    bus = smbus2.SMBus(1)
    address = 0x36
    
    # Initialize GPIO
    PLD_PIN = 6
    chip = gpiod.Chip('gpiochip0')
    
    # Power loss detection pin
    pld_line = chip.get_line(PLD_PIN)
    pld_line.request(consumer="PLD", type=gpiod.LINE_REQ_DIR_IN)
    
    # Charging control pin
    try:
        charge_line = chip.get_line(CHARGE_CONTROL_PIN)
        charge_line.request(consumer="CHARGE_CTRL", type=gpiod.LINE_REQ_DIR_OUT)
        charge_line.set_value(CHARGE_ENABLE_STATE)  # Start with charging enabled
        logger.info(f"Charging control initialized on GPIO {CHARGE_CONTROL_PIN}")
    except Exception as e:
        logger.warning(f"Could not initialize charging control on GPIO {CHARGE_CONTROL_PIN}: {e}")
        logger.warning("Continuing without charging control")
        charge_line = None
    
    # Perform initial fuel gauge quick-start for better accuracy
    quick_start_fuel_gauge(bus)
    
    logger.info("UPS monitoring started")
    logger.info(f"Charging control: Max voltage {MAX_CHARGE_VOLTAGE}V, Resume voltage {CHARGE_RESUME_VOLTAGE}V")
    
    while True:
        failure_counter = 0

        for _ in range(SHUTDOWN_THRESHOLD):
            # Read sensor values
            ac_power_state = pld_line.get_value()
            voltage = readVoltage(bus)
            capacity = readCapacity(bus)
            battery_status = get_battery_status(voltage)
            
            # Control charging if charge control is available
            if charge_line is not None:
                charging_enabled = control_charging(charge_line, voltage, charging_enabled)
            
            # Display status
            voltage_str = f"{voltage:.3f}V" if voltage is not None else "N/A"
            capacity_str = f"{capacity:.2f}%" if capacity is not None else "N/A"
            charge_status = "Enabled" if charging_enabled else "Disabled"
            
            print(f"Capacity: {capacity_str} ({battery_status}), "
                  f"AC Power: {'Plugged in' if ac_power_state == 1 else 'Unplugged'}, "
                  f"Voltage: {voltage_str}, "
                  f"Charging: {charge_status}")
            
            # Check for critical conditions
            if ac_power_state == 0:
                logger.warning("UPS is unplugged or AC power loss detected.")
                failure_counter += 1
                
                if capacity is not None and capacity < 20:
                    logger.warning("Battery level critical.")
                    failure_counter += 1
                    
                if voltage is not None and voltage < 3.20:
                    logger.warning("Battery voltage critical.")
                    failure_counter += 1
            else:
                failure_counter = 0
                break

            if failure_counter < SHUTDOWN_THRESHOLD:
                time.sleep(SLEEP_TIME)

        # Handle shutdown conditions
        if failure_counter >= SHUTDOWN_THRESHOLD:
            shutdown_reason = ""
            if capacity is not None and capacity < 20:
                shutdown_reason = "due to critical battery level."
            elif voltage is not None and voltage < 3.20:
                shutdown_reason = "due to critical battery voltage."
            elif ac_power_state == 0:
                shutdown_reason = "due to AC power loss or UPS unplugged."

            shutdown_message = f"Critical condition met {shutdown_reason} Initiating shutdown."
            logger.critical(shutdown_message)
            print(shutdown_message)
            
            # Disable charging before shutdown
            if charge_line is not None:
                try:
                    charge_line.set_value(1 - CHARGE_ENABLE_STATE)
                    logger.info("Charging disabled before shutdown")
                except Exception as e:
                    logger.error(f"Error disabling charging before shutdown: {e}")
            
            call("sudo nohup shutdown -h now", shell=True)
        else:
            if Loop:
                time.sleep(SLEEP_TIME)
            else:
                logger.info("Single check completed, exiting")
                break

except KeyboardInterrupt:
    logger.info("Script interrupted by user")
except Exception as e:
    logger.error(f"Unexpected error: {e}")
finally:
    # Cleanup
    if charge_line is not None:
        try:
            charge_line.release()
        except:
            pass
    if pld_line is not None:
        try:
            pld_line.release()
        except:
            pass
    if chip is not None:
        try:
            chip.close()
        except:
            pass
    if os.path.isfile(pidfile):
        os.unlink(pidfile)
    
    logger.info("UPS monitoring stopped")
    exit(0)