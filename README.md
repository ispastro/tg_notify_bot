# tg_notify_bot

Small Telegram scheduler/notification bot using aiogram.

## Requirements
- Python 3.11+ (use a virtual environment)
- This project lists Python package dependencies in `requirements.txt`.

## Quick setup

1. Create & activate a virtual environment (PowerShell):

```powershell
python -m venv venv
.\venv\Scripts\Activate
```

2. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

3. Create a `.env` file (if required) and add your Telegram bot token and any other secrets. Example:

```
TG_BOT_TOKEN=your_token_here
DATABASE_URL=postgresql://user:pass@localhost/dbname
```

4. Run the bot (example):

```powershell
python main.py
```

## VS Code / Pylance notes

- This project includes a workspace setting that points VS Code to the project's venv: `.vscode/settings.json` -> `python.defaultInterpreterPath`.
- If Pylance reports "Import 'aiogram' could not be resolved":
  - Ensure the venv is activated and `aiogram` is installed in it (`pip show aiogram`).
  - In VS Code, run `Python: Select Interpreter` and choose the project's venv interpreter at `./venv/Scripts/python.exe`.
  - Reload the window (Developer: Reload Window) to force Pylance to re-index.

## Common issues
- `Package 'python' is not installed` when reading `requirements.txt`: don't include `python==...` in `requirements.txt`. Use `pyproject.toml`, `runtime.txt`, or document the Python version in this README.
- If you accidentally committed secrets, rotate them immediately and remove them from the repository history.

## Contributing
- Open an issue or PR if you have improvements or feature requests.

## License
- (Add your license here)
