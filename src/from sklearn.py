from sklearn.linear_model import LinearRegression
import numpy as np
from datetime import datetime, timedelta

# Your data
dates = ['10/05/2025', '11/05/2025', '12/05/2025']
values = [12949, 12297, 10611]

# Convert dates to numbers
base_date = datetime.strptime('10/05/2025', '%d/%m/%Y')
days = [(datetime.strptime(d, '%d/%m/%Y') - base_date).days for d in dates]

# Fit regression model
model = LinearRegression()
model.fit(np.array(days).reshape(-1, 1), values)

# Get the slope (a) and intercept (b)
a = model.coef_[0]
b = model.intercept_

# Calculate the day when value = 0
day_zero_value = -b / a
date_zero_value = base_date + timedelta(days=day_zero_value)

print(f"La valeur atteindra 0 le {date_zero_value.strftime('%d/%m/%Y')} (jour = {day_zero_value:.2f})")
