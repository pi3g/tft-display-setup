# Copyright (c) 2023 pi3g GmbH & Co. KG

import click
import subprocess
from subprocess import STDOUT, DEVNULL
import os
import sys
import re

bootconfigfile = "/boot/config.txt"
verbose_mode = False

config = {
    "pi3g-capacitive-tft": {
        "file": "pi3g-capacitive-tft",
        "calibrations": "320 65536 0 -65536 0 15728640 65536",
        "overlay": "dtoverlay=pi3g-capacitive-tft,speed=64000000,fps=30\ndtoverlay=pi3g-capacitive-tft,{rotation}",
        "xorg": """
Section "InputClass"
        Identifier "FocalTech Touchscreen Calibration"
        MatchProduct "EP0110M09"
        MatchDevicePath "/dev/input/event*"
        Driver "libinput"
        Option "TransformationMatrix" "0 1 0 -1 0 1 0 0 1"
EndSection
        """
    },
    "pi3g-capacitive-tft-tpm": {
        "file": "pi3g-capacitive-tft-tpm",
        "calibrations": "320 65536 0 -65536 0 15728640 65536",
        "overlay": "dtoverlay=spi1-2cs\ndtoverlay=pi3g-capacitive-tft-tpm,speed=64000000,fps=30\ndtoverlay=pi3g-capacitive-tft-tpm,{rotation}",
        "xorg": """
Section "InputClass"
        Identifier "FocalTech Touchscreen Calibration"
        MatchProduct "EP0110M09"
        MatchDevicePath "/dev/input/event*"
        Driver "libinput"
        Option "TransformationMatrix" "0 1 0 -1 0 1 0 0 1"
EndSection
        """
    }
}

rotation_options = {
    0: "rotate=0",
    90: "rotate=90,touch-invy=true,touch-swapxy=true",
    180: "rotate=180,touch-invy=true,touch-invx=true",
    270: "rotate=270,touch-invx=true,touch-swapxy=true",
}

# Installation Functions

def update_and_install():
    """
    Updates apt indexes and installs all pre-requisite Software
    """

    print("Updating apt indexes and installing pre-requisite Software...")
    if not run("apt update"):
        print("Couldn't update apt indexes, Exiting.")
        sys.exit(1)
    
    if not run("apt-get install -y bc fbi git python3-dev python3-pip python3-smbus python3-spidev evtest libts-bin device-tree-compiler libraspberrypi-dev build-essential libts0"):
        print("Couldn't install pre-requisite Software, Exiting.")
        sys.exit(1)

def install_drivers(overlay_file):
    """
    Compiles and installs the Device Tree Overlay files needed for the chosen display
    """

    print("Compiling and installing drivers...")
    if not run("dtc -O dtb -o {0}.dtbo -b 0 -@ {0}.dts".format(overlay_file)):
        print("Error compiling the device tree overlay file, Exiting.")
        sys.exit(1)

    if not run("mv -f {0}.dtbo /boot/overlays/{0}.dtbo".format(overlay_file)):
        print("Error moving the device tree overlay to /boot/overlays, Exiting.")
        sys.exit(1)

def update_configtxt(rotation, overlay):
    """
    Adds necessary entries to the /boot/config.txt
    """

    print("Updating {0}".format(bootconfigfile))
    overlay = overlay.format(rotation=rotation_options[rotation])

    with open(bootconfigfile, "a") as file:
        file.write("""
# --- added by pi3g tft installer ---
[all]
hdmi_force_hotplug=1  # required for cases when HDMI is not plugged in!
dtparam=spi=on
dtparam=i2c1=on
dtparam=i2c_arm=on
{overlay}
# --- end pi3g tft installer ---
""".format(overlay=overlay))

def update_udev():
    with open("/etc/udev/rules.d/95-touchmouse.rules", "w") as file:
        file.write("""
SUBSYSTEM=="input", ATTRS{name}=="touchmouse", ENV{DEVNAME}=="*event*", SYMLINK+="input/touchscreen"
""")
    
    with open("/etc/udev/rules.d/95-ftcaptouch.rules", "w") as file:
        file.write("""
SUBSYSTEM=="input", ATTRS{name}=="EP0110M09", ENV{DEVNAME}=="*event*", SYMLINK+="input/touchscreen"
SUBSYSTEM=="input", ATTRS{name}=="generic ft5x06*", ENV{DEVNAME}=="*event*", SYMLINK+="input/touchscreen"
""")

    with open("/etc/udev/rules.d/95-stmpe.rules", "w") as file:
        file.write("""
SUBSYSTEM=="input", ATTRS{name}=="*stmpe*", ENV{DEVNAME}=="*event*", SYMLINK+="input/touchscreen"
""")
                   
def install_fbcp_unit():
    with open("/etc/systemd/system/fbcp.service", "w") as file:
        file.write("""[Unit]
Description=Framebuffer copy utility for PiTFT
After=network.target

[Service]
Type=simple
ExecStartPre=/bin/sleep 10
ExecStart=/usr/local/bin/fbcp

[Install]
WantedBy=multi-user.target
""")
                   
def install_fbcp(rotation):
    print("Installing fbcp...")

    # Install cmake
    if not run("apt-get --yes --allow-downgrades --allow-remove-essential --allow-change-held-packages install cmake"):
        print("Error installing cmake, Exiting.")
    
    # Download and unzip
    if not os.path.exists("/tmp"):
        os.mkdir("/tmp")
    os.chdir("/tmp")
    run("curl -sLO https://github.com/adafruit/rpi-fbcp/archive/master.zip")
    run("rm -rf /tmp/rpi-fbcp-master")
    if not run("unzip master.zip"):
        print("Failed to uncompress rpi-fbcp, Exiting.")
        sys.exit(1)
    
    # Build
    os.chdir("rpi-fbcp-master")
    os.mkdir("build")
    os.chdir("build")
    with open("../CMakeLists.txt", "a") as file:
        file.write("\nset (CMAKE_C_FLAGS \"-std=gnu99 ${CMAKE_C_FLAGS}\")")
    if not run("cmake .."):
        print("Failed to cmake fbcp, Exiting.")
        sys.exit(1)
    if not run("make"):
        print("Failed to make fbcp, Exiting.")
        sys.exit(1)
    
    # Install the build
    run("install fbcp /usr/local/bin/fbcp")
    os.chdir("..")
    run("rm -rf /tmp/rpi-fbcp-master")

    # Install fbcp systemd unit and enable it
    install_fbcp_unit()
    run("systemctl enable fbcp.service")

    # Disable overscan compensation (use full screen):
    run("raspi-config nonint do_overscan 1")
    pattern_replace(bootconfigfile, r"^.*hdmi_force_hotplug.*$", "hdmi_force_hotplug=1", insert=True)
    pattern_replace(bootconfigfile, r"^.*hdmi_group.*$", "hdmi_group=2", insert=True)
    pattern_replace(bootconfigfile, r"^.*hdmi_mode.*$", "hdmi_mode=87", insert=True)
    pattern_replace(bootconfigfile, r"^[^#]*dtoverlay=vc4-kms-v3d.*$", "#dtoverlay=vc4-kms-v3d")
    pattern_replace(bootconfigfile, r"^[^#]*dtoverlay=vc4-fkms-v3d.*$", "#dtoverlay=vc4-fkms-v3d")
    if rotation == 90 or rotation == 270:
        pattern_replace(bootconfigfile, r"^.*hdmi_cvt.*$", "hdmi_cvt=640 480 60 1 0 0 0", insert=True)
    else:
        pattern_replace(bootconfigfile, r"^.*hdmi_cvt.*$", "hdmi_cvt=480 640 60 1 0 0 0", insert=True)

def update_xorg(content):
    with open("/usr/share/X11/xorg.conf.d/20-calibration.conf", "w") as file:
        file.write(content)

def update_pointercal(cal):
    with open("/etc/pointercal", "w") as file:
        file.write(cal)


# Uninstallation Functions

def uninstall_configtxt():
    with open(bootconfigfile, "r") as file:
        lines = file.readlines()
        
    try:
        blockstart = lines.index("# --- added by pi3g tft installer ---\n")
        print(blockstart)
        blockend = lines.index("# --- end pi3g tft installer ---\n", blockstart)
    except ValueError:
        print("Nothing to remove from the {0}".format(bootconfigfile))
        return

    del(lines[blockstart:blockend+1])

    with open(bootconfigfile, "w") as file:
        file.writelines(lines)

def uninstall_fbcp():
    run("sudo systemctl disable fbcp.service")
    run("raspi-config nonint do_overscan 0")
    pattern_replace(bootconfigfile, r"^.*#.*dtoverlay=vc4-kms-v3d.*$", "dtoverlay=vc4-kms-v3d")
    pattern_replace(bootconfigfile, r"^.*#.*dtoverlay=vc4-fkms-v3d.*$", "dtoverlay=vc4-fkms-v3d")
    pattern_replace(bootconfigfile, r"^hdmi_group=2.*$", "")
    pattern_replace(bootconfigfile, r"^hdmi_mode=87.*$", "")
    pattern_replace(bootconfigfile, r"^hdmi_cvt=.*$", "")


# Utilities

def pattern_replace(filename, pattern, replacement, insert = False):
    with open(filename, "r") as file:
        data = file.read()

    if len(re.findall(pattern, data, flags=re.MULTILINE)) == 0:
        if insert:
            data += "\n{0}".format(replacement)
    else:
        data = re.sub(pattern, replacement, data, flags=re.MULTILINE)
   
    with open(filename, "w") as file:
        file.write(data)

def is_root():
    return os.geteuid() == 0

def run(command):
    global verbose_mode
    if verbose_mode:
        return subprocess.run(command, shell=True)
    else:
        return subprocess.run(command, shell=True, stdout=DEVNULL, stderr=STDOUT)
    
def prompt_user(options, prompt):
    i = 0
    for option in options:
        i += 1
        print("[{0}] {1}".format(i, option))
        
    choice = int(input("{0} [1-{1}]: ".format(prompt, i)))
    if choice == 0 or choice > i:
        print("Invalid choice. Exiting")
        sys.exit(1)
    return options[choice - 1]

@click.group()
def cli():
    pass

@cli.command()
@click.option("--display", "-d", nargs=1, default=None, type=click.Choice(list(config.keys())), help="Specify what display you have")
@click.option("--rotation", "-r", nargs=1, default=None, type=int, help="Specify a rotation option in degress {}".format([0,90,180,270]))
@click.option("--reboot/--no-reboot", default=None, help="Specify if you want to automatically reboot after finishing the installation")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose mode to show output of commands")
def install(display, rotation, reboot, verbose):
    global config
    global verbose_mode

    verbose_mode = verbose
    
    if not is_root():
        print("Must be run with sudo")
        sys.exit(1)

    if display is None:
        display = prompt_user(list(config.keys()), "Please specify what display you have: ")
        
    if rotation is None:
        rotation = prompt_user([0,90,180,270], "Specify if the Display should be rotated: ")

    # update and install pre-requisite
    update_and_install()

    # install dto
    install_drivers(overlay_file=config[display]["file"])
    
    # install udev links
    update_udev()

    # install fbcp
    install_fbcp(rotation)

    # config.txt updates
    uninstall_configtxt()
    update_configtxt(rotation, config[display]["overlay"])

    # Update xorg touchscreen calibration
    if "xorg" in config[display]:
        update_xorg(config[display]["xorg"])

    # Update pointercal
    if "calibrations" in config[display]:
        update_pointercal(config[display]["calibrations"])

    print("Installation complete. Settings take effect on next boot.")
    if reboot is None:
        reboot = input("Reboot now ? (y/n) ")
        if reboot.strip().lower() == "y" or reboot.strip().lower() == "yes":
            run("reboot")
    elif reboot:
        run("reboot")

@cli.command()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug mode to show output of commands")
def uninstall(verbose):
    global verbose_mode

    verbose_mode = verbose

    if not is_root():
        print("Must be run with sudo")
        sys.exit(1)

    uninstall_configtxt()
    uninstall_fbcp()
    print("Done.")

if __name__ == '__main__':
    cli()
