# VSCode Debugging

## Launch configuration

Set up the debugger in VSCode to debug the Python code by adding the following to the `.vscode/launch.json` file:

Minimal set of configuration options:

```json
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
            ],
            "justMyCode": true
        }
    ]
}
```

Extended set of configuration options:

```json
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
            "python": "${command:python.interpreterPath}",

            "console": "integratedTerminal",  // better for CLI apps
            "autoReload": {
                "enable": true  // reload of the debugger when changes are made
            },
            "internalConsoleOptions": "neverOpen",

            "args": [
                "required_value",
                "--optional-arg",
                "opt_value"
            ],

            "env": {
                "PYTHONPATH": "${workspaceFolder}/src",
                "PYTHONUNBUFFERED": "1",  // log output appear immediately
                "PYTHONASYNCIODEBUG": "1"  // asyncio debugging
            },

            "justMyCode": true,
            "subProcess": true  // debugger follows subprocesses
        }
    ]
}
```

## Using `debugpy` instead of `python` debugger type

https://devblogs.microsoft.com/python/python-in-visual-studio-code-february-2024-release/

From Jan 2024, ensure you are using the new Python Debugger extension, replace `"type": "python"` with `"type": "debugpy"` in your launch.json configuration file. In the future, the Python extension will no longer offer debugging support, and we will transition all debugging support to the Python Debugger extension.


## References

https://code.visualstudio.com/docs/debugtest/debugging-configuration

https://code.visualstudio.com/docs/python/debugging

https://code.visualstudio.com/docs/python/debugging#_python-debugger-extension
