#!/usr/bin/env bash
set -euo pipefail

echo "Launch configuration creation..."

if [ -f .vscode/launch.json ]; then
    echo "Already exists, skipping creation of .vscode/launch.json."
    exit 0
fi

mkdir -p .vscode

cat > .vscode/launch.json << 'EOF2'
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python Debugger: Module",
            "type": "debugpy",
            "request": "launch",
            "module": "{{cookiecutter.app_package}}.app",
            "cwd": "${workspaceFolder}",
            "envFile": "${workspaceFolder}/.env",
            "args": [
                "required_value",
                "--optional-arg",
                "opt_value"
            ],
            "justMyCode": true
        }
    ]
}
EOF2

cat .vscode/launch.json

echo "Created .vscode/launch.json."
