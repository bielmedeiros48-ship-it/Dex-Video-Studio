@echo off
title Dex Video Studio - Canal Dark
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Dex-Video.ps1" dark-news --project canal-noticias
echo.
echo O fluxo terminou ou parou em uma etapa que precisa de revisao.
pause
