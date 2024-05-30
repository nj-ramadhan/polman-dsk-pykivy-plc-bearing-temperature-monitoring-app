import pandas as pd

# Menghilangkan nilai None dari list
arr_bearing_temps = [temp for temp in db_bearing_temps if temp is not None]

# Membuat DataFrame dari list
df = pd.DataFrame({'Bearing_Temps': arr_bearing_temps})

# Menyimpan DataFrame ke file Excel
data_bearing_excel = 'bearing_temps.xlsx'
df.to_excel(data_bearing_excel, index=False)

print("Data telah disimpan ke file Excel:", data_bearing_excel)
