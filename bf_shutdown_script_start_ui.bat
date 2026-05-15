echo Script ran at %time% >> C:\temp\shutdown_log.txt

@echo off
start "" /wait "C:\Program Files (x86)\ControlSoftware\ControlSoftwareCore.exe"

timeout /t 10

cd /d C:\Users\quantumuser\bluefors-temp-control
python bf_shutdown_4k_heater.py

