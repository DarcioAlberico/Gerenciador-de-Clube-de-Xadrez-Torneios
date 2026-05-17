import sys

try:
    with open('c:\\PythonCurso\\Albericus\\src\\ui_settings.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. Insert UI elements for cloud sync dir
    ui_elements = '''
        ctk.CTkLabel(settings_panel, text="Pasta de Nuvem (Google Drive/Dropbox)").grid(
            row=8,
            column=0,
            padx=16,
            pady=(8, 4),
            sticky="w",
        )
        cloud_dir_entry = ctk.CTkEntry(settings_panel, width=320)
        cloud_dir_entry.grid(row=9, column=0, padx=16, pady=(0, 8), sticky="ew")
        cloud_dir_entry.insert(0, str(settings.get("cloud_sync_dir", "")))

        def choose_cloud_dir() -> None:
            directory = filedialog.askdirectory(
                title="Escolha a pasta sincronizada em nuvem",
                initialdir="/",
            )
            if directory:
                cloud_dir_entry.delete(0, "end")
                cloud_dir_entry.insert(0, directory)

        ctk.CTkButton(settings_panel, text="Escolher nuvem", command=choose_cloud_dir).grid(
            row=10,
            column=0,
            padx=16,
            pady=(0, 14),
            sticky="ew",
        )
'''
    
    target_ui = '        ctk.CTkLabel(\n            settings_panel,\n            text="Seguranca operacional",'
    content = content.replace(target_ui, ui_elements + '\n' + target_ui)
    
    # Update row indices for security block
    content = content.replace('row=8, column=0, padx=16, pady=(6, 4)', 'row=11, column=0, padx=16, pady=(6, 4)', 1) # Seguranca operacional
    content = content.replace('row=9,', 'row=12,', 1) # Operador local label
    content = content.replace('row=10,', 'row=13,', 1) # operator entry
    content = content.replace('row=11,', 'row=14,', 1) # Perfil label
    content = content.replace('row=12,', 'row=15,', 1) # role option
    content = content.replace('row=13,', 'row=16,', 1) # Manter ultimos backups label
    content = content.replace('row=14,', 'row=17,', 1) # retention entry

    # Note: we must also get cloud_dir_entry.get() when saving settings.
    target_payload = '''            "backup_dir": backup_dir_entry.get(),
            "operator_name": operator_name_entry.get(),'''
    replacement_payload = '''            "backup_dir": backup_dir_entry.get(),
            "cloud_sync_dir": cloud_dir_entry.get(),
            "operator_name": operator_name_entry.get(),'''
    content = content.replace(target_payload, replacement_payload)

    with open('c:\\PythonCurso\\Albericus\\src\\ui_settings.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('done ui_settings replace')
except Exception as e:
    print('error', e)
