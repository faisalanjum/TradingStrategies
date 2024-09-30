url_readBacktest        = f"https://www.quantconnect.com/api/v2/backtests/read"
url_readProject         = f"https://www.quantconnect.com/api/v2/projects/read"
url_listProjectBacktest = f"https://www.quantconnect.com/api/v2/backtests/list"

# Your QuantConnect API credentials
USER_ID = '92090'
API_TOKEN = '7df20f89e389d894c09528956e8bbd1c8a76946c12d56dd8624a6705825243ef'

import requests
import hashlib
import time
import base64
import pandas as pd

# Function to create headers with appropriate authentication
def get_authenticated_headers():
    timestamp = str(int(time.time()))
    data_string = f"{API_TOKEN}:{timestamp}"
    hashed_token = hashlib.sha256(data_string.encode('utf-8')).hexdigest()
    auth_string = f"{USER_ID}:{hashed_token}"
    api_token = base64.b64encode(auth_string.encode('utf-8')).decode('ascii')
    return {
        'Authorization': f'Basic {api_token}',
        'Timestamp': timestamp
    }


def list_backtests(project_id):
    response = requests.post(url_listProjectBacktest, headers=get_authenticated_headers(), data={'projectId': project_id, 'includeStatistics': True})
    if response.status_code == 200:
        return response.json().get('backtests', [])
    else:
        print("Failed to list backtests:", response.status_code, response.text)
        return []
    
backtests = list_backtests(19014068)
backtest_metrics = ['backtestId', 'alpha',  'beta', 'compoundingAnnualReturn', 'drawdown', 'lossRate', 'netProfit', 'parameters', 'psr', 'sortinoRatio', 'trades' ,'treynorRatio', 'winRate'] 


df = pd.DataFrame([[bkt.get(metric, None) for metric in backtest_metrics] for bkt in backtests], columns=backtest_metrics)
df.index = [bkt['name'] for bkt in backtests]

def fetch_backtest_result(project_id, backtest_id, key = None):
    response = requests.post(url_readBacktest, headers=get_authenticated_headers(), data={'projectId': project_id, 'backtestId': backtest_id})
    if response.status_code == 200:
        
        if key is not None:
            return response.json()['backtest'][key]
        else:
            return response.json()['backtest']
    else:
        print("Failed to retrieve backtest results:", response.status_code, response.text)
        return {}
    
backtest_result = fetch_backtest_result(project_id=19016182, backtest_id='fe286f90bb0da4738404135abd17136d')



# Convert to DataFrame
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# Convert to DataFrame
equity_values = backtest_result['charts']['Strategy Equity']['series']['Equity']['values']
return_values = backtest_result['charts']['Strategy Equity']['series']['Return']['values']

# Assuming equity_values has 5 elements and return_values has 2
equity_df = pd.DataFrame(equity_values, columns=['Timestamp', 'Open', 'High', 'Low', 'Close'])
return_df = pd.DataFrame(return_values, columns=['Timestamp', 'Return'])

# Convert Unix timestamps to human-readable dates
equity_df['Date'] = pd.to_datetime(equity_df['Timestamp'], unit='s')
return_df['Date'] = pd.to_datetime(return_df['Timestamp'], unit='s')

# Create a subplot with 2 rows
fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                    vertical_spacing=0.05, subplot_titles=('Equity', 'Returns'),
                    row_heights=[0.7, 0.3])

# Add Candlestick for Equity
fig.add_trace(go.Candlestick(x=equity_df['Date'],
                             open=equity_df['Open'], high=equity_df['High'],
                             low=equity_df['Low'], close=equity_df['Close'],
                             name='Equity', legendgroup='Equity'), row=1, col=1)

# Add Bars for Returns on the second subplot
fig.add_trace(go.Bar(x=return_df['Date'], y=return_df['Return'],
                     name='Returns', marker_color='blue', legendgroup='Returns'), row=2, col=1)

# Layout settings
fig.update_layout(
    xaxis_title='Date',
    yaxis_title='Equity',
    yaxis2_title='Returns',
    legend_title='Legend',
    hovermode='x unified',
    height=800,  # Adjust height here
    width=1200,  # Adjust width here
    title='Strategy Analysis'
)

# Set y-axis to be percentage for returns
fig.update_yaxes(tickformat=".0%", row=2, col=1)

# Show the plot in Streamlit using full container width
st.plotly_chart(fig, use_container_width=True)