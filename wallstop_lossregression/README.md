# Wall stop loss regression — 10/29

Fit a straight line `speed = m·reflection + b` to the wall-stopping run by
**gradient descent** on mean squared error, first in Excel (one row per
epoch) and then in Python. This follows the class handout "Solving things by
minimizing a loss or error".

## Data

`annacode-data.csv` is the logged run from Anna's site: time, Color Sensor
reflection, and Double Motor speed over 5 approaches to the wall. The fit uses
only the 120 rows where **reflection > 0 and speed ≠ 0**, which is the stretch
where the robot sees the wall and is still slowing. Rows with reflection 0 are
the robot speeding up before the sensor sees anything. Rows with speed 0 are
the robot sitting still. Neither kind says anything about how speed depends
on reflection.

## Files

- `gradient_descent.xlsx` has one formula row per epoch: `m`, `b`, `dm`, `db`, loss.
  - **Example raw x / Example centered x:** the handout's 4-point example (y = 2x).
  - **Wall raw x:** reflection used as-is. It needs learning rate ≤ 0.0004 and is still far off after 1000 rows.
  - **Wall standardized x:** x̂ = (x − mean)/std, learning rate 0.5. It converges in about 20 rows, then converts m and b back to reflection units.
  - Yellow cells are inputs. Every tab has `SLOPE()`/`INTERCEPT()` cells to check against.
- `build_workbook.py` regenerates the workbook. It needs `openpyxl`. Excel calculates the formulas when the file is opened.
- `wall_fit.py` is the same fit in numpy, like the handout's `run()`.

```bash
../venv/bin/python wall_fit.py
../venv/bin/python build_workbook.py
```

## Result

**speed ≈ 0.153 × reflection − 17.6** (loss 8.7). Gradient descent on
standardized x matches `np.polyfit` / Excel `SLOPE`/`INTERCEPT` exactly.

## Why standardize instead of only centering?

The handout's example x only spans 6–11, so subtracting the mean is enough
there. Reflection spans 6–96, a standard deviation of about 34. The step size
for m scales with x², so the learning rate has to be below roughly 2/var(x),
about 0.0017. At that rate b barely moves, and you'd need thousands of rows.
Dividing by the std puts m and b on the same scale, so a learning rate of 0.5
works for both. Anna's code normalizes for the same reason. To convert back:
`m_raw = m/std` and `b_raw = b − m·mean/std`.

Note: the handout says the centered intercept becomes `mean(x) + b`. The
algebra gives `y = m(x − x̄) + b = mx + (b − m·x̄)`, so the correct form is
`b − m·x̄`.
