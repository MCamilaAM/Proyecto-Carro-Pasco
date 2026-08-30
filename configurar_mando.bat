@echo off
title Mapeador y Calibrador de Mandos
if exist "GamepadMapperApp.exe" (
    start "" GamepadMapperApp.exe
) else (
    start "" python gamepad_mapper.py --multi
)
