@echo off
echo Iniciando o empacotamento do Albericus...

:: Atualizar dependencias se necessario
uv pip install pyinstaller

:: Rodar o PyInstaller com base no spec
uv run pyinstaller albericus.spec --clean -y

echo.
echo Build finalizado! Verifique a pasta 'dist/Albericus'.
pause
