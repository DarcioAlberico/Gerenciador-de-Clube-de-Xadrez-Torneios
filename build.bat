@echo off
setlocal
echo Iniciando o empacotamento do Albericus...

:: Atualizar dependencias se necessario
uv pip install pyinstaller
if errorlevel 1 exit /b %errorlevel%

:: Rodar o PyInstaller com base no spec
uv run pyinstaller albericus.spec --clean -y
if errorlevel 1 (
    echo FALHA: o PyInstaller nao gerou o executavel.
    exit /b 1
)

:: RGS-05: o executavel que sera distribuido precisa passar no autoteste
:: (textos, banco, 3 rodadas e desempate pelo Gacrux, PDF e TRF).
:: start /wait: o .exe e janela (console=False); sem ele o cmd nao espera.
set SELFTEST_DIR=%~dp0build\selftest
if exist "%SELFTEST_DIR%" rmdir /s /q "%SELFTEST_DIR%"
start "" /wait "%~dp0dist\Albericus.exe" --self-test "%SELFTEST_DIR%"
set SELFTEST_CODE=%errorlevel%
if not "%SELFTEST_CODE%"=="0" (
    echo FALHA: autoteste do executavel saiu com codigo %SELFTEST_CODE%.
    echo Detalhes em %SELFTEST_DIR%\selftest.json
    exit /b %SELFTEST_CODE%
)

echo.
echo Build finalizado e autoteste aprovado: dist\Albericus.exe
exit /b 0
