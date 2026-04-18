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
