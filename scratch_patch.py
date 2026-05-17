import sys

try:
    with open('c:\\PythonCurso\\Albericus\\src\\ui_settings.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    content = content.replace('if report_option.get() == "Site HTML":', 'if report_option.get() in ("Site HTML", "TRF FIDE", "PGN (Partidas)"):')
    
    # Fix names dict
    target_names = '"Equipes": f"{safe_name}_equipes",\n            }'
    replacement_names = '"Equipes": f"{safe_name}_equipes",\n                "TRF FIDE": f"{safe_name}_fide",\n                "PGN (Partidas)": f"{safe_name}_partidas",\n            }'
    content = content.replace(target_names, replacement_names)
    
    # Fix extension and export cases
    target_ext = 'extension = format_option.get()'
    replacement_ext = 'extension = format_option.get()\n                if report == "TRF FIDE":\n                    extension = "txt"\n                elif report == "PGN (Partidas)":\n                    extension = "pgn"'
    content = content.replace(target_ext, replacement_ext)
    
    target_case = 'elif report == "Equipes":\n                        self.export_service.export_teams(tournament_id, path)\n                    else:'
    replacement_case = 'elif report == "Equipes":\n                        self.export_service.export_teams(tournament_id, path)\n                    elif report == "TRF FIDE":\n                        self.export_service.export_trf(tournament_id, path)\n                    elif report == "PGN (Partidas)":\n                        self.export_service.export_pgn(tournament_id, path)\n                    else:'
    content = content.replace(target_case, replacement_case)

    with open('c:\\PythonCurso\\Albericus\\src\\ui_settings.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('done')
except Exception as e:
    print(e)
