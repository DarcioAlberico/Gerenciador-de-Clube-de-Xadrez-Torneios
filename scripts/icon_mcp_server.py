import logging
import os
import sys
from typing import List, Optional

from mcp.server.fastmcp import FastMCP
from PIL import Image, ImageDraw, ImageFont

# Configura o logger para escrever no stderr para não interferir com a comunicação stdio
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("icon-specialist")

# Inicializa o servidor MCP
mcp = FastMCP(
    name="IconSpecialist",
    instructions="Servidor MCP local para criação, conversão e extração de ícones para programas."
)

@mcp.tool()
def generate_ico(
    image_path: str,
    output_path: str,
    sizes: Optional[List[int]] = None
) -> str:
    """Converte uma imagem (PNG, JPG, etc.) em um arquivo .ico do Windows contendo múltiplos tamanhos de resolução.

    Args:
        image_path: Caminho absoluto para a imagem de origem.
        output_path: Caminho absoluto de destino para o arquivo .ico.
        sizes: Tamanhos das resoluções desejadas (ex: [16, 32, 48, 64, 128, 256]). Se omitido, usará o padrão completo.
    """
    logger.info(f"Gerando ICO de {image_path} para {output_path}")
    if not os.path.exists(image_path):
        return f"Erro: O arquivo de imagem de origem não existe: {image_path}"
    
    if sizes is None:
        sizes = [16, 32, 48, 64, 128, 256]

    try:
        img = Image.open(image_path)
        valid_sizes = []
        for size in sizes:
            if 1 <= size <= 256:  # O formato ICO padrão do Windows suporta até 256x256
                valid_sizes.append((size, size))
        
        if not valid_sizes:
            valid_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
            
        # Garante que a pasta de destino exista
        dest_dir = os.path.dirname(output_path)
        if dest_dir and not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)
            
        img.save(output_path, format='ICO', sizes=valid_sizes)
        return f"Sucesso: Ícone do Windows (.ico) gerado em '{output_path}' com tamanhos {[s[0] for s in valid_sizes]}."
    except Exception as e:
        logger.error(f"Erro ao gerar ICO: {str(e)}")
        return f"Erro ao gerar ícone ICO: {str(e)}"

@mcp.tool()
def generate_icns(
    image_path: str,
    output_path: str,
    sizes: Optional[List[int]] = None
) -> str:
    """Converte uma imagem (PNG, JPG, etc.) em um arquivo .icns do macOS contendo múltiplos tamanhos de resolução.

    Args:
        image_path: Caminho absoluto para a imagem de origem.
        output_path: Caminho absoluto de destino para o arquivo .icns.
        sizes: Tamanhos das resoluções desejadas (ex: [16, 32, 48, 64, 128, 256, 512, 1024]). Se omitido, usará o padrão completo.
    """
    logger.info(f"Gerando ICNS de {image_path} para {output_path}")
    if not os.path.exists(image_path):
        return f"Erro: O arquivo de imagem de origem não existe: {image_path}"
    
    if sizes is None:
        sizes = [16, 32, 48, 64, 128, 256, 512, 1024]

    try:
        img = Image.open(image_path)
        valid_sizes = []
        for size in sizes:
            # ICNS suporta resoluções maiores como 512 e 1024
            if 1 <= size <= 1024:
                valid_sizes.append((size, size))
        
        if not valid_sizes:
            valid_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256), (512, 512), (1024, 1024)]
            
        # Garante que a pasta de destino exista
        dest_dir = os.path.dirname(output_path)
        if dest_dir and not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)
            
        img.save(output_path, format='ICNS', sizes=valid_sizes)
        return f"Sucesso: Ícone do macOS (.icns) gerado em '{output_path}' com tamanhos {[s[0] for s in valid_sizes]}."
    except Exception as e:
        logger.error(f"Erro ao gerar ICNS: {str(e)}")
        return f"Erro ao gerar ícone ICNS: {str(e)}"

@mcp.tool()
def generate_placeholder_icon(
    text: str,
    output_path: str,
    bg_color: str = "#2C3E50",
    fg_color: str = "#ECF0F1",
    size: int = 256
) -> str:
    """Gera um ícone minimalista moderno contendo um monograma/texto, útil para novos aplicativos ou protótipos.

    Args:
        text: Texto/Monograma para desenhar no centro (ex: "CH", "SM", "APP").
        output_path: Caminho do arquivo a ser salvo (.png, .ico, ou .icns).
        bg_color: Cor de fundo do ícone (hex ou nome de cor CSS, ex: "#3498DB", "#2C3E50").
        fg_color: Cor do texto (hex ou nome de cor CSS, ex: "#FFFFFF").
        size: Tamanho da imagem base (padrão 256).
    """
    logger.info(f"Gerando ícone placeholder com texto '{text}' para {output_path}")
    try:
        # Cria a imagem com fundo colorido
        img = Image.new("RGBA", (size, size), bg_color)
        draw = ImageDraw.Draw(img)
        
        # Tenta carregar uma fonte elegante ou usa a padrão
        font = None
        try:
            # Lista de fontes comuns no Windows
            font_names = ["arial.ttf", "calibri.ttf", "segoeui.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"]
            for font_name in font_names:
                try:
                    font = ImageFont.truetype(font_name, int(size * 0.45))
                    break
                except IOError:
                    continue
            if font is None:
                font = ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()
            
        # Calcula a centralização do texto
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
        except AttributeError:
            # Pillow legado
            w, h = draw.textsize(text, font=font)
            
        x = (size - w) / 2
        y = (size - h) / 2 - (size * 0.05)  # Ajuste fino vertical
        
        draw.text((x, y), text, fill=fg_color, font=font)
        
        # Garante que a pasta de destino exista
        dest_dir = os.path.dirname(output_path)
        if dest_dir and not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)
            
        # Salva dependendo da extensão
        ext = os.path.splitext(output_path)[1].lower()
        if ext == '.ico':
            img.save(output_path, format='ICO', sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
        elif ext == '.icns':
            img.save(output_path, format='ICNS', sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256), (512, 512)])
        else:
            img.save(output_path)
            
        return f"Sucesso: Ícone placeholder gerado em '{output_path}' (Tamanho base: {size}x{size}, Texto: '{text}')."
    except Exception as e:
        logger.error(f"Erro ao gerar ícone placeholder: {str(e)}")
        return f"Erro ao gerar ícone placeholder: {str(e)}"

@mcp.tool()
def extract_ico_from_exe(
    exe_path: str,
    output_path: str
) -> str:
    """Extrai o ícone principal de um executável do Windows (.exe ou .dll) e salva como um arquivo .ico.

    Args:
        exe_path: Caminho absoluto para o arquivo executável.
        output_path: Caminho absoluto para salvar o arquivo de ícone extraído.
    """
    logger.info(f"Extraindo ícone de {exe_path} para {output_path}")
    if not os.path.exists(exe_path):
        return f"Erro: O arquivo executável de origem não existe: {exe_path}"
        
    try:
        from icoextract import IconExtractor
        extractor = IconExtractor(exe_path)
        
        # Garante que a pasta de destino exista
        dest_dir = os.path.dirname(output_path)
        if dest_dir and not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)
            
        extractor.export_icon(output_path)
        return f"Sucesso: Ícone extraído de '{exe_path}' e salvo em '{output_path}'."
    except Exception as e:
        logger.error(f"Erro ao extrair ícone com icoextract: {str(e)}")
        return f"Erro ao extrair ícone do executável: {str(e)}"

if __name__ == "__main__":
    mcp.run()
