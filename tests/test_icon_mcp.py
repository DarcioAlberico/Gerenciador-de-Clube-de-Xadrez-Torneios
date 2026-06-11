import os
import shutil
from PIL import Image
from scripts.icon_mcp_server import generate_ico, generate_icns, generate_placeholder_icon

def test_generate_placeholder_and_conversions():
    # Define caminhos temporários de teste
    test_dir = os.path.abspath("tests/temp_test_icons")
    os.makedirs(test_dir, exist_ok=True)
    
    png_path = os.path.join(test_dir, "test_app_icon.png")
    ico_path = os.path.join(test_dir, "test_app_icon.ico")
    icns_path = os.path.join(test_dir, "test_app_icon.icns")
    
    try:
        # 1. Testar geração de placeholder PNG
        res_placeholder = generate_placeholder_icon(
            text="AB",
            output_path=png_path,
            bg_color="#3498DB",
            fg_color="#FFFFFF",
            size=256
        )
        assert "Sucesso" in res_placeholder, f"Falha na geração de placeholder: {res_placeholder}"
        assert os.path.exists(png_path), "PNG de teste não foi criado"
        assert os.path.getsize(png_path) > 0, "PNG de teste está vazio"
        
        # 2. Testar conversão para ICO do Windows
        res_ico = generate_ico(
            image_path=png_path,
            output_path=ico_path,
            sizes=[16, 32, 48, 64, 128, 256]
        )
        assert "Sucesso" in res_ico, f"Falha na geração de ICO: {res_ico}"
        assert os.path.exists(ico_path), "ICO de teste não foi criado"
        assert os.path.getsize(ico_path) > 0, "ICO de teste está vazio"
        
        # 3. Testar conversão para ICNS do macOS
        res_icns = generate_icns(
            image_path=png_path,
            output_path=icns_path,
            sizes=[16, 32, 48, 64, 128, 256, 512]
        )
        assert "Sucesso" in res_icns, f"Falha na geração de ICNS: {res_icns}"
        assert os.path.exists(icns_path), "ICNS de teste não foi criado"
        assert os.path.getsize(icns_path) > 0, "ICNS de teste está vazio"
        
        # 4. Validar se o ICO contém múltiplos tamanhos abrindo com o Pillow
        with Image.open(ico_path) as img_ico:
            assert img_ico.format == "ICO", "Formato não é ICO"
            # O Pillow expõe os tamanhos do ICO no atributo `ico.sizes`
            assert len(img_ico.ico.sizes()) > 0, "ICO não contém sub-imagens de tamanhos"
        
    finally:
        # Limpa os arquivos temporários após o teste
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)
