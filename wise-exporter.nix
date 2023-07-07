{ pkgs ? import <nixpkgs> { } }:
pkgs.python3.pkgs.buildPythonApplication {
  pname = "wise-exporter";
  version = "0.0.1";
  src = ./wise-exporter;
  propagatedBuildInputs = [
    pkgs.python3.pkgs.rsa
  ];
  nativeBuildInputs = [
    pkgs.python3.pkgs.black
    pkgs.python3.pkgs.mypy
    pkgs.ruff
  ];

  doCheck = true;
  checkPhase = ''
    mypy wise_exporter
    black --check .
    ruff .
  '';
}