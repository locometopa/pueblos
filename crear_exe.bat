@echo off
chcp 65001 >nul
rem Crea PUEBLOS.exe (opcional). Los archivos de trabajo van a una carpeta temporal y se borran al acabar.
echo === Creando PUEBLOS.exe, tarda un par de minutos ===
set "TRABAJO=%TEMP%\pueblos_exe"
rem Primero, todo lo que el programa necesita, para que PyInstaller lo encuentre y lo meta dentro del .exe
py -m pip install --upgrade pip >nul
py -m pip install -r "%~dp0requirements.txt"
py -m pip install pyinstaller
py -m PyInstaller --noconfirm --onefile --windowed --name PUEBLOS --icon "%~dp0nucleo\icono.ico" ^
  --collect-all customtkinter --collect-all pillow_heif ^
  --collect-all requests --collect-all certifi --collect-all charset_normalizer --collect-all urllib3 --collect-all idna ^
  --collect-submodules nucleo ^
  --distpath "%TRABAJO%\dist" --workpath "%TRABAJO%\build" --specpath "%TRABAJO%" ^
  --add-data "%~dp0nucleo;nucleo" "%~dp0pueblos.py"
if exist "%TRABAJO%\dist\PUEBLOS.exe" copy /y "%TRABAJO%\dist\PUEBLOS.exe" "%~dp0PUEBLOS.exe" >nul
rmdir /s /q "%TRABAJO%" 2>nul
rem restos de versiones anteriores de este archivo
if exist "%~dp0build" rmdir /s /q "%~dp0build"
if exist "%~dp0dist" rmdir /s /q "%~dp0dist"
if exist "%~dp0PUEBLOS.spec" del /q "%~dp0PUEBLOS.spec"
echo.
echo Listo: PUEBLOS.exe esta en esta carpeta.
pause
