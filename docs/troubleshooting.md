## Troubleshooting

### Common Issues

#### I2C Device Not Detected
```bash
# Check I2C connection
sudo i2cdetect -y 1

# If 0x36 not shown, clean GPIO contacts and reconnect UPS
# Make sure the pogo pins fit the GIPO Pins smoothly
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

### Reading Logs

- **With systemd/journalctl** (recommended):  
  ```bash
  sudo journalctl -u btcups.service -f
  ```
- **If logging to a file is configured** (edit the script to use `logging.FileHandler`):  
  Check the specified log file, e.g.:
  ```bash
  tail -f /var/log/btcups.log
  ```
- **For manual runs (BTCups.py)**:  
  Output is printed directly to the terminal.

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