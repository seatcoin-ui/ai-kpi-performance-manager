# AI KPI Performance Manager — Version 2

## New in V2
- Upload Excel (.xlsx/.xls) or CSV
- Professional executive dashboard
- Company and week filters
- Green / Amber / Red status
- Productivity
- RTR / Efficiency
- Quality
- On-Time Delivery
- Forecast accuracy
- Cost performance
- Safety
- Actual vs budget hours
- Forecast vs actual volume
- Weekly company trends
- Error Pareto
- AI management review
- CSV export of calculated KPI results
- Company-specific KPI thresholds through the `Targets` sheet

## Recommended workflow
1. Open `AI_KPI_Data_Template_v2.xlsx`.
2. Replace the demo rows in the `Data` sheet with your data.
3. Adjust company targets in `Targets` if needed.
4. Add error categories in `Errors` if you want Pareto analysis.
5. Save the file.
6. Upload it directly in the online KPI dashboard.

## Update your existing Streamlit app
Your current GitHub repository can be reused.

Replace / upload these files:
- `app.py`
- `requirements.txt`
- `AI_KPI_Data_Template_v2.xlsx`

Commit the changes. Streamlit Community Cloud normally redeploys automatically.

## Optional OpenAI analysis
The app works without an API key using rule-based management analysis.

For real AI analysis, add these in Streamlit:
App -> Settings -> Secrets

```toml
OPENAI_API_KEY = "your-key"
OPENAI_MODEL = "gpt-6-astra"
```

Never put your API key in GitHub.

The app uses the OpenAI Responses API.
