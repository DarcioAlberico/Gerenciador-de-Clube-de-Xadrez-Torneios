from pathlib import Path

import markdown
from xhtml2pdf import pisa


def generate_pdf():
    manual_dir = Path(__file__).resolve().parent
    md_path = manual_dir / "Manual_do_Usuario.md"
    pdf_path = manual_dir / "Manual_do_Usuario.pdf"

    md_text = md_path.read_text(encoding="utf-8")

    # Convert relative image links to absolute paths for xhtml2pdf
    for image_name in ("dashboard.png", "tournaments.png", "club.png", "settings.png"):
        md_text = md_text.replace(f"]({image_name})", f"]({manual_dir / image_name})")

    # Markdown to HTML
    html_content = markdown.markdown(md_text, extensions=['tables'])

    # Wrap in HTML with styling
    full_html = f"""
    <html>
    <head>
    <meta charset="utf-8">
    <style>
        @page {{
            size: A4;
            margin: 2cm;
        }}
        body {{
            font-family: Helvetica, Arial, sans-serif;
            font-size: 12pt;
            line-height: 1.5;
            color: #333333;
        }}
        h1 {{
            color: #1a5276;
            text-align: center;
            font-size: 24pt;
            margin-bottom: 20px;
        }}
        h2 {{
            color: #2980b9;
            font-size: 18pt;
            border-bottom: 1px solid #bdc3c7;
            padding-bottom: 5px;
            margin-top: 30px;
        }}
        h3 {{
            color: #2c3e50;
            font-size: 14pt;
            margin-top: 20px;
        }}
        img {{
            max-width: 100%;
            display: block;
            margin: 15px auto;
            border: 1px solid #cccccc;
        }}
        p {{
            text-align: justify;
        }}
        ul {{
            margin-bottom: 15px;
        }}
        blockquote {{
            background-color: #f8f9f9;
            border-left: 5px solid #3498db;
            padding: 10px;
            margin: 10px 0;
            font-style: italic;
        }}
    </style>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """

    with pdf_path.open("wb") as f_out:
        pisa_status = pisa.CreatePDF(full_html.encode("utf-8"), dest=f_out, encoding="utf-8")

    if pisa_status.err:
        print(f"Error creating PDF: {pisa_status.err}")
    else:
        print("PDF created successfully at:", pdf_path)

if __name__ == "__main__":
    generate_pdf()
