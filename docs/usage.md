## Usage

### Manual Operation (BTCups.py)

```bash
# Single check and exit
sudo python3 BTCups.py

# Continuous monitoring (if Loop = True)
sudo python3 BTCups.py
```

### Service Operation (BTCupsSystemd.py)

Once enabled, BTCupsSystemd.py will run automatically in the background and handle UPS monitoring and shutdown as needed. Use systemctl and journalctl to manage and view logs.

### Output

- **BTCups.py**: Prints status and warnings to the console for manual review.
- **BTCupsSystemd.py**: Logs all status and warnings to the system journal (view with `journalctl -u btcups.service -f`).

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