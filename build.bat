@echo off
setlocal

echo ====================================
echo        SuperCopy Build Script
echo ====================================
echo.

:: Define the virtual environment directory
set VENV_DIR=.venv
set PYTHON_EXE=%VENV_DIR%\Scripts\python.exe
set PYINSTALLER_EXE=%VENV_DIR%\Scripts\pyinstaller.exe
set REQUIREMENTS_FILE=requirements.txt
set MAIN_SCRIPT=supercopy.py
set OUTPUT_NAME=SuperCopy

:: 1. Check for and create the virtual environment
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

:: 2. Install dependencies from requirements.txt
echo Installing required packages from %REQUIREMENTS_FILE%...
%PYTHON_EXE% -m pip install -r %REQUIREMENTS_FILE%
if errorlevel 1 (
    echo ERROR: Failed to install required packages. Check your internet connection and %REQUIREMENTS_FILE%.
    goto :error
)
echo Packages installed successfully.
echo.

:: 3. Run PyInstaller to build the executable
echo Building executable with PyInstaller...
echo This may take a few minutes.
%PYINSTALLER_EXE% --name "%OUTPUT_NAME%" --onefile --icon=NONE "%MAIN_SCRIPT%"

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
goto :success

:error
echo.
echo ====================================
echo      BUILD FAILED
echo ====================================
pause
exit /b 1

:success
pause
exit /b 0
