@echo off
title Mapeador y Calibrador de Mandos
if exist "SingleSwitchMapperApp.exe" (
    start "" SingleSwitchMapperApp.exe
) else (
    start "" python gamepad_mapper.py --switch
)
