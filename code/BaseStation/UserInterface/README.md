# Base Station User Interface
Used on the base station to receive inputs from a controller and send appropriate commands to the robot.

## Libraries to install
- PyQt5 for the GUI -> "pip install PyQt5"
- xbox_controller -> "pip install xbox-controller-py"

## X-Box Controller Setup
Some X-box controllers that we are using require a chinese-made dongle to plug into the computer.  This requires drivers which the following steps should help in installing. Note: I already have them installed, so this procedure might require revision.
1. Open device manager and verify that no driver is listed for the X-Box controller. If you need a driver, continue to step 2.
2. Navigate to https://www.s-config.com/chinese-xbox-360-wireless-receiver-driver-setup/
3. Download and extract the 7-zip archive. My downloaded folder was called "chinabox.7z"
4. Run the "Xbox360_64Eng/setup.exe"
5. While this is running, you should be able to added the driver for your controller:
    1. Open device manager and locate the unknown device
    2. Right click and Update Driver Software
    3. Browse the computer for the driver sofware
    4. Pick from the list of device drivers on the computer
    5. Select "Xbox 360 Peripherals"
    6. Select "Xbox 360 Wireless Receiver for widnows Version: 2.1.0.1349"
6. Note: The installer also installs a bunch of .NET stuff, which I don't think we need, so I cancelled the installation once I got the driver assigned

### To pair the X-Box Controller
1. Turn on both the controller and the dongle.
2. Press the sync button on the top end of the controller
