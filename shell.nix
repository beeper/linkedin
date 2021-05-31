{ pkgs ? import <nixpkgs> {} }: with pkgs;
pkgs.mkShell {
  propagatedBuildInputs = with python38Packages; [
    black
    poetry
    python37
    rnix-lsp
  ];
}
