import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import hashlib
import time
import base64
import re
import asyncio
import aiohttp


# Environment variables for credentials
USER_ID = '92090'
API_TOKEN = '7df20f89e389d894c09528956e8bbd1c8a76946c12d56dd8624a6705825243ef'

# Define API endpoints
URL_READ_BACKTEST = "https://www.quantconnect.com/api/v2/backtests/read"
URL_READ_PROJECT = "https://www.quantconnect.com/api/v2/projects/read"
URL_LIST_PROJECT_BACKTEST = "https://www.quantconnect.com/api/v2/backtests/list"


# Project IDs
MONTHLY_PROJECT_IDS = [19333694]
OTHER_PROJECT_IDS = [19395255]
INTRADAY_PROJECT_IDS = [19014068, 19015686, 19016182, 19016331, 19025603, 19015442, 19087390, 19087500, 19095659, 
                        19113130, 19134299, 19359592]

PROJECT_IDS = INTRADAY_PROJECT_IDS + MONTHLY_PROJECT_IDS + OTHER_PROJECT_IDS

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

@st.cache_data
def list_backtests(project_id):
    response = requests.post(URL_LIST_PROJECT_BACKTEST, headers=get_authenticated_headers(), data={'projectId': project_id, 'includeStatistics': True})
    if response.status_code == 200:
        return response.json().get('backtests', [])
    else:
        print("Failed to list backtests:", response.status_code, response.text)
        return []

@st.cache_data
def fetch_project_details(project_id):
    headers = get_authenticated_headers()
    response = requests.post(URL_READ_PROJECT, headers=headers, data={'projectId': project_id})
    if response.status_code == 200:
        return response.json()['projects'][0]
    else:
        print("Failed to retrieve project details:", response.status_code, response.text)
        return None

@st.cache_data
def fetch_backtest_result(project_id, backtest_id):
    headers = get_authenticated_headers()
    response = requests.post(URL_READ_BACKTEST, headers=headers, data={'projectId': project_id, 'backtestId': backtest_id})
    if response.status_code == 200:
        return response.json().get('backtest', {})
    else:
        print("Failed to retrieve backtest results:", response.status_code, response.text)
        return {}

def create_project_name_mapping(PROJECT_IDS):
    project_details = {ID: fetch_project_details(ID) for ID in PROJECT_IDS}
    project_names_short = {ID: re.findall(r'\d+', details['name'])[0] if details and 'name' in details else 'Unknown' for ID, details in project_details.items()}
    return project_names_short

def create_short_to_full_name_mapping(PROJECT_IDS):
    project_details = {ID: fetch_project_details(ID) for ID in PROJECT_IDS}
    short_to_full_name_map = {
        re.findall(r'\d+', details['name'])[0]: (details['name'][3+len(re.findall(r'\d+', details['name'])[0]):].strip(), ID)
        if details and 'name' in details else ('Unknown', ID)
        for ID, details in project_details.items()
    }
    return short_to_full_name_map


def process_data(backtest_period):
    project_names_map = create_short_to_full_name_mapping(PROJECT_IDS)
    project_names_short = create_project_name_mapping(PROJECT_IDS)
    
    backtest_metrics = ['alpha', 'beta', 'compoundingAnnualReturn', 'drawdown', 'lossRate', 'netProfit', 'parameters', 'psr', 'sortinoRatio', 'trades', 'treynorRatio', 'winRate', 'backtestId']

    strategy_dict = {ID: next((bkt for bkt in list_backtests(ID) if bkt['name'] == backtest_period), None) for ID in PROJECT_IDS}
    missing_IDs = [str(ID) for ID in PROJECT_IDS if not strategy_dict.get(ID)]
    if missing_IDs:
        st.write(f"No data found for project IDs: {', '.join(missing_IDs)}")

    strategy_dict = {k: v for k, v in strategy_dict.items() if v is not None}

    df_metrics = pd.DataFrame({k: {m: v[m] for m in backtest_metrics if m in v} for k, v in strategy_dict.items()}).transpose()

    strategy_equity_dict = {}
    strategy_return_dict = {}
    strategy_trades_dict = {}

    for projectID, row in df_metrics.iterrows():
        backtest_result = fetch_backtest_result(project_id=projectID, backtest_id=row['backtestId'])

        if 'charts' in backtest_result and 'Strategy Equity' in backtest_result['charts']:
            equity_values = backtest_result['charts']['Strategy Equity']['series']['Equity']['values']
            equity_df = pd.DataFrame(equity_values, columns=['Timestamp', 'Open', 'High', 'Low', 'Close'])
            equity_df.index = pd.to_datetime(equity_df['Timestamp'], unit='s')
            equity_df.drop(columns=['Timestamp', 'Open', 'High', 'Low'], inplace=True)
            strategy_equity_dict[projectID] = equity_df

            return_values = backtest_result['charts']['Strategy Equity']['series']['Return']['values']
            return_df = pd.DataFrame(return_values, columns=['Timestamp', 'Return'])
            return_df.index = pd.to_datetime(return_df['Timestamp'], unit='s')
            return_df.drop(columns=['Timestamp'], inplace=True)
            strategy_return_dict[projectID] = return_df

        if 'totalPerformance' in backtest_result and 'closedTrades' in backtest_result['totalPerformance']:
            trades = backtest_result['totalPerformance']['closedTrades']
            trade_df = pd.DataFrame([{
                **{f'symbol_{k}': v for k, v in trade.get('symbol', {}).items()}, 
                **{k: v for k, v in trade.items() if k not in ['symbol', 'direction', 'symbol_value', 'symbol_id']}
            } for trade in trades])
            strategy_trades_dict[projectID] = trade_df

    df = pd.DataFrame({
        ID: {
            **backtest_result.get('statistics', {}),
            **backtest_result.get('totalPerformance', {}).get('tradeStatistics', {}),
            **backtest_result.get('totalPerformance', {}).get('portfolioStatistics', {}),
            **backtest_result.get('runtimeStatistics', {})
        }
        for ID, backtest_result in strategy_dict.items()
    }).transpose()

    df.index.name = 'ProjectID'

    final_df = pd.concat([df_metrics, df], axis=1)
    final_df = final_df.T
    
    final_df.columns = [project_names_short[ID] for ID in final_df.columns]

    mask_first = final_df.index.isin(['winRate', 'lossRate', 'sortinoRatio', 'beta', 'alpha', 'treynorRatio']) & final_df.index.duplicated(keep='last')
    mask_second = ~final_df.index.isin(['winRate', 'lossRate', 'sortinoRatio', 'beta', 'alpha', 'treynorRatio']) & final_df.index.duplicated(keep='first')
    final_df = final_df[~(mask_first | mask_second)]

    return strategy_equity_dict, final_df, project_names_map

def create_equity_df(strategy_equity_dict):
    strategy_equity_df = pd.concat({projectID: df['Close'] for projectID, df in strategy_equity_dict.items()}, axis=1)
    project_names = {ID: fetch_project_details(ID)['name'][3:] for ID in strategy_equity_df.columns}
    strategy_equity_df.columns = [project_names.get(ID, ID) for ID in strategy_equity_df.columns]
    strategy_equity_df.sort_index(inplace=True)
    strategy_equity_df.ffill(inplace=True)
    return strategy_equity_df

@st.cache_data
def get_processed_data(backtest_period):
    return process_data(backtest_period)

def main():
    st.set_page_config(layout="wide")
    st.title("Strategies Dashboard")

    backtest_periods = ['YTD', '5YR', '2023']
    selected_backtest_period = st.selectbox("Select Backtest Period", options=backtest_periods)

    strategy_equity_dict, final_df, project_names_map = get_processed_data(selected_backtest_period)
    strategy_equity_df = create_equity_df(strategy_equity_dict)
    
    strategy_equity_df.columns = [re.findall(r'\d+', col)[0] if re.findall(r'\d+', col) else 'Unknown' for col in strategy_equity_df.columns]
    
    if selected_backtest_period == '5YR':
        strategy_equity_df = strategy_equity_df.loc['2019-01-01':]
    elif selected_backtest_period == '2023':
        strategy_equity_df = strategy_equity_df.loc['2023-01-01':]
    elif selected_backtest_period == 'YTD':
        strategy_equity_df = strategy_equity_df.loc['2024-01-01':]

    fig = px.line(strategy_equity_df, x=strategy_equity_df.index, y=strategy_equity_df.columns, title='Equity Curve')
    st.plotly_chart(fig, use_container_width=True)

    if not final_df.empty:
        st.write("Strategy Metrics Table:")
        st.dataframe(final_df, height=600, use_container_width=True)
    else:
        st.write("No data available to display.")

    st.write("Strategy Keys:")
    df = pd.DataFrame([(key, name_id[0], name_id[1]) for key, name_id in project_names_map.items()], 
                      columns=['Key', 'Strategy Name', 'QuantConnect ID'])
    df.index = df.index + 1
    st.table(df)

if __name__ == "__main__":
    main()
