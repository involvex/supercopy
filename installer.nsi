; SuperCopy NSIS Installer Script
;
; This script requires that NSIS is installed on your system.
; It assumes you have run build.bat to create 'dist\SuperCopy.exe'.
; It no longer requires any external .nsh files or assets.

;--------------------------------
; General

!define APP_NAME "SuperCopy"
!define COMPANY_NAME "SuperCopy Project"
!define VERSION "1.0.0"
!define EXE_NAME "SuperCopy.exe"
!define INSTALLER_NAME "SuperCopy-Installer.exe"

Name "${APP_NAME} ${VERSION}"
OutFile "${INSTALLER_NAME}"
InstallDir "$LOCALAPPDATA\${APP_NAME}"
RequestExecutionLevel user

;--------------------------------
; Interface Settings

!include "MUI2.nsh"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

;============================================================================
; Embedded Environment Variable Functions
; (Self-contained, from NSIS Wiki)
;============================================================================

!macro AddToEnvVar PATH_VAR NEW_VALUE
  Push "${PATH_VAR}"
  Push "${NEW_VALUE}"
  Call AddToPath
!macroend
!macro un.RemoveFromEnvVar PATH_VAR OLD_VALUE
  Push "${PATH_VAR}"
  Push "${OLD_VALUE}"
  Call un.RemoveFromPath
!macroend

Function AddToPath
  Exch $0
  Exch
  Exch $1
  Push $2
  Push $3
  Push $4
  Push $5

  ReadRegStr $2 HKCU "Environment" "$1"
  StrCpy $3 $0 -1
  StrCmp $3 ";" 0 +2
  StrCpy $0 $0 -1

  StrCpy $3 $2 1 -1
  StrCmp $3 ";" 0 +2
  StrCpy $2 $2 -1

  StrCpy $5 $2
  StrCpy $4 ""
  GetNextPart:
    StrCpy $3 $5 1
    StrCmp $3 ";" 0 +3
    StrCpy $3 $4
    StrCpy $4 ""
    Goto +2
    StrCpy $4 "$4$3"
    StrCpy $5 $5 "" 1
    StrCmp $5 "" GetNextPartDone GetNextPart

  GetNextPartDone:
    StrCmp $3 $0 PathAlreadyExists

  StrCmp $2 "" PathIsEmpty
  StrCpy $0 "$2;$0"

PathIsEmpty:
  WriteRegExpandStr HKCU "Environment" "$1" "$0"
  SendMessage ${HWND_BROADCAST} ${WM_WININICHANGE} 0 "STR:Environment" /TIMEOUT=5000

PathAlreadyExists:
  Pop $5
  Pop $4
  Pop $3
  Pop $2
  Pop $1
  Pop $0
FunctionEnd

Function un.RemoveFromPath
  Exch $0
  Exch
  Exch $1
  Push $2
  Push $3
  Push $4
  Push $5
  Push $6

  ReadRegStr $2 HKCU "Environment" "$1"
  StrCpy $6 ""
  StrCpy $5 $2
  un.GetNextPart:
    StrCpy $3 $5 1
    StrCmp $3 ";" 0 +3
    StrCpy $3 $4
    StrCpy $4 ""
    Goto +2
    StrCpy $4 "$4$3"
    StrCpy $5 $5 "" 1
    StrCmp $5 "" un.GetNextPartDone un.GetNextPart

  un.GetNextPartDone:
    StrCmp $3 $0 un.FoundPart
    StrCmp $6 "" +2
    StrCpy $6 "$6;"
    StrCpy $6 "$6$3"
    Goto un.GetNextPart

  un.FoundPart:
    Goto un.GetNextPart

  WriteRegExpandStr HKCU "Environment" "$1" "$6"
  SendMessage ${HWND_BROADCAST} ${WM_WININICHANGE} 0 "STR:Environment" /TIMEOUT=5000

  Pop $6
  Pop $5
  Pop $4
  Pop $3
  Pop $2
  Pop $1
  Pop $0
FunctionEnd


;--------------------------------
; Installer Sections

Section "Install" SecInstall
  SetOutPath "$INSTDIR"
  
  File "dist\${EXE_NAME}"
  
  WriteRegStr HKCU "Software\${COMPANY_NAME}\${APP_NAME}" "Install_Dir" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayName" "${APP_NAME}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "NoRepair" 1
  
  ; Add to PATH
  Push "PATH"
  Push "$INSTDIR"
  Call AddToPath

  WriteUninstaller "$INSTDIR\uninstall.exe"
  
  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortCut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${EXE_NAME}"
  CreateShortCut "$SMPROGRAMS\${APP_NAME}\Uninstall ${APP_NAME}.lnk" "$INSTDIR\uninstall.exe"
  
SectionEnd

;--------------------------------
; Uninstaller Section

Section "Uninstall"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
  DeleteRegKey HKCU "Software\${COMPANY_NAME}\${APP_NAME}"

  Delete "$INSTDIR\${EXE_NAME}"
  Delete "$INSTDIR\uninstall.exe"
  RMDir "$INSTDIR"
  
  Delete "$SMPROGRAMS\${APP_NAME}\*.*"
  RMDir "$SMPROGRAMS\${APP_NAME}"
  
  ; Remove from PATH
  Push "PATH"
  Push "$INSTDIR"
  Call un.RemoveFromPath
  
SectionEnd
