let
  pkgs = import <nixpkgs> {};

  # CoC Config
  cocConfig = with pkgs; writeText "coc-settings.json" (
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
pkgs.mkShell {
  shellHook = ''
    mkdir -p .vim
    ln -sf ${cocConfig} .vim/coc-settings.json
  '';

  buildInputs = with pkgs; [
    black
    poetry
    python37
    rnix-lsp
  ];
}
