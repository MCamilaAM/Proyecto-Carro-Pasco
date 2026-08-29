@echo off
title Instalador - Proyecto Robot PASCO & GamepadMapper
color 0A

echo =========================================================
echo    INSTALADOR AUTOMATICO - ROBOT PASCO & GAMEPADMAPPER
echo =========================================================
echo.

:: 1. Verificar si Python esta instalado
where python >nul 2>nul
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Python no fue encontrado en el sistema.
    echo Por favor instala Python 3.10 o superior desde https://www.python.org/
    echo Asegurate de marcar la casilla "Add Python to PATH" durante la instalacion.
    echo.
    pause
    exit /b 1
)

echo [1/3] Python detectado correctamente:
python --version
echo.

:: 2. Actualizar pip e instalar dependencias
echo [2/3] Instalando dependencias desde requirements.txt...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if %errorlevel% neq 0 (
    color 0C
    echo.
    echo [ERROR] Hubo un problema al instalar los paquetes.
    pause
    exit /b 1
)

echo.
echo [3/3] Verificando binarios de GamepadMapper y plugins Qt...
if exist "GamepadMapper.dll" (
    echo [OK] GamepadMapper.dll presente.
) else (
    echo [AVISO] GamepadMapper.dll no se encuentra en la raiz.
)

if exist "platforms\qwindows.dll" (
    echo [OK] Plugin Qt platforms/qwindows.dll presente.
) else (
    echo [AVISO] platforms/qwindows.dll no encontrado.
)

echo.
echo =========================================================
echo    INSTALACION COMPLETADA EXITOSAMENTE!
echo =========================================================
echo.
echo Puedes iniciar el proyecto ejecutando:
echo   - iniciar_panel_visual.bat   (Interfaz grafica recomendada)
echo   - iniciar_control_consola.bat (Modo consola)
echo   - configurar_mando.bat       (Mapeador visual de controles)
echo.
pause
