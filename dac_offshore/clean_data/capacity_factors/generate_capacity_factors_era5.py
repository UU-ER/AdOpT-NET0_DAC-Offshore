from scipy.interpolate import interp1d

import xarray as xr
import pandas as pd
import numpy as np
from metpy.calc import wind_speed
from metpy.units import units

def roundPartial (value, resolution):
    """
    Rounds number to decimals

    Rounds to grid level of JRC dataset

    :param float value: value to round
    :param float resolution: resolution of rounding
    :return float rounded value: result value
    """
    return round (value / resolution) * resolution

def convert_era5_data(year, lon, lat):
    lat = roundPartial(lat, 0.25)
    lon = roundPartial(lon, 0.25)
    ds = xr.open_dataset(path_wind_speed_data, engine='cfgrib', backend_kwargs={'indexpath': ''})
    ds = ds.sel(time=str(year))
    time_index = ds.time.to_pandas()
    ws = {}
    u100 = ds.u100.sel(longitude=lon, latitude=lat).to_numpy()
    v100 = ds.v100.sel(longitude=lon, latitude=lat).to_numpy()
    ws['100'] = wind_speed(u100 * units.m / units.s, v100 * units.m / units.s)
    answer = {}
    answer['longitude'] = lon
    answer['latitude'] = lat
    answer['altitude'] = 0
    answer['dataframe'] = pd.DataFrame(index=time_index)
    for height in ws:
        answer['dataframe']['ws' + str(height)] = ws[height]

    return answer

climate_years = [1995, 2008, 2009]
path_wind_cluster_data = '/dac_offshore/clean_data/nodes/nodes.xlsx'
path_wind_speed_data = '/Users/8051917/Downloads/data.grib'
path_power_curves = '/adopt_net0/database/templates/technology_data/RES/WT_data/WT_data.csv'

# Load wind park data and power curves to dataframe
power_curves = pd.read_csv(path_power_curves, delimiter=';')
power_curve = power_curves[power_curves['TurbineName'] == 'WindTurbine_Offshore_9500']
cut_in = power_curve.iloc[0]['CutInMS']
cut_out = power_curve.iloc[0]['CutOffMS']

wind_park_data = pd.read_excel(path_wind_cluster_data)
wind_park_data = wind_park_data[wind_park_data['Type'] == 'offshore_new']

for climate_year in climate_years:

    path_save_profile = '/Users/8051917/PycharmProjects/AdOpT-NET0_DAC-Offshore/dac_offshore/clean_data/capacity_factors/wind_offshore' + str(climate_year) + '.csv'

    # Loop through each wind park
    cap_factors = pd.DataFrame()
    for index, wind_park in wind_park_data.iterrows():
        lon = wind_park['x']
        lat = wind_park['y']

        name = wind_park['Node']
        print(name)

        rated_power_turbine_model =  power_curve.iloc[0]['RatedPowerkW']

        ws = convert_era5_data(climate_year, lon, lat)

        ws100 = ws['dataframe'].ws100


        hub_height = 150
        alpha = 0.11
        ws_hubheight = ws100 * (hub_height / 100) ** alpha

        # Make power curve
        x = np.linspace(0, 35, 71)
        y = power_curve.iloc[:,13:84]
        y = y.to_numpy()

        f = interp1d(x, y)
        ws_hubheight[ws_hubheight < 0] = 0
        ws_hubheight[ws_hubheight > 35] = 35

        capacity_factor = f(ws_hubheight) / rated_power_turbine_model
        capacity_factor = capacity_factor[0]
        capacity_factor[ws_hubheight < cut_in] = 0
        capacity_factor[ws_hubheight > cut_out] = 0

        cap_factors[name] = capacity_factor

    cap_factors = cap_factors[0:8760]
    cap_factors.to_csv(path_save_profile)
#
# cap_factors = pd.DataFrame.from_dict(cap_factors, orient='index', columns=['cf'])
# cap_factors.to_csv(path_save_profile + '00_capacity_factors_' + str(year) + '.csv')
