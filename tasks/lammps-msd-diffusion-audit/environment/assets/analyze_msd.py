#!/usr/bin/env python3
"""Analyze MSD from the LAMMPS production run.

Reads msd.dat (columns: step, msd_x, msd_y, msd_z, msd_total [A^2]),
fits the Einstein relation <r^2> = 2 D t, reports the self-diffusion
coefficient D, and saves a plot.
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DT_PS = 0.002          # 2 fs timestep -> ps per step
FIT_LO, FIT_HI = 100.0, 500.0   # fit window [ps]

data = np.loadtxt("msd.dat")
step, mx, my, mz, mt = data.T
t = step * DT_PS

# ---- Einstein fit on total MSD ----
sel = (t >= FIT_LO) & (t <= FIT_HI)
slope, intercept = np.polyfit(t[sel], mt[sel], 1)
fit = slope * t + intercept
resid = mt[sel] - (slope * t[sel] + intercept)
ss_res = np.sum(resid**2)
ss_tot = np.sum((mt[sel] - mt[sel].mean())**2)
r2 = 1 - ss_res / ss_tot

# Einstein relation: MSD = 2 D t  ->  D = slope / 2
D_A2_per_ps = slope / 2.0
D_cm2_per_s = D_A2_per_ps * 1e-4     # 1 A^2/ps = 1e-4 cm^2/s

# per-component slopes as an isotropy check
sx = np.polyfit(t[sel], mx[sel], 1)[0] / 2
sy = np.polyfit(t[sel], my[sel], 1)[0] / 2
sz = np.polyfit(t[sel], mz[sel], 1)[0] / 2

print(f"fit window          : {FIT_LO:.0f}-{FIT_HI:.0f} ps")
print(f"slope (total MSD)   : {slope:.4f} A^2/ps")
print(f"R^2 of fit          : {r2:.6f}")
print(f"D = slope/2         : {D_A2_per_ps:.4f} A^2/ps")
print(f"D                   : {D_cm2_per_s:.3e} cm^2/s")
print(f"D (1e-5 cm^2/s)     : {D_cm2_per_s*1e5:.2f}")
print(f"component D (x,y,z) : {sx*1e-4:.2e}, {sy*1e-4:.2e}, {sz*1e-4:.2e} cm^2/s")

# ---- plot ----
fig, ax = plt.subplots(figsize=(6.5, 5))
ax.plot(t, mt, lw=1.6, color="navy", label="MSD (total)")
ax.plot(t, mx, lw=0.8, alpha=0.5, color="tab:red", label="MSD x")
ax.plot(t, my, lw=0.8, alpha=0.5, color="tab:green", label="MSD y")
ax.plot(t, mz, lw=0.8, alpha=0.5, color="tab:orange", label="MSD z")
ax.plot(t[sel], fit[sel], "--", color="black", lw=1.4,
        label=f"fit {FIT_LO:.0f}-{FIT_HI:.0f} ps: D = {D_cm2_per_s*1e5:.2f}e-5 cm$^2$/s")
ax.set_xlabel("time (ps)")
ax.set_ylabel(r"MSD ($\AA^2$)")
ax.set_title("TIP3P liquid water, NVT 300 K, 1 ns")
ax.legend(frameon=False, fontsize=9)
fig.tight_layout()
fig.savefig("msd_analysis.png", dpi=150)
print("saved msd_analysis.png")

# save summary to file as well
with open("diffusion_summary.txt", "w") as f:
    f.write("TIP3P liquid water, 1000 molecules, NVT 300 K, 1 ns production\n")
    f.write(f"fit window: {FIT_LO:.0f}-{FIT_HI:.0f} ps\n")
    f.write(f"slope = {slope:.4f} A^2/ps, R^2 = {r2:.6f}\n")
    f.write(f"D = {D_cm2_per_s:.3e} cm^2/s ({D_cm2_per_s*1e5:.2f} x 1e-5 cm^2/s)\n")
    f.write(f"component D (x,y,z) = {sx*1e-4:.3e}, {sy*1e-4:.3e}, {sz*1e-4:.3e} cm^2/s\n")
print("saved diffusion_summary.txt")
