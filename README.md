# Raspberry Pi UPS Monitoring Script

This project provides two Python scripts for monitoring and managing Suptronics X120X series UPS boards on Raspberry Pi 5:

- **BTCups.py**: Intended for **manual operation, testing, and troubleshooting**. Run this script directly for single checks or interactive monitoring. Recommended for initial setup, diagnostics, or development. Output is printed to the console.
- **BTCupsSystemd.py**: Designed for **continuous, unattended operation as a systemd service**. Use this script for automatic startup and safe shutdown in production environments. All output is logged (not printed) and is suitable for background/system use.

> **Summary:**  
> Use `BTCups.py` for manual checks and debugging.  
> Use `BTCupsSystemd.py` for 24/7 monitoring as a background service (systemd).

Both scripts provide battery monitoring, charging control, and automatic safe shutdown functionality. This is a fork of the original repo [suptronics](https://github.com/suptronics/x120x.git).

Tested with Rpi5 only. If your SBC matches the Rpi5 pin layout, it should work as well.

Intended for use with Bitcoin Fullnode projects like [raspiblitz](https://github.com/raspiblitz/raspiblitz), [raspibolt](https://github.com/raspibolt/raspibolt/) or similar. With lightning enabled, you don't want to risk a power loss and get a corrupted database. This script allows you to run some hours without power and, if the batteries are close to empty, perform a graceful shutdown.

**Open Points**
Once the desired voltage is reached, the script stops charging. However, as long the charger is plugged in, there is still kind of charge happening.

**This fork is enhanced by AI.**

## Features

- **Battery Monitoring**: Real-time voltage and capacity monitoring using MAX17040/MAX17041 fuel gauge
- **Smart Charging Control**: Prevents overcharging with configurable voltage thresholds
- **Power Loss Detection**: Monitors AC power status via GPIO
- **Safe Shutdown**: Automatic shutdown on critical battery conditions
- **Logging**: Comprehensive logging with configurable levels
- **Service Integration**: BTCupsSystemd.py can run as a systemd service for automatic startup

## Hardware Requirements

- Raspberry Pi 5 (or GIPO compatible boards )
- Geekworm X1200 series UPS board (X1200, X1201, X1202)
- I2C enabled on Raspberry Pi

## Safety Features

- **Multiple Failure Threshold**: Requires consecutive failures before shutdown
- **Graceful Cleanup**: Properly releases GPIO resources
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