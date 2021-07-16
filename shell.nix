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
  buildInputs = [
    python39
    python39Packages.poetry

    # Python Dependencies
    python39Packages.psycopg2
    python39Packages.python-olm
    python39Packages.python_magic

    rnix-lsp
  ];

  # Now we can execute any commands within the virtual environment.
  # This is optional and can be left out to run pip manually.
  shellHook = ''
    # allow pip to install wheels
    unset SOURCE_DATE_EPOCH

    mkdir -p .vim
    ln -sf ${cocConfig} .vim/coc-settings.json
  '';
}
