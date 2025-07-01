# BTCups - Raspberry Pi UPS Monitoring Script

A comprehensive Python script for monitoring and managing Suptronics X120X series UPS boards on Raspberry Pi 5. This script provides battery monitoring, charging control, and automatic safe shutdown functionality.

## Features

- **Battery Monitoring**: Real-time voltage and capacity monitoring using MAX17040/MAX17041 fuel gauge
- **Smart Charging Control**: Prevents overcharging with configurable voltage thresholds
- **Power Loss Detection**: Monitors AC power status via GPIO
- **Safe Shutdown**: Automatic shutdown on critical battery conditions
- **Logging**: Comprehensive logging with configurable levels
- **Service Integration**: Can run as a systemd service for automatic startup

## Hardware Requirements

- Raspberry Pi 5 (or compatible)
- Suptronics X120X series UPS board (X1200, X1201, X1202)
- I2C enabled on Raspberry Pi

## Installation

### 1. Prerequisites

Enable I2C and install required packages:

```bash
# Enable I2C
sudo raspi-config
# Navigate to: Interfacing Options > I2C > Enable

# Install required Python packages
sudo apt update
sudo apt install python3-smbus2 python3-gpiod

# Verify I2C connection (should show device at 0x36)
sudo i2cdetect -y 1
```

### 2. Download and Setup Script

```bash
# Make script executable
chmod +x BTCups.py

# Test run (recommended first)
sudo python3 BTCups.py
```

### 3. Configure for Continuous Operation

Edit the script to enable continuous monitoring:

```python
# In BTCups.py, change:
Loop = False  # to:
Loop = True
```

## Configuration

### Safety Thresholds

Modify these variables in `BTCups.py` based on your requirements:

#### Conservative Settings (Safer, Earlier Shutdown)
```python
SHUTDOWN_THRESHOLD = 2      # Fewer failures needed (faster response)
SLEEP_TIME = 30            # Check more frequently
CRITICAL_CAPACITY = 25     # Shutdown at 25% instead of 20%
CRITICAL_VOLTAGE = 3.30    # Shutdown at 3.30V instead of 3.20V
```

#### Moderate Settings (Balanced - Default)
```python
SHUTDOWN_THRESHOLD = 3      # Default setting
SLEEP_TIME = 60            # Default setting
CRITICAL_CAPACITY = 20     # Default setting  
CRITICAL_VOLTAGE = 3.20    # Default setting
```

#### Aggressive Settings (Maximum Runtime, Higher Risk)
```python
SHUTDOWN_THRESHOLD = 5      # More failures needed (slower response)
SLEEP_TIME = 90            # Check less frequently
CRITICAL_CAPACITY = 15     # Run battery lower
CRITICAL_VOLTAGE = 3.10    # Run voltage lower (risky for Li-ion)
```

### Charging Control Settings

```python
MAX_CHARGE_VOLTAGE = 4.10   # Maximum charging voltage (V)
CHARGE_RESUME_VOLTAGE = 4.05 # Resume charging below this voltage (V)
CHARGE_CONTROL_PIN = 16     # GPIO pin to control charging
CHARGE_ENABLE_STATE = 0     # GPIO state to enable charging (0 = low/enable, 1 = high/disable)
```

**Important**: According to the Suptronics manual:
- `sudo pinctrl set 16 op dl` (drive low) **enables** charging
- `sudo pinctrl set 16 op dh` (drive high) **disables** charging

## Running as a Service

### 1. Create Service File

```bash
sudo tee /etc/systemd/system/btcups.service > /dev/null <<EOF
[Unit]
Description=BTCups UPS Monitor
After=network.target
Wants=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/python3 /home/pi/BTCups.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
```

### 2. Enable and Start Service

```bash
# Reload systemd configuration
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable btcups.service

# Start the service
sudo systemctl start btcups.service
```

### 3. Service Management Commands

```bash
# Check service status
sudo systemctl status btcups.service

# View real-time logs
sudo journalctl -u btcups.service -f

# Stop the service
sudo systemctl stop btcups.service

# Restart the service
sudo systemctl restart btcups.service

# Disable service from starting on boot
sudo systemctl disable btcups.service
```

## Usage

### Manual Operation

```bash
# Single check and exit
sudo python3 BTCups.py

# Continuous monitoring (if Loop = True)
sudo python3 BTCups.py
```

### Expected Output

```
Capacity: 85.23% (High), AC Power: Plugged in, Voltage: 3.856V, Charging: Enabled
Capacity: 84.87% (High), AC Power: Plugged in, Voltage: 3.854V, Charging: Enabled
```

### During Power Loss

```
Capacity: 78.45% (High), AC Power: Unplugged, Voltage: 3.812V, Charging: Disabled
WARNING - UPS is unplugged or AC power loss detected.
```

### Critical Shutdown

```
CRITICAL - Critical condition met due to critical battery level. Initiating shutdown.
```

## GPIO Pin Configuration

The script uses the following GPIO pins:

- **GPIO 6**: Power Loss Detection (PLD) - Input
- **GPIO 16**: Charging Control - Output

### Manual Charging Control

You can manually control charging using pinctrl commands:

```bash
# Enable charging (drive GPIO 16 LOW)
sudo pinctrl set 16 op dl

# Disable charging (drive GPIO 16 HIGH)  
sudo pinctrl set 16 op dh

# Check current GPIO 16 state
sudo pinctrl get 16
```

## Troubleshooting

### Common Issues

#### I2C Device Not Detected
```bash
# Check I2C connection
sudo i2cdetect -y 1

# If 0x36 not shown, clean GPIO contacts and reconnect UPS
```

#### Permission Errors
```bash
# Run with sudo
sudo python3 BTCups.py

# Or add user to i2c group
sudo usermod -a -G i2c $USER
```

#### Service Won't Start
```bash
# Check service logs
sudo journalctl -u btcups.service

# Verify script path in service file
sudo systemctl cat btcups.service
```

#### Charging Control Not Working
- Verify GPIO 16 wiring
- **Important**: Set `CHARGE_ENABLE_STATE = 0` in your script (LOW enables charging)
- Test manually: `sudo pinctrl set 16 op dl` (enable) / `sudo pinctrl set 16 op dh` (disable)
- Check GPIO permissions

### Testing Shutdown Safely

For testing, comment out the actual shutdown command:

```python
# In BTCups.py, replace:
call("sudo nohup shutdown -h now", shell=True)

# With:
logger.critical("TEST MODE: Would shutdown now")
print("TEST MODE: Shutdown would occur here")
# call("sudo nohup shutdown -h now", shell=True)  # Commented for testing
```

## Safety Features

- **Multiple Failure Threshold**: Requires consecutive failures before shutdown
- **Graceful Cleanup**: Properly releases GPIO resources and removes PID file
- **Charging Protection**: Prevents overcharging with voltage monitoring
- **Comprehensive Logging**: All events logged with timestamps
- **Error Handling**: Continues operation even with sensor read failures

## Battery Status Levels

- **Full**: 3.87V - 4.2V
- **High**: 3.7V - 3.87V  
- **Medium**: 3.55V - 3.7V
- **Low**: 3.4V - 3.55V
- **Critical**: < 3.4V

## License

This script is provided as-is for educational and practical use with Suptronics X120X UPS boards.

## Contributing

Feel free to submit issues, feature requests, or improvements via pull requests.

## Support

For hardware-specific issues, consult the [Suptronics X120X documentation](https://suptronics.com/Raspberrypi/Power_mgmt/x120x-v1.0_software.html).

---

**Warning**: This script can trigger automatic system shutdown. Test thoroughly before deploying in production environments.
