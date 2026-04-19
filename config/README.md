# Configuration Files

This directory contains configuration templates for API access.

## Mosqlimate API (InfoDengue)

To use the InfoDengue API accessor, you need an API key from Mosqlimate.

### Setup

1. Copy the example file:
   ```bash
   cp config/mosqlimate.env.example config/mosqlimate.env
   ```

2. Edit `config/mosqlimate.env` and add your API key:
   ```
   MOSQLIMATE_API_KEY=your_actual_api_key_here
   ```

3. The accessor will automatically load the key from:
   - Environment variable: `MOSQLIMATE_API_KEY`
   - Config file: `~/.nanobot/config/mosqlimate.env`
   - Config file: `config/mosqlimate.env`

### Security

**IMPORTANT**: Never commit your actual API key to GitHub!

- `mosqlimate.env` is listed in `.gitignore` and will not be committed
- Only `mosqlimate.env.example` (without real keys) should be committed
- Keep your API key private and do not share it

### Obtaining an API Key

Visit https://mosqlimate.org/ to create an account and request API access.

---

## Copernicus Climate Data Store (CDS)

To use the Copernicus CDS accessor, you need a free account from the Copernicus Climate Data Store.

### Setup

1. Register at https://cds.climate.copernicus.eu/

2. Get your API key from your profile page

3. Configure credentials in one of these ways:

   **Option A: ~/.cdsapirc file**
   ```
   url: https://cds.climate.copernicus.eu/api
   key: YOUR_API_KEY_HERE
   ```

   **Option B: Environment variables**
   ```bash
   export CDSAPI_URL=https://cds.climate.copernicus.eu/api
   export CDSAPI_KEY=your_api_key_here
   ```

   **Option C: Config file**
   ```bash
   cp config/cdsapi.env.example ~/.nanobot/config/cdsapi.env
   # Edit and add your key
   ```

4. Accept the Terms of Use for each dataset you want to access:
   - Go to https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels
   - Click "Download" tab
   - Accept Terms of Use

### Security

**IMPORTANT**: Never commit your CDS credentials to GitHub!

- `~/.cdsapirc` and `cdsapi.env` are protected by `.gitignore`
- Only `cdsapi.env.example` (template without real credentials) is committed

### Required Dependencies

```bash
pip install cdsapi xarray netCDF4
```

### Available Datasets

- ERA5 hourly data on single levels
- ERA5 hourly data on pressure levels  
- ERA5-Land hourly data

### Common Variables for Epidemiology

- `2m_temperature`: Air temperature at 2 meters
- `total_precipitation`: Total precipitation
- `relative_humidity`: Relative humidity
- `2m_dewpoint_temperature`: For humidity calculations
