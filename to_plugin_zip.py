import os


def run():
    # Annahme, dass hier eine Plugin-ZIP erstellt werden soll
    from submodules.tools.create_plugin_zip import CreatePluginZip

    repo_location = os.path.dirname(__file__)  # dieses Verzeichnis
    zip_file_name = os.path.basename(repo_location) # Wie soll die ZIP-Datei heißen?
    # Wo soll diese ZIP-Datei gespeichert werden?
    destination_zip_file = os.path.join(repo_location, zip_file_name + ".zip")

    ignore_paths = [
        # root folder
        ".idea", ".editorconfig", ".gitignore", ".gitignore", ".git", ".vscode",
        ".mypy_cache",
        # submodules/tools
        "submodules/tools/.git", "submodules/tools/.gitignore", "submodules/tools/.editorconfig",
        # submodules/core
        "submodules/core/.git", "submodules/core/.gitignore", "submodules/core/.editorconfig",
    ]

    obj = CreatePluginZip(zip_file_name,
                          repo_location,
                          destination_zip_file,
                          ignore_paths=ignore_paths,
                          overwrite=True)


if __name__ == "__main__":
    run()
