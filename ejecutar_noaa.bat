@echo off

cd /d "%~dp0"

call .venv\Scripts\activate

echo.
echo ============================================================
echo PROYECTO NOAA - INICIO DEL PROCESO
echo ============================================================

REM ============================================================
REM VERIFICAR INTEGRIDAD DEL HISTORICO
REM ============================================================

echo.
echo ============================================================
echo VERIFICACION DE INTEGRIDAD
echo ============================================================

python scripts\verificar_integridad.py --check

if errorlevel 1 (
    echo.
    echo ============================================================
    echo ALERTA: PROCESO DETENIDO
    echo ============================================================
    echo El archivo historico no paso la verificacion.
    echo No se ejecutara la adquisicion NOAA.
    exit /b 1
)

echo.
echo ============================================================
echo INTEGRIDAD CORRECTA
echo ============================================================

REM ============================================================
REM EJECUTAR ADQUISICION NOAA
REM ============================================================

echo.
echo Iniciando adquisicion NOAA...

python -m scripts.noaa_adquisicion

if errorlevel 1 (
    echo.
    echo ============================================================
    echo ERROR EN ADQUISICION NOAA
    echo ============================================================
    echo El proceso fue detenido debido a un error.
    exit /b 1
)

REM ============================================================
REM PROCESO COMPLETADO
REM ============================================================

echo.
echo ============================================================
echo PROCESO COMPLETADO CORRECTAMENTE
echo ============================================================

echo.
echo El proceso NOAA finalizo sin errores.

exit /b 0