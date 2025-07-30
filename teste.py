import xarray as xr
ds = xr.open_dataset('data/processed/data_0.nc', engine='netcdf4')
print(f'Latitude: {ds['latitude'].values}')
print(f'Longitude: {ds['longitude'].values}')