"""Build v_fit_5_iterations.xlsx: 5 gradient-descent iterations on m and b for y = ReLU(m*x_hat + b).

Tabs:
  Summary            the inputs, one row per iteration (m, b, dLoss/dm, dLoss/db, loss), and two charts
  Iteration 1 ... 5  one row per data point: x̂, z, ReLU(z), ReLU'(z), the error and the two gradient
                     terms, with their averages at the top. Summary reads those averages.

Same start (m = b = 1), learning rate (0.1) and loss (MSE, with its factor 2) as v_fit.py
and one_neuron.py, so iterations 1-5 here are those scripts' epochs 0-4, and "after 5" is epoch 5.
"""
from pathlib import Path
import csv
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.chart import LineChart, ScatterChart, Reference, Series

HERE = Path(__file__).parent
LEARNING_RATE, M0, B0, ITERATIONS = 0.1, 1.0, 1.0, 5

BOLD = Font(name="Arial", bold=True); BLUE = Font(name="Arial", color="0000FF")
YELLOW = PatternFill("solid", fgColor="FFFF00"); GREY = PatternFill("solid", fgColor="EDEDED")

with open(HERE / "annacode-v.tsv", encoding="utf-8") as f:
    rows = list(csv.reader(f, delimiter="\t"))[1:]
pts = sorted((float(r[1]), float(r[2])) for r in rows)   # sorted by x so fits draw as lines
first, last = 5, 4 + len(pts)                             # data rows on each iteration tab

wb = Workbook()
sm = wb.active; sm.title = "Summary"                      # titles before charts, or charts point at 'Sheet'
tabs = [wb.create_sheet(f"Iteration {k}") for k in range(1, ITERATIONS + 1)]
D1 = "'Iteration 1'!"                                     # the data and x̂ live on Iteration 1


def inp(cell, value):
    cell.value = value; cell.font = BLUE; cell.fill = YELLOW


def header(cell, text):
    cell.value = text; cell.font = BOLD; cell.fill = GREY


# ---- Summary: inputs ----
sm["A1"] = "Gradient descent on one neuron + ReLU (V data from Anna's code)"; sm["A1"].font = Font(name="Arial", bold=True, size=13)
sm["A3"] = "learning rate α"; inp(sm["B3"], LEARNING_RATE)
sm["A4"] = "starting m"; inp(sm["B4"], M0)
sm["A5"] = "starting b"; inp(sm["B5"], B0)
sm["A6"] = "mean of x"; sm["B6"] = f"=AVERAGE({D1}$A${first}:$A${last})"
sm["A7"] = "std of x"; sm["B7"] = f"=STDEVP({D1}$A${first}:$A${last})"
sm["A8"] = "(change the yellow cells and everything updates)"

# ---- Summary: one row per iteration ----
T = 10                                                    # header row of the table
for j, h in enumerate(["iteration", "m", "b", "dLoss/dm", "dLoss/db", "loss", "points off"]):
    header(sm.cell(T, 1 + j), h)
for k in range(1, ITERATIONS + 1):
    r, tab = T + k, f"'Iteration {k}'!"
    sm[f"A{r}"] = k
    if k == 1:
        sm[f"B{r}"], sm[f"C{r}"] = "=B4", "=B5"
    else:
        sm[f"B{r}"] = f"=B{r-1}-$B$3*D{r-1}"              # m_new = m_old − α·dLoss/dm
        sm[f"C{r}"] = f"=C{r-1}-$B$3*E{r-1}"              # b_new = b_old − α·dLoss/db
    sm[f"D{r}"], sm[f"E{r}"], sm[f"F{r}"] = f"={tab}H3", f"={tab}I3", f"={tab}J3"
    sm[f"G{r}"] = f"=COUNTIF({tab}F{first}:F{last},0)"
end = T + ITERATIONS + 1                                  # the "after 5" row
sm[f"A{end}"] = f"after {ITERATIONS}"
sm[f"B{end}"] = f"=B{end-1}-$B$3*D{end-1}"
sm[f"C{end}"] = f"=C{end-1}-$B$3*E{end-1}"
z = f"(B{end}*{D1}$C${first}:$C${last}+C{end})"          # z for every point, with the final m and b
sm[f"F{end}"] = f"=SUMPRODUCT(({D1}$B${first}:$B${last}-({z}>0)*{z})^2)/COUNT({D1}$A${first}:$A${last})"
sm[f"G{end}"] = f"=SUMPRODUCT(--({z}<=0))"
for r in range(T + 1, end + 1):
    for c in "BCDEF":
        sm[f"{c}{r}"].number_format = "0.000"
for k, w in {"A": 22, "B": 11, "C": 11, "D": 11, "E": 11, "F": 11, "G": 11}.items():
    sm.column_dimensions[k].width = w

# ---- Iteration tabs ----
heads = ["x", "y", "x̂", "z = m·x̂+b", "ReLU(z)", "ReLU'(z)", "error = y − ReLU(z)",
         "−2·error·ReLU'·x̂", "−2·error·ReLU'", "error²"]
for k, ws in enumerate(tabs, start=1):
    r = T + k                                             # this iteration's row on Summary
    ws["A1"] = f"Iteration {k}"; ws["A1"].font = Font(name="Arial", bold=True, size=13)
    ws["C1"] = "m ="; ws["D1"] = f"=Summary!B{r}"
    ws["E1"] = "b ="; ws["F1"] = f"=Summary!C{r}"
    for c, h in zip("HIJ", ["dLoss/dm", "dLoss/db", "loss"]):
        header(ws[f"{c}2"], h)
        ws[f"{c}3"] = f"=AVERAGE({c}{first}:{c}{last})"; ws[f"{c}3"].font = BOLD
    ws["G3"] = "average →"; ws["G3"].font = BOLD
    for j, h in enumerate(heads):
        header(ws.cell(4, 1 + j), h)
    for i, (xv, yv) in enumerate(pts, start=first):
        if k == 1:
            inp(ws[f"A{i}"], xv); inp(ws[f"B{i}"], yv)
            ws[f"C{i}"] = f"=(A{i}-Summary!$B$6)/Summary!$B$7"
        else:
            ws[f"A{i}"], ws[f"B{i}"], ws[f"C{i}"] = f"={D1}A{i}", f"={D1}B{i}", f"={D1}C{i}"
        ws[f"D{i}"] = f"=$D$1*C{i}+$F$1"
        ws[f"E{i}"] = f"=MAX(0,D{i})"
        ws[f"F{i}"] = f"=IF(D{i}>0,1,0)"
        ws[f"G{i}"] = f"=B{i}-E{i}"
        ws[f"H{i}"] = f"=-2*G{i}*F{i}*C{i}"
        ws[f"I{i}"] = f"=-2*G{i}*F{i}"
        ws[f"J{i}"] = f"=G{i}^2"
    for c in "ABCDEFGHIJ":
        ws.column_dimensions[c].width = 13
    ws.column_dimensions["G"].width = 18
    ws.freeze_panes = "A5"

# ---- Charts on Summary ----
ch = LineChart(); ch.title = "Loss vs iteration"; ch.y_axis.title = "loss"; ch.x_axis.title = "iteration"
ch.add_data(Reference(sm, min_col=6, min_row=T, max_row=end), titles_from_data=True)
ch.set_categories(Reference(sm, min_col=1, min_row=T + 1, max_row=end))
ch.legend = None; ch.height, ch.width = 7, 12
sm.add_chart(ch, f"A{end + 2}")

sc = ScatterChart(); sc.title = "Data and fit"; sc.x_axis.title = "x"; sc.y_axis.title = "y"
xs = Reference(tabs[0], min_col=1, min_row=first, max_row=last)
s = Series(Reference(tabs[0], min_col=2, min_row=first, max_row=last), xs, title="V data")
s.marker.symbol = "circle"; s.marker.size = 4; s.graphicalProperties.line.noFill = True
sc.series.append(s)
for k in (1, ITERATIONS):
    s = Series(Reference(tabs[k - 1], min_col=5, min_row=first, max_row=last), xs, title=f"fit, iteration {k}")
    s.marker.symbol = "none"
    if k == 1: s.graphicalProperties.line.dashStyle = "dash"
    sc.series.append(s)
sc.height, sc.width = 7, 12
sm.add_chart(sc, f"I{end + 2}")

for ws in wb:
    for row in ws.iter_rows():
        for c in row:
            if c.font.name != "Arial":
                c.font = Font(name="Arial", bold=c.font.bold, color=c.font.color, size=c.font.size)
out = HERE / "v_fit_5_iterations.xlsx"
wb.save(out)
print("wrote", out)
