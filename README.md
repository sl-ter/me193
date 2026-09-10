# ME193 Robotics Libs

Python code and libraries for ME193 (AI in Mobile Robotics), controlling LEGO Education hardware via the [`legoeducation`](https://github.com/LEGO/LEGOEducation) library.

## Setup

```bash
# 1. Create a virtual environment
python3 -m venv venv

# 2. Activate it
source venv/bin/activate      # Mac/Linux
venv\Scripts\activate.bat     # Windows

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

## Usage

Update `card_color` and `card_serial` in `spin_motor.py` to match your Connection Card, then:

```bash
python spin_motor.py
```

This connects to a single motor and spins it clockwise at 50% speed for 3 seconds.
