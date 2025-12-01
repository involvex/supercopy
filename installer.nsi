; SuperCopy NSIS Installer Script
;
; This script requires that:
; 1. NSIS is installed on your system.
; 2. You have run build.bat to create 'dist\SuperCopy.exe'.
; 3. You have placed 'unrar.exe' inside the 'assets' directory.
;    Get the "UnRAR for Windows" command-line tool from:
;    https://www.rarlab.com/rar_add.htm

;--------------------------------
; General

!define APP_NAME "SuperCopy"
!define COMPANY_NAME "SuperCopy Project"
!define VERSION "1.0.0"
!define EXE_NAME "SuperCopy.exe"
!define UNRAR_EXE "unrar.exe"
!define INSTALLER_NAME "SuperCopy-Installer.exe"

; The name of the installer
Name "${APP_NAME} ${VERSION}"

; The file to write
OutFile "${INSTALLER_NAME}"

; The default installation directory
InstallDir "$LOCALAPPDATA\${APP_NAME}"

; Request application privileges for Windows Vista+
RequestExecutionLevel user

;--------------------------------
; Interface Settings

!include "MUI2.nsh"

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; Languages
!insertmacro MUI_LANGUAGE "English"

;--------------------------------
; Installer Sections

Section "Install" SecInstall
  SetOutPath "$INSTDIR"
  
  ; Add files
  File "dist\${EXE_NAME}"
  File "assets\${UNRAR_EXE}"
  
  ; Write the installation path to the registry
  WriteRegStr HKCU "Software\${COMPANY_NAME}\${APP_NAME}" "Install_Dir" "$INSTDIR"
  
  ; Write the uninstall keys for Windows
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayName" "${APP_NAME}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "NoRepair" 1
  
  ; Add to PATH
  !include "EnvVarUpdate.nsh"
  ${EnvVarUpdate} $0 "PATH" "A" "HKCU" "$INSTDIR"

  ; Create uninstaller
  WriteUninstaller "$INSTDIR\uninstall.exe"
  
  ; Create Start Menu shortcuts
  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortCut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${EXE_NAME}"
  CreateShortCut "$SMPROGRAMS\${APP_NAME}\Uninstall ${APP_NAME}.lnk" "$INSTDIR\uninstall.exe"
  
SectionEnd

;--------------------------------
; Uninstaller Section

Section "Uninstall"
  ; Remove registry keys
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
  DeleteRegKey HKCU "Software\${COMPANY_NAME}\${APP_NAME}"

  ; Remove files and directories
  Delete "$INSTDIR\${EXE_NAME}"
  Delete "$INSTDIR\${UNRAR_EXE}"
  Delete "$INSTDIR\uninstall.exe"
  RMDir "$INSTDIR"
  
  ; Remove Start Menu shortcuts
  Delete "$SMPROGRAMS\${APP_NAME}\*.*"
  RMDir "$SMPROGRAMS\${APP_NAME}"
  
  ; Remove from PATH
  !include "EnvVarUpdate.nsh"
  ${un.EnvVarUpdate} $0 "PATH" "R" "HKCU" "$INSTDIR"
  
SectionEnd
