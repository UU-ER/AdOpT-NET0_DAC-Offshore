from pathlib import Path  # import Path from pathlib module
import os  # import os module
import pandas as pd

directory = Path(r'C:\Users\6574114\OneDrive - Universiteit Utrecht\PhD Jan\Papers\DOSTA - HydrogenOffshore\00_raw_data\climate_data')  # set directory path


summary = {}
summary["1995"] = {}
summary["2008"] = {}
summary["2009"] = {}
for root, _, files in os.walk(directory):
    for filename in files:
        idx = filename.replace(".csv", "")
        idx = idx.split("_")
        nuts_region = idx[0]
        year = idx[1]
        summary[year][nuts_region] = pd.read_csv(os.path.join(root, filename), index_col=0).mean().to_dict()


records = []
for year, regions in summary.items():
    for region, values in regions.items():
        for key, val in values.items():
            records.append((year, region, key, val))

df = pd.DataFrame(records, columns=['year', 'region', 'variable', 'value'])
df.to_excel("climate_data.xlsx")