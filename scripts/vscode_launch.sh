#!/bin/bash

echo "Launch configuration creation..."

# Check if launch.json already exists
if [ -f .vscode/launch.json ]; then
    echo "Already exists, skipping creation of .vscode/launch.json."
    exit 0
fi

# Create .vscode directory if it doesn't exist
mkdir -p .vscode

# Create launch.json file
cat > .vscode/launch.json << 'EOF'
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python Debugger: Module",
            "type": "debugpy",
            "request": "launch",
            "module": "my_project.app",
            "cwd": "${workspaceFolder}",
            "envFile": "${workspaceFolder}/.env",
            "args": [
                "required_value",
                "--optional-arg",
                "opt_value"
            ]
            "justMyCode": true
        }
    ]
}
EOF

cat .vscode/launch.json

echo "Created .vscode/launch.json."

