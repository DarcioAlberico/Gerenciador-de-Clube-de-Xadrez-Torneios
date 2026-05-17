import sys

try:
    with open('c:\\PythonCurso\\Albericus\\src\\ui_settings.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    target = '''            self.db.save_app_settings(
                {
                    "appearance_mode": appearance_values[appearance_option.get()],
                    "default_export_dir": str(export_dir),
                    "backup_dir": str(backup_dir),
                }
            )'''
            
    replacement = '''            self.db.save_app_settings(
                {
                    "appearance_mode": appearance_values[appearance_option.get()],
                    "default_export_dir": str(export_dir),
                    "backup_dir": str(backup_dir),
                    "cloud_sync_dir": cloud_dir_entry.get().strip(),
                }
            )'''
            
    content = content.replace(target, replacement)
    
    with open('c:\\PythonCurso\\Albericus\\src\\ui_settings.py', 'w', encoding='utf-8') as f:
        f.write(content)
        
    print('done persist update')
except Exception as e:
    print('error', e)
