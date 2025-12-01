@echo off
setlocal

:: Set the destination directory for the installation
set "INSTALL_DIR=%LOCALAPPDATA%\SuperCopy"
set "SOURCE_EXE=.\dist\SuperCopy.exe"

echo Installing SuperCopy...

:: 1. Check if the SuperCopy.exe exists
if not exist "%SOURCE_EXE%" (
    echo.
    echo ERROR: SuperCopy.exe not found in .\dist directory.
    echo Please make sure you have run the packaging step first.
    goto :eof
)

:: 2. Create the installation directory if it doesn't exist
if not exist "%INSTALL_DIR%" (
    echo Creating installation directory at %INSTALL_DIR%
    mkdir "%INSTALL_DIR%"
)

:: 3. Copy the executable to the installation directory
echo Copying SuperCopy.exe to %INSTALL_DIR%...
copy /Y "%SOURCE_EXE%" "%INSTALL_DIR%" > nul
if errorlevel 1 (
    echo.
    echo ERROR: Failed to copy SuperCopy.exe.
    goto :eof
)

:: 4. Add the installation directory to the user's PATH if it's not already there
echo Checking if SuperCopy is already in PATH...
set "CURRENT_PATH="
for /f "skip=2 tokens=2,*" %%A in ('reg query HKCU\Environment /v PATH') do set "CURRENT_PATH=%%B"

echo "%CURRENT_PATH%" | find /I "%INSTALL_DIR%" > nul
if %errorlevel% == 0 (
    echo SuperCopy is already in your PATH.
) else (
    echo Adding %INSTALL_DIR% to your PATH.
    :: The `setx` command permanently adds the directory to the user's PATH.
    setx PATH "%%PATH%%;%INSTALL_DIR%"
    if errorlevel 1 (
        echo.
        echo ERROR: Failed to update the PATH. Please try running this script as an administrator.
        goto :eof
    )
    echo Successfully added SuperCopy to PATH.
)

echo.
echo +-------------------------------------------------------------------+
echo ^|                                                                 ^|
echo ^|  SuperCopy has been successfully installed!                     ^|
echo ^|                                                                 ^|
echo ^|  To use it, you MUST restart your terminal/command prompt.      ^|
echo ^|                                                                 ^|
echo ^|  Usage: SuperCopy ^<source^> ^<destination^>                        ^|
echo ^|                                                                 ^|
echo +-------------------------------------------------------------------+
echo.

endlocal
pause
