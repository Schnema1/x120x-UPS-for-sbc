#!/usr/bin/python3

import struct
import smbus2
import time
import logging
import gpiod
from subprocess import call, check_output, CalledProcessError
from pathlib import Path

# User-configurable variables
SHUTDOWN_THRESHOLD = 3  # Number of consecutive failures required for shutdown
SLEEP_TIME = 60  # Time in seconds to wait between failure checks
Loop = True  # Always loop for systemd service

# Critical thresholds for shutdown
CRITICAL_VOLTAGE_THRESHOLD = 3.2  # Critical voltage threshold for shutdown (V)
CRITICAL_CAPACITY_THRESHOLD = 20  # Critical capacity threshold for shutdown (%)

# Charging control variables
MAX_CHARGE_VOLTAGE = 4.10  # Maximum charging voltage (V)
CHARGE_RESUME_VOLTAGE = 3.89  # Resume charging below this voltage (V)
CHARGE_CONTROL_PIN = 16  # GPIO pin to control charging (per Suptronics X120X manual)
CHARGE_ENABLE_STATE = 0  # GPIO state to enable charging 1 = disable (high), 0 = enable (low)

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def readVoltage(bus, address):
    """Read battery voltage from MAX17040/MAX17041"""
    try:
        read = bus.read_word_data(address, 2)  # VCELL register
        swapped = struct.unpack("<H", struct.pack(">H", read))[0]  # big endian to little endian
        voltage = swapped * 1.25 / 1000 / 16  # convert to voltage (MAX17040: 1.25mV resolution)
        #logger.debug(f"Raw voltage data: {read}, Swapped: {swapped}, Calculated Voltage: {voltage}")
        return voltage
    except Exception as e:
        logger.error(f"Error reading voltage: {e}")
        return None

def readCapacity(bus, address):
    """Read battery capacity from MAX17040/MAX17041"""
    try:
        read = bus.read_word_data(address, 4)  # SOC register
        swapped = struct.unpack("<H", struct.pack(">H", read))[0]  # big endian to little endian
        capacity = swapped / 256  # convert to 1-100% scale
        return capacity
    except Exception as e:
        logger.error(f"Error reading capacity: {e}")
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

def read_hardware_metric(command_args, strip_chars):
    """Read hardware metrics using vcgencmd"""
    try:
        output = check_output(command_args).decode("utf-8")
        metric_str = output.split("=")[1].strip().rstrip(strip_chars)
        return float(metric_str)
    except (CalledProcessError, ValueError, IndexError) as e:
        logger.error(f"Error reading hardware metric: {e}")
        return None

def read_cpu_volts():
    return read_hardware_metric(["vcgencmd", "pmic_read_adc", "VDD_CORE_V"], 'V')

def read_cpu_amps():
    return read_hardware_metric(["vcgencmd", "pmic_read_adc", "VDD_CORE_A"], 'A')

def read_cpu_temp():
    return read_hardware_metric(["vcgencmd", "measure_temp"], "'C")

def read_input_voltage():
    return read_hardware_metric(["vcgencmd", "pmic_read_adc", "EXT5V_V"], 'V')

def get_fan_rpm():
    try:
        sys_devices_path = Path('/sys/devices/platform/cooling_fan') 
        fan_input_files = list(sys_devices_path.rglob('fan1_input'))
        if not fan_input_files:
            return "No fan detected"
        with open(fan_input_files[0], 'r') as file:
            rpm = file.read().strip()
        return f"{rpm} RPM"
    except FileNotFoundError: 
        return "Fan RPM file not found"
    except PermissionError:
        return "Permission denied accessing fan RPM"
    except Exception as e:
        return f"Fan error: {e}"

def power_consumption_watts():
    try:
        output = check_output(['vcgencmd', 'pmic_read_adc']).decode("utf-8")
        lines = output.split('\n')
        amperages = {}
        voltages = {}
        for line in lines:
            cleaned_line = line.strip()
            if cleaned_line:
                parts = cleaned_line.split(' ')
                label, value = parts[0], parts[-1]
                val = float(value.split('=')[1][:-1])
                short_label = label[:-2]
                if label.endswith('A'):
                    amperages[short_label] = val
                else:
                    voltages[short_label] = val
        wattage = sum(amperages[key] * voltages[key] for key in amperages if key in voltages)
        return wattage
    except Exception as e:
        logger.error(f"Error calculating power consumption: {e}")
        return None

def log_system_stats(voltage, capacity, charging_enabled, ac_power_state):
    cpu_volts = read_cpu_volts()
    cpu_amps = read_cpu_amps()
    cpu_temp = read_cpu_temp()
    input_voltage = read_input_voltage()
    fan_rpm = get_fan_rpm()
    pwr_use = power_consumption_watts()
    charge_status = "enabled" if charging_enabled else "disabled"
    if ac_power_state == 1:
        power_status = "AC Power: OK! Power Adapter: OK!"
    else:
        power_status = "Power Loss OR Power Adapter Failure"
    logger.info(f"UPS Voltage: {voltage if voltage else 'N/A'} V, Battery: {capacity if capacity else 'N/A'} %, Charging: {charge_status}, Input Voltage: {input_voltage if input_voltage else 'N/A'} V, CPU Volts: {cpu_volts if cpu_volts else 'N/A'} V, CPU Amps: {cpu_amps if cpu_amps else 'N/A'} A, System Watts: {pwr_use if pwr_use else 'N/A'} W, CPU Temp: {cpu_temp if cpu_temp else 'N/A'} C, Fan RPM: {fan_rpm}, Power Status: {power_status}")
    if ac_power_state != 1 and capacity:
        if capacity >= 51:
            logger.warning(f"Running on UPS Backup Power - Batteries @ {capacity:.2f}% - Voltage @ {voltage if voltage else 'N/A'} V")
        elif 25 <= capacity <= 50:
            logger.warning(f"UPS Power levels approaching critical - Batteries @ {capacity:.2f}% - Voltage @ {voltage if voltage else 'N/A'} V")
        elif 16 <= capacity <= 24:
            logger.warning(f"UPS Power levels critical - Batteries @ {capacity:.2f}% - Voltage @ {voltage if voltage else 'N/A'} V")
        elif capacity <= 15:
            logger.critical(f"UPS Power failure imminent - Batteries @ {capacity:.2f}%")

def control_charging(charge_line, voltage, current_charge_state):
    hysteresis = 0.05  # Voltage buffer to prevent frequent toggling
    if voltage is None:
        logger.warning("Cannot control charging - voltage reading failed")
        return current_charge_state
    try:
        if voltage >= MAX_CHARGE_VOLTAGE and current_charge_state:
            charge_line.set_value(1 - CHARGE_ENABLE_STATE)  # Disable charging
            logger.info(f"CHARGING STOPPED - Voltage {voltage:.3f}V >= {MAX_CHARGE_VOLTAGE}V")
            return False
        elif voltage <= (CHARGE_RESUME_VOLTAGE - hysteresis) and not current_charge_state:
            charge_line.set_value(CHARGE_ENABLE_STATE)  # Enable charging
            logger.info(f"CHARGING RESUMED - Voltage {voltage:.3f}V <= {CHARGE_RESUME_VOLTAGE - hysteresis}V")
            return True
        elif current_charge_state and voltage < MAX_CHARGE_VOLTAGE:
            # Ensure charging continues until MAX_CHARGE_VOLTAGE is reached
            logger.info(f"CHARGING CONTINUING - Voltage {voltage:.3f}V < {MAX_CHARGE_VOLTAGE}V")
            return True
        else:
            #logger.debug(f"No change in charging state. Voltage: {voltage:.3f}V, Current State: {current_charge_state}")
            return current_charge_state
    except Exception as e:
        logger.error(f"Error controlling charging: {e}")
        return current_charge_state

def check_critical_conditions(ac_power_state, voltage, capacity):
    critical_conditions = []
    if voltage is not None and voltage < CRITICAL_VOLTAGE_THRESHOLD:
        critical_conditions.append(f"critical battery voltage ({voltage:.3f}V < {CRITICAL_VOLTAGE_THRESHOLD}V)")
    if ac_power_state == 0 and voltage is not None and voltage < CRITICAL_VOLTAGE_THRESHOLD:
        critical_conditions.append("AC power loss with critical battery voltage")
    # Optionally check capacity as a secondary condition
    # if capacity is not None and capacity < CRITICAL_CAPACITY_THRESHOLD:
    #     critical_conditions.append(f"critical battery capacity ({capacity:.1f}% < {CRITICAL_CAPACITY_THRESHOLD}%)")
    return critical_conditions

def quick_start_fuel_gauge(bus, address):
    try:
        bus.write_word_data(address, 6, 0x4000)  # MODE register quick-start command
        time.sleep(1)
    except Exception as e:
        logger.error(f"Error performing quick-start: {e}")

# Main logic
charging_enabled = True
bus = None
chip = None
pld_line = None
charge_line = None

try:
    bus = smbus2.SMBus(1)
    address = 0x36

    PLD_PIN = 6
    chip = gpiod.Chip('gpiochip0')

    pld_line = chip.get_line(PLD_PIN)
    pld_line.request(consumer="PLD", type=gpiod.LINE_REQ_DIR_IN)

    try:
        charge_line = chip.get_line(CHARGE_CONTROL_PIN)
        charge_line.request(consumer="CHARGE_CTRL", type=gpiod.LINE_REQ_DIR_OUT)
        charge_line.set_value(CHARGE_ENABLE_STATE)
        logger.info(f"Charging control initialized on GPIO {CHARGE_CONTROL_PIN}")
    except Exception as e:
        logger.warning(f"Could not initialize charging control on GPIO {CHARGE_CONTROL_PIN}: {e}")
        logger.warning("Continuing without charging control")
        charge_line = None

    quick_start_fuel_gauge(bus, address)

    logger.info("UPS monitoring started")
    logger.info(f"Critical voltage threshold: {CRITICAL_VOLTAGE_THRESHOLD}V")
    logger.info(f"AC power loss will only trigger shutdown when combined with critical voltage")

    while True:
        failure_counter = 0

        for _ in range(SHUTDOWN_THRESHOLD):
            ac_power_state = pld_line.get_value()
            voltage = readVoltage(bus, address)
            capacity = readCapacity(bus, address)
            battery_status = get_battery_status(voltage)

            if charge_line is not None:
                charging_enabled = control_charging(charge_line, voltage, charging_enabled)

            log_system_stats(voltage, capacity, charging_enabled, ac_power_state)

            critical_conditions = check_critical_conditions(ac_power_state, voltage, capacity)

            if critical_conditions:
                for condition in critical_conditions:
                    logger.warning(f"Critical condition detected: {condition}")
                failure_counter += 1
            else:
                failure_counter = 0
                if ac_power_state == 0:
                    logger.info("AC power loss detected, but battery voltage is above critical threshold - continuing operation")
                break

            if failure_counter < SHUTDOWN_THRESHOLD:
                time.sleep(SLEEP_TIME)

        if failure_counter >= SHUTDOWN_THRESHOLD:
            critical_conditions = check_critical_conditions(ac_power_state, voltage, capacity)
            shutdown_reason = "due to: " + ", ".join(critical_conditions)
            shutdown_message = f"Critical conditions met {shutdown_reason}. Initiating shutdown."
            logger.critical(shutdown_message)

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
    if charge_line is not None:
        try:
            charge_line.release()
        except Exception:
            pass
    if pld_line is not None:
        try:
            pld_line.release()
        except Exception:
            pass
    if chip is not None:
        try:
            chip.close()
        except Exception:
            pass
    logger.info("UPS monitoring stopped")