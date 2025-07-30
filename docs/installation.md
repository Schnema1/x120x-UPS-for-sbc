## Installation

### 1. Prerequisites

Enable I2C and install required Python libraries:

```bash
# Enable I2C interface
sudo raspi-config
# Navigate to: Interfacing Options > I2C > Enable

# Install required system packages
sudo apt update
sudo apt install python3-pip python3-smbus2 python3-gpiod i2c-tools

# (Optional) Upgrade pip
python3 -m pip install --upgrade pip

# Install any missing Python libraries via pip (if needed)
python3 -m pip install smbus2 gpiod

# Verify I2C connection (should show device at 0x36)
sudo i2cdetect -y 1
```

### 2. Download and Setup Script

```bash
# Download the script
wget https://github.com/Schnema1/x120x-UPS-for-sbc/blob/main/BTCupsSystemd.py
# or
wget 
https://github.com/Schnema1/x120x-UPS-for-sbc/blob/main/BTCups.py

# Make script executable
chmod +x BTCups.py BTCupsSystemd.py

# Test run BTCups.py (recommended for manual or initial setup)
sudo python3 BTCups.py
```

### 3. Configure for Continuous Operation

For production use, run BTCupsSystemd.py as a systemd service. See below for service setup instructions.

## Configuration

### Safety Thresholds

Modify these variables in `BTCups.py` or `BTCupsSystemd.py` based on your requirements:

#### Conservative Settings (Safer, Earlier Shutdown)
```python
SHUTDOWN_THRESHOLD = 2     # Fewer failures needed (faster response)
SLEEP_TIME = 30            # Check more frequently
CRITICAL_CAPACITY = 25     # Shutdown at 25% instead of 20%
CRITICAL_VOLTAGE = 3.30    # Shutdown at 3.30V instead of 3.20V
```

#### Moderate Settings (Balanced - Default)
```python
SHUTDOWN_THRESHOLD = 3     # Default setting
SLEEP_TIME = 60            # Default setting
CRITICAL_CAPACITY = 20     # Default setting  
CRITICAL_VOLTAGE = 3.20    # Default setting
```

#### Aggressive Settings (Maximum Runtime, Higher Risk)
```python
SHUTDOWN_THRESHOLD = 5     # More failures needed (slower response)
SLEEP_TIME = 90            # Check less frequently
CRITICAL_CAPACITY = 15     # Run battery lower
CRITICAL_VOLTAGE = 3.10    # Run voltage lower (risky for Li-ion)
```

### Charging Control Settings

```python
MAX_CHARGE_VOLTAGE = 4.10   # Maximum charging voltage (V)
CHARGE_RESUME_VOLTAGE = 3.9 # Resume charging below this voltage (V)
CHARGE_CONTROL_PIN = 16     # GPIO pin to control charging
CHARGE_ENABLE_STATE = 0     # GPIO state to enable charging (0 = low/enable, 1 = high/disable)
```

**Important**: According to the Suptronics manual:
- `sudo pinctrl set 16 op dl` (drive low) **enables** charging
- `sudo pinctrl set 16 op dh` (drive high) **disables** charging

## Running as a Service

### 1. Create Service File
**Change path** and user according to your needs. **Use BTCupsSystemd.py for systemd!**

```bash
sudo tee /etc/systemd/system/btcups.service > /dev/null <<EOF
[Unit]
Description=BTCups UPS Monitor
After=network.target
Wants=network.target

[Service]
Type=simple
User=<your user>
ExecStart=/usr/bin/python3 /home/<pathToFile>/BTCupsSystemd.py
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