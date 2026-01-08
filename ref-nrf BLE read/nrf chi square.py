import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import chi2
from matplotlib.widgets import Slider

# Initial setup for degrees of freedom
initial_df = 4

# Create figure and axis objects
fig, (ax_pdf, ax_cdf) = plt.subplots(1, 2, figsize=(12, 5))
plt.subplots_adjust(bottom=0.25)

# X range for the chi-square distribution
x = np.linspace(0, 20, 1000)

# Initial PDF and CDF plots
pdf, = ax_pdf.plot(x, chi2.pdf(x, initial_df), color="blue")
cdf, = ax_cdf.plot(x, chi2.cdf(x, initial_df), color="green")

# Set plot titles and labels
ax_pdf.set_title("Chi-square Probability Density Function")
ax_pdf.set_xlabel("x")
ax_pdf.set_ylabel("Density")
ax_cdf.set_title("Chi-square Cumulative Distribution Function")
ax_cdf.set_xlabel("x")
ax_cdf.set_ylabel("Cumulative Probability")

# Create slider axis and slider
ax_slider = plt.axes([0.25, 0.1, 0.5, 0.03])
df_slider = Slider(ax_slider, "Degrees of Freedom", 1, 10, valinit=initial_df, valstep=1)

# Update function to redraw the plots
def update(val):
    df = df_slider.val
    pdf.set_ydata(chi2.pdf(x, df))
    cdf.set_ydata(chi2.cdf(x, df))
    fig.canvas.draw_idle()

# Attach the update function to the slider
df_slider.on_changed(update)

plt.show()
