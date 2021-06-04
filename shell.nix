with import <nixpkgs> {};
let
  # CoC Config
  cocConfig = writeText "coc-settings.json" (
    builtins.toJSON {
      "python.formatting.provider" = "black";
      "python.linting.enabled" = true;
      "python.linting.flake8Enabled" = true;
      "python.linting.mypyEnabled" = true;
      "python.linting.pylintEnabled" = false;
      "python.pythonPath" = ".venv/bin/python";
    }
  );
in
mkShell rec {
  name = "impurePythonEnv";
  venvDir = "./.venv";

  buildInputs = [
    python3Packages.python
    python3Packages.venvShellHook

    # Python Dependencies
    python3Packages.psycopg2

    postgresql_11
    rnix-lsp
  ];

  # Run this command, only after creating the virtual environment
  postVenvCreation = ''
    unset SOURCE_DATE_EPOCH
    pip install -r requirements.txt
    pip install -r dev-requirements.txt
  '';

  # Now we can execute any commands within the virtual environment.
  # This is optional and can be left out to run pip manually.
  postShellHook = ''
    # allow pip to install wheels
    unset SOURCE_DATE_EPOCH

    mkdir -p .vim
    ln -sf ${cocConfig} .vim/coc-settings.json
  '';
}
