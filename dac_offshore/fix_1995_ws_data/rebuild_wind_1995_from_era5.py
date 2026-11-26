from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from scipy.interpolate import interp1d

from mes_north_sea.preprocessing.utilities import CalculateReGeneration


def roundPartial(value, resolution):
    return round(value / resolution) * resolution


def ws100(lat, lon):
    u100 = ds.u100.sel(longitude=roundPartial(lon, 0.25), latitude=roundPartial(lat, 0.25)).to_numpy()
    v100 = ds.v100.sel(longitude=roundPartial(lon, 0.25), latitude=roundPartial(lat, 0.25)).to_numpy()
    return np.sqrt(u100 ** 2 + v100 ** 2)


climate_year = 1995
path_wind_speed_data = '/Users/8051917/Downloads/data.grib'
path_profiles = './dac_offshore/clean_data/production_profiles_re/production_profiles_re' + str(climate_year) + '.csv'
path_cap_factors = './dac_offshore/clean_data/capacity_factors/wind_onshore' + str(climate_year) + '.csv'

ds = xr.open_dataset(path_wind_speed_data, engine='cfgrib', backend_kwargs={'indexpath': ''})
ds = ds[['u100', 'v100']].sel(time=str(climate_year)).load()

production_profiles = pd.read_csv(path_profiles, index_col=0, header=[0, 1])

# Wind onshore
cap_nuts = pd.read_csv('./mes_north_sea/clean_data/installed_capacities/capacities_nuts.csv', index_col=0)
nodekeys_nuts = pd.read_csv('./mes_north_sea/nodekeys/nuts2nodes.csv')

production_profiles_nuts = pd.DataFrame()
ReCalc = CalculateReGeneration()
for idx, nuts_region in cap_nuts.iterrows():
    location = {}
    if nuts_region['NUTS_ID'] == 'DK01':
        location["lat"] = 55.8
        location["lon"] = 12.43
    elif nuts_region['NUTS_ID'] == 'DK05':
        location["lat"] = 56.96
        location["lon"] = 9.817
    else:
        location["lat"] = nuts_region['lat']
        location["lon"] = nuts_region['lon']
    location["alt"] = 10

    climate_data = pd.DataFrame(index=pd.date_range(start=str(climate_year) + '-01-01 00:00',
                                                    end=str(climate_year) + '-12-31 23:00', freq='1h'))
    climate_data["ws100"] = ws100(location["lat"], location["lon"])

    ReCalc.fit_technology_performance(climate_data, 'Wind', location)
    production_profiles_nuts[nuts_region['NUTS_ID']] = \
        ReCalc.processed_coeff.time_dependent_full["capfactor"] * nuts_region['Capacity_Wind_on_2030']

production_profiles_nodes = production_profiles_nuts.T.reset_index().merge(nodekeys_nuts[['NUTS_ID', 'Node']],
                                                                           left_on='index', right_on='NUTS_ID')
production_profiles_nodes = production_profiles_nodes.drop(columns=['NUTS_ID', 'index'])
production_profiles_nodes = production_profiles_nodes.groupby('Node').sum().T[0:8760]

for node in production_profiles_nodes.columns:
    production_profiles[(node, 'Wind onshore')] = production_profiles_nodes[node].to_numpy()
    production_profiles[(node, 'total')] = production_profiles[node].drop(columns='total').sum(axis=1)

# Wind offshore (same method as DataPreprocessing/utilities/generate_offshore_windfarm_production.py)
power_curves = pd.read_csv('./adopt_net0/database/templates/technology_data/RES/WT_data/WT_data.csv', delimiter=';')
alpha = 0.11

cap_offshore = pd.read_csv(Path(__file__).parent / 'WindFarms_v4.csv', delimiter=';')
cap_offshore = cap_offshore[cap_offshore['NODE_2'].notna()]

for node in cap_offshore['NODE_2'].unique():
    cap_at_node = cap_offshore[cap_offshore['NODE_2'] == node]
    total_generation = np.zeros(8760)
    for idx, park in cap_at_node.iterrows():
        power_curve = power_curves[power_curves['TurbineName'] == park['TURBINE_TYPE_POWER']]
        cut_in = power_curve.iloc[0]['CutInMS']
        cut_out = power_curve.iloc[0]['CutOffMS']
        rated_power_turbine_model = power_curve.iloc[0]['RatedPowerkW']
        f = interp1d(np.linspace(0, 35, 71), power_curve.iloc[:, 13:84].to_numpy())

        if park['YEAR'] < 2010:
            hub_height = 80
        elif park['YEAR'] < 2020:
            hub_height = 100
        else:
            hub_height = 120

        ws_hubheight = ws100(float(park['lat']), float(park['lon'])) * (hub_height / 100) ** alpha
        ws_hubheight[ws_hubheight < 0] = 0
        ws_hubheight[ws_hubheight > 35] = 35
        capacity_factor = f(ws_hubheight)[0] / rated_power_turbine_model
        capacity_factor[ws_hubheight < cut_in] = 0
        capacity_factor[ws_hubheight > cut_out] = 0
        capacity_factor = capacity_factor * 0.95
        total_generation = total_generation + float(park['POWER_MW']) * capacity_factor[0:8760]

    production_profiles[(node, 'Wind offshore')] = total_generation
    production_profiles[(node, 'total')] = production_profiles[node].drop(columns='total').sum(axis=1)

production_profiles.to_csv(path_profiles)

# Capacity factors
caps = pd.read_csv('./mes_north_sea/clean_data/installed_capacities/capacities_node.csv', index_col=[0])
caps = caps[(caps['Technology'] == 'Wind Onshore') & (caps['Node'] != 'NO1')]

cap_factors = pd.read_csv(path_cap_factors, index_col=0)
for idx, row in caps.iterrows():
    cap_factors[row['Node']] = production_profiles[(row['Node'], 'Wind onshore')].to_numpy() / row['Capacity our work']

cap_factors.to_csv(path_cap_factors)
