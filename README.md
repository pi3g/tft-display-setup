# pi3g TFT Display Setup Script

This repository contains a python script that automates the installation of necessary software in order to use the pi3g capacitive touch TFT displays. 

## Installation

Follow the instructions below to install it. 

1. Clone this repository to your local machine using:
    ```sh
    git clone https://github.com/pi3g/tft-display-setup
    ```
2. Navigate into the cloned repository:
    ```sh
    cd tft-display-setup/
    ```
3. Run the setup script to install the necessary software:
    ```sh
    sudo python setup.py install
    ```

The Installer will automatically prompt you to input what display you have and if the display should be rotated. For a non interactive install `--rotation`, `--display` and either `--reboot` or `--no-reboot` should be specified when executing the python script.

## Uninstallation

In case you want to uninstall the software, run the following command:

```sh
sudo python setup.py uninstall
```