@echo off
setlocal EnableExtensions

echo ====================================
echo        SuperCopy Build Script
echo ====================================
echo.

set VENV_DIR=.venv
set PYTHON_EXE=%VENV_DIR%\Scripts\python.exe
set PYINSTALLER_EXE=%VENV_DIR%\Scripts\pyinstaller.exe
set REQUIREMENTS_FILE=requirements.txt
set MAIN_SCRIPT=supercopy.py
set OUTPUT_NAME=SuperCopy
set BUILD_CLI=0
set NOPAUSE=0

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--cli" (
    set BUILD_CLI=1
    shift
    goto parse_args
)
if /I "%~1"=="--nopause" (
    set NOPAUSE=1
    shift
    goto parse_args
)
echo Unknown argument: %~1
echo Usage: build.bat [--cli] [--nopause]
exit /b 2

:args_done

if defined npm_lifecycle_event set NOPAUSE=1
if defined CI set NOPAUSE=1
if defined BUN set NOPAUSE=1

:: Extract version from package.json
for /f "tokens=2 delims=:" %%a in ('findstr /R "\"version\":" package.json') do (
    set VERSION=%%a
)
set VERSION=%VERSION:"=%
set VERSION=%VERSION:,=%
set VERSION=%VERSION: =%

echo Version: %VERSION%
if "%BUILD_CLI%"=="1" (
    echo Mode: CLI-only slim build
) else (
    echo Mode: Full build ^(GUI + CLI^)
)
echo.

if not exist "%VENV_DIR%" (
    echo Creating Python virtual environment in %VENV_DIR%...
    python -m venv %VENV_DIR%
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment. Make sure Python is installed and in your PATH.
        goto :error
    )
    echo Virtual environment created successfully.
) else (
    echo Virtual environment already exists.
)
echo.

echo Installing required packages from %REQUIREMENTS_FILE%...
%PYTHON_EXE% -m pip install -r %REQUIREMENTS_FILE%
if errorlevel 1 (
    echo ERROR: Failed to install required packages. Check your internet connection and %REQUIREMENTS_FILE%.
    goto :error
)
echo Packages installed successfully.
echo.

echo Building executable with PyInstaller...
echo This may take a few minutes.

if "%BUILD_CLI%"=="1" (
    %PYINSTALLER_EXE% --name "%OUTPUT_NAME%" --onefile --console ^
        --exclude-module customtkinter --exclude-module tkinter --exclude-module _tkinter ^
        --hidden-import=py7zr --hidden-import=tqdm ^
        "%MAIN_SCRIPT%"
) else (
    %PYINSTALLER_EXE% --name "%OUTPUT_NAME%" --onefile --console ^
        --hidden-import=customtkinter --hidden-import=py7zr --hidden-import=tqdm ^
        "%MAIN_SCRIPT%"
)

if errorlevel 1 (
    echo ERROR: PyInstaller failed to build the executable.
    goto :error
)
echo.

echo ====================================
echo  Build successful!
echo ====================================
echo.
echo The executable can be found at:
echo   .\dist\%OUTPUT_NAME%.exe
echo.

where makensis >nul 2>nul
if %errorlevel% equ 0 (
    if "%BUILD_CLI%"=="1" (
        echo Skipping NSIS installer for CLI-only build.
    ) else (
        echo Creating Windows installer with NSIS...
        makensis /DVERSION=%VERSION% installer.nsi
        if errorlevel 1 (
            echo WARNING: NSIS installer creation failed.
        ) else (
            echo Installer created: SuperCopy-Installer.exe
        )
    )
) else (
    echo NSIS not found in PATH. Skipping installer creation.
    echo Install NSIS from https://nsis.sourceforge.io/ to create installer.
)
echo.
goto :success

:error
echo.
echo ====================================
echo      BUILD FAILED
echo ====================================
if "%NOPAUSE%"=="0" pause
exit /b 1

:success
if "%NOPAUSE%"=="0" pause
exit /b 0
