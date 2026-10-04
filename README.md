# AI KPI Performance Manager — Version 1

This prototype is a Streamlit web app for logistics / warehouse performance management.

## What it does
- Upload KPI data from CSV
- Calculates productivity, quality, OTD, cost and safety performance
- Creates an overall performance score
- Shows Green / Amber / Red status
- Compares companies
- Shows weekly trends
- Generates management analysis
- Suggests top 3 corrective actions
- Works without AI using built-in management rules
- Can use the OpenAI Responses API when an API key and model are configured

## 1. Install Python
Use Python 3.10 or newer.

## 2. Install packages
Open Command Prompt in this folder and run:

    pip install -r requirements.txt

## 3. Start the dashboard

    streamlit run app.py

Your browser will open the KPI dashboard.

## 4. Optional: activate AI analysis

Set these environment variables before starting the app:

Windows PowerShell:

    $env:OPENAI_API_KEY="your_api_key_here"
    $env:OPENAI_MODEL="your_available_model_name"
    streamlit run app.py

The app intentionally does not hard-code an AI model because model availability can differ by API account.

## CSV format
Required columns:

- Week
- Company
- Volume
- Actual_Hours
- Target_Rate
- Errors
- OTD_pct
- Cost_Actual
- Cost_Budget
- Safety_Incidents

Use `sample_kpi_data.csv` as the template.

## Current KPI rules
- Productivity: Green >=100%, Amber >=95%, Red <95%
- Quality: Green >=99.5%, Amber >=99.0%, Red <99.0%
- OTD: Green >=98%, Amber >=95%, Red <95%
- Cost: Green >=100% of budget performance, Amber >=95%, Red <95%
- Safety: Green = 0 incidents, Amber = 1, Red >=2

These targets should be customized per company/customer in Version 2.
