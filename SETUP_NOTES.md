# Setup Notes

## Manual Steps Required

### Python Virtual Environment Setup

The Python virtual environment creation requires `python3.12-venv` package to be installed.

**Run this command manually**:
```bash
sudo apt install python3.12-venv
```

Then create the virtual environment:
```bash
cd /home/kasadis/portfolio-ai/backend
python3 -m venv .venv
```

After the venv is created, activate it and install dependencies:
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

## Next Steps After Manual Setup

Continue with task 0.12 onwards from the task list.
